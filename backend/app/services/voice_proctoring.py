"""Asynchronous voice-profile bootstrap and evidence interval persistence."""

from __future__ import annotations

import tempfile
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.storage import PrivateObjectStorage
from app.domain.proctoring import (
    MonitoringEventKind,
    ReferenceAudio,
    TimeInterval,
    VoiceAnalysisResult,
    VoiceProfileStatus,
    VoiceProfileValidation,
)
from app.models.interview import (
    CandidateResponse,
    InterviewMonitoringEvent,
    InterviewVoiceProfile,
)


EVENT_NAMESPACE = UUID("43d24c67-62ba-49ea-811a-9484f1e52c42")


class VoiceAnalyzer(Protocol):
    name: str
    version: str

    def validate_references(
        self, references: tuple[ReferenceAudio, ReferenceAudio]
    ) -> VoiceProfileValidation: ...

    def inspect(self, target: Path) -> VoiceAnalysisResult: ...

    def analyze(
        self,
        references: tuple[ReferenceAudio, ReferenceAudio],
        target: Path,
    ) -> VoiceAnalysisResult: ...


class VoiceProctoringScheduler:
    """Run heavyweight speaker analysis outside candidate API requests."""

    def __init__(
        self,
        sessions: sessionmaker,
        storage: PrivateObjectStorage,
        analyzer: VoiceAnalyzer,
        *,
        executor: Executor | None = None,
    ) -> None:
        self.sessions = sessions
        self.storage = storage
        self.analyzer = analyzer
        self.executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="voice-proctoring"
        )

    def schedule(self, response_id: UUID) -> None:
        self.executor.submit(self._run, response_id)

    def _run(self, response_id: UUID) -> None:
        with self.sessions() as db:
            target = db.get(CandidateResponse, response_id)
            if not target or not target.checksum:
                return
            responses = list(
                db.scalars(
                    select(CandidateResponse)
                    .where(
                        CandidateResponse.session_id == target.session_id,
                        CandidateResponse.checksum != "",
                    )
                    .order_by(CandidateResponse.created_at, CandidateResponse.id)
                )
            )
            try:
                position = next(
                    index
                    for index, response in enumerate(responses)
                    if response.id == response_id
                )
            except StopIteration:
                return
            references = (
                (responses[0], responses[1]) if position >= 1 else None
            )
            exclusions = (
                {
                    response.id: self._excluded_intervals(db, response.id)
                    for response in references
                }
                if references
                else {}
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix="ai-interviewer-voice-"
            ) as directory:
                directory_path = Path(directory)
                if position == 0:
                    target_path = directory_path / "target.webm"
                    self.storage.download_to(target.storage_key, target_path)
                    result = self.analyzer.inspect(target_path)
                    validation = VoiceProfileValidation(
                        VoiceProfileStatus.COLLECTING
                    )
                else:
                    reference_audio = self._download_references(
                        references, exclusions, directory_path
                    )
                if position == 1:
                    validation = self.analyzer.validate_references(
                        reference_audio
                    )
                    result = self.analyzer.inspect(reference_audio[1].path)
                elif position > 1:
                    target_path = directory_path / "target.webm"
                    self.storage.download_to(target.storage_key, target_path)
                    result = self.analyzer.analyze(
                        reference_audio, target_path
                    )
                    validation = result.profile
        except Exception:
            validation = VoiceProfileValidation(
                VoiceProfileStatus.NOT_READY, "voice_analysis_failed"
            )
            result = None

        with self.sessions() as db:
            self._save_profile(
                db,
                target.session_id,
                first=(references[0].id if references else target.id),
                second=(references[1].id if references else None),
                validation=validation,
            )
            if result:
                self._save_events(db, target, result)

    def _download_references(
        self,
        responses: tuple[CandidateResponse, CandidateResponse],
        exclusions: dict[UUID, tuple[TimeInterval, ...]],
        directory: Path,
    ) -> tuple[ReferenceAudio, ReferenceAudio]:
        downloaded = []
        for index, response in enumerate(responses):
            path = directory / f"reference-{index + 1}.webm"
            self.storage.download_to(response.storage_key, path)
            downloaded.append(ReferenceAudio(path, exclusions[response.id]))
        return downloaded[0], downloaded[1]

    @staticmethod
    def _excluded_intervals(
        db: Session, response_id: UUID
    ) -> tuple[TimeInterval, ...]:
        events = db.scalars(
            select(InterviewMonitoringEvent).where(
                InterviewMonitoringEvent.response_id == response_id,
                InterviewMonitoringEvent.kind.in_(
                    [
                        MonitoringEventKind.FACE_MISSING,
                        MonitoringEventKind.MULTIPLE_FACES,
                        MonitoringEventKind.FACE_DETECTION_UNAVAILABLE,
                    ]
                ),
            )
        )
        return tuple(
            TimeInterval(item.started_at_ms, item.ended_at_ms)
            for item in events
        )

    def _save_profile(
        self,
        db: Session,
        session_id: UUID,
        *,
        first: UUID,
        second: UUID | None,
        validation: VoiceProfileValidation,
    ) -> None:
        now = datetime.now(timezone.utc)
        profile = db.scalar(
            select(InterviewVoiceProfile).where(
                InterviewVoiceProfile.session_id == session_id
            )
        )
        if not profile:
            profile = InterviewVoiceProfile(
                session_id=session_id,
                detector_name=self.analyzer.name,
                detector_version=self.analyzer.version,
                created_at=now,
                updated_at=now,
            )
            db.add(profile)
        profile.first_response_id = first
        profile.second_response_id = second
        profile.status = validation.status
        profile.reason_code = validation.reason_code
        profile.updated_at = now
        db.commit()

    @staticmethod
    def _save_events(
        db: Session, target: CandidateResponse, result: VoiceAnalysisResult
    ) -> None:
        now = datetime.now(timezone.utc)
        for detected in result.events:
            stable_key = ":".join(
                [
                    str(target.id),
                    detected.kind.value,
                    str(detected.interval.start_ms),
                    str(detected.interval.end_ms),
                    result.detector_version,
                ]
            )
            event_id = uuid5(EVENT_NAMESPACE, stable_key)
            if db.get(InterviewMonitoringEvent, event_id):
                continue
            db.add(
                InterviewMonitoringEvent(
                    id=event_id,
                    session_id=target.session_id,
                    response_id=target.id,
                    question_id=target.question_id,
                    kind=detected.kind,
                    started_at_ms=detected.interval.start_ms,
                    ended_at_ms=detected.interval.end_ms,
                    confidence=detected.confidence,
                    source="server_voice",
                    detector_name=result.detector_name,
                    detector_version=result.detector_version,
                    created_at=now,
                )
            )
        db.commit()
