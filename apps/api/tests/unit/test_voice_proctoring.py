from concurrent.futures import Executor, Future
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.proctoring import (
    DetectedVoiceEvent,
    MonitoringEventKind,
    ReferenceAudio,
    TimeInterval,
    VoiceAnalysisResult,
    VoiceProfileStatus,
    VoiceProfileValidation,
)
from app.models.interview import (
    Base,
    CandidateResponse,
    InterviewInvitation,
    InterviewMonitoringEvent,
    InterviewSession,
    InterviewVoiceProfile,
    TranscriptionStatus,
)
from app.services.voice_proctoring import VoiceProctoringScheduler


class ImmediateExecutor(Executor):
    def submit(self, fn, /, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as error:
            future.set_exception(error)
        return future


class FakeStorage:
    def download_to(self, key: str, destination: Path) -> None:
        destination.write_bytes(key.encode())


class FakeAnalyzer:
    name = "synthetic_speaker_analyzer"
    version = "test_v1"

    def __init__(self) -> None:
        self.references: tuple[ReferenceAudio, ReferenceAudio] | None = None

    def validate_references(self, references):
        self.references = references
        return VoiceProfileValidation(VoiceProfileStatus.READY)

    def inspect(self, target):
        if not target.is_file():
            raise AssertionError("target was not downloaded")
        return VoiceAnalysisResult(
            VoiceProfileValidation(VoiceProfileStatus.COLLECTING),
            (
                DetectedVoiceEvent(
                    MonitoringEventKind.OVERLAPPING_SPEECH,
                    TimeInterval(200, 600),
                ),
            ),
            self.name,
            self.version,
        )

    def analyze(self, references, target):
        self.references = references
        self.assert_files(references, target)
        return VoiceAnalysisResult(
            VoiceProfileValidation(VoiceProfileStatus.READY),
            (
                DetectedVoiceEvent(
                    MonitoringEventKind.OVERLAPPING_SPEECH,
                    TimeInterval(1_000, 1_800),
                    0.9,
                ),
            ),
            self.name,
            self.version,
        )

    @staticmethod
    def assert_files(references, target) -> None:
        if not all(item.path.is_file() for item in references):
            raise AssertionError("reference was not downloaded")
        if not target.is_file():
            raise AssertionError("target was not downloaded")


class VoiceProctoringSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        now = datetime.now(timezone.utc)
        with self.sessions() as db:
            invitation = InterviewInvitation(
                token_digest="a" * 64,
                expires_at=now + timedelta(hours=1),
            )
            db.add(invitation)
            db.flush()
            interview = InterviewSession(
                invitation_id=invitation.id,
                consented_at=now,
            )
            db.add(interview)
            db.flush()
            self.response_ids = []
            for index in range(3):
                response = CandidateResponse(
                    session_id=interview.id,
                    question_id=uuid4(),
                    storage_key=f"responses/{index}.webm",
                    content_type="audio/webm",
                    checksum=str(index + 1) * 64,
                    transcription_status=TranscriptionStatus.PROCESSING,
                    created_at=now + timedelta(seconds=index),
                )
                db.add(response)
                db.flush()
                self.response_ids.append(response.id)
            db.add(
                InterviewMonitoringEvent(
                    session_id=interview.id,
                    response_id=self.response_ids[0],
                    question_id=db.get(
                        CandidateResponse, self.response_ids[0]
                    ).question_id,
                    kind=MonitoringEventKind.FACE_MISSING,
                    started_at_ms=5_000,
                    ended_at_ms=8_000,
                    source="browser_face",
                    detector_name="mediapipe_face_detector",
                    detector_version="face_presence_v1",
                    created_at=now,
                )
            )
            db.commit()

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_third_answer_uses_first_two_references_and_persists_signal(self) -> None:
        analyzer = FakeAnalyzer()
        scheduler = VoiceProctoringScheduler(
            self.sessions,
            FakeStorage(),
            analyzer,
            executor=ImmediateExecutor(),
        )

        scheduler.schedule(self.response_ids[2])

        with self.sessions() as db:
            profile = db.scalar(select(InterviewVoiceProfile))
            signals = list(
                db.scalars(
                    select(InterviewMonitoringEvent).where(
                        InterviewMonitoringEvent.source == "server_voice"
                    )
                )
            )
        self.assertEqual(profile.status, VoiceProfileStatus.READY)
        self.assertEqual(profile.first_response_id, self.response_ids[0])
        self.assertEqual(profile.second_response_id, self.response_ids[1])
        self.assertEqual(len(signals), 1)
        self.assertEqual(
            signals[0].kind, MonitoringEventKind.OVERLAPPING_SPEECH
        )
        self.assertEqual(
            analyzer.references[0].excluded_intervals,
            (TimeInterval(5_000, 8_000),),
        )

    def test_first_answer_detects_overlap_while_profile_is_collecting(self) -> None:
        scheduler = VoiceProctoringScheduler(
            self.sessions,
            FakeStorage(),
            FakeAnalyzer(),
            executor=ImmediateExecutor(),
        )

        scheduler.schedule(self.response_ids[0])

        with self.sessions() as db:
            profile = db.scalar(select(InterviewVoiceProfile))
            signal = db.scalar(
                select(InterviewMonitoringEvent).where(
                    InterviewMonitoringEvent.source == "server_voice"
                )
            )
        self.assertEqual(profile.status, VoiceProfileStatus.COLLECTING)
        self.assertIsNone(profile.second_response_id)
        self.assertEqual(
            signal.kind, MonitoringEventKind.OVERLAPPING_SPEECH
        )


if __name__ == "__main__":
    unittest.main()
