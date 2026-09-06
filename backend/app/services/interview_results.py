"""Recruiter-only projections of persisted interview evidence."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage import PrivateObjectStorage
from app.interview_config import invitation_input
from app.models.hiring_context import Vacancy
from app.models.interview import (
    CandidateResponse, CodeAnswer, InterviewFollowUpQuestion, InterviewInvitation,
    InterviewMonitoringEvent, InterviewRecording, InterviewRecordingChunk,
    InterviewSession, TranscriptionStatus,
)
from app.config import settings
from app.security.media_access import create_media_signature


class InterviewResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID | None
    invitation_id: UUID
    candidate_alias: str | None
    status: Literal["invited", "in_progress", "processing", "completed"]
    score: float | None = None
    answered_questions: int
    total_questions: int
    expires_at: datetime
    submitted_at: datetime | None


class ResultMedia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int
    start_offset_ms: int
    end_offset_ms: int
    content_type: str
    url: str


class ResultCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str
    source_code: str


class ResultAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_id: UUID
    question_id: UUID
    question_text: str
    question_kind: str
    is_follow_up: bool
    transcription_status: str
    transcript_text: str | None
    start_offset_ms: int | None
    end_offset_ms: int | None
    timed_out: bool
    code: ResultCode | None


class ResultMonitoringEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    response_id: UUID
    question_id: UUID
    kind: str
    started_at_ms: int
    ended_at_ms: int
    review_status: str
    evidence_url: str | None


class InterviewResultDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: InterviewResultSummary
    vacancy_title: str
    recording_duration_ms: int | None
    media: list[ResultMedia]
    answers: list[ResultAnswer]
    monitoring_events: list[ResultMonitoringEvent]
    assessment: dict | None = None


class InterviewResultsService:
    def __init__(self, db: Session, storage: PrivateObjectStorage) -> None:
        self.db, self.storage = db, storage

    def close(self) -> None:
        self.db.close()

    def media_key(self, vacancy_id: UUID, session_id: UUID, sequence: int) -> tuple[str, str] | None:
        vacancy = self.db.get(Vacancy, vacancy_id)
        session = self.db.get(InterviewSession, session_id)
        invitation = self.db.get(InterviewInvitation, session.invitation_id) if session else None
        recording = self.db.scalar(select(InterviewRecording).where(InterviewRecording.session_id == session_id))
        if not vacancy or not invitation or invitation.vacancy_id != vacancy_id or not recording:
            return None
        extension = "mp4" if recording.content_type == "video/mp4" else "webm"
        full_key = f"{recording.storage_key}/full.{extension}"
        if sequence == 0 and self.storage.object_exists(full_key):
            return full_key, recording.content_type
        chunk = self.db.scalar(select(InterviewRecordingChunk).where(
            InterviewRecordingChunk.recording_id == recording.id,
            InterviewRecordingChunk.sequence == sequence,
            InterviewRecordingChunk.uploaded_at.is_not(None),
        ))
        return (chunk.storage_key, chunk.content_type) if chunk else None

    def _summary(self, invitation: InterviewInvitation) -> InterviewResultSummary:
        session = self.db.scalar(select(InterviewSession).where(
            InterviewSession.invitation_id == invitation.id
        ))
        configured = invitation_input(invitation.question_config, invitation.follow_up_after_all_answers)
        responses = list(self.db.scalars(select(CandidateResponse).where(
            CandidateResponse.session_id == session.id
        ))) if session else []
        if not session:
            state = "invited"
        elif not session.submitted_at:
            state = "in_progress"
        elif any(item.transcription_status in {TranscriptionStatus.PENDING, TranscriptionStatus.PROCESSING} for item in responses):
            state = "processing"
        else:
            state = "completed"
        return InterviewResultSummary(
            session_id=session.id if session else None, invitation_id=invitation.id,
            candidate_alias=invitation.candidate_alias, status=state,
            answered_questions=len(responses), total_questions=len(configured.questions),
            expires_at=invitation.expires_at, submitted_at=session.submitted_at if session else None,
        )

    def list_for_vacancy(self, vacancy_id: UUID) -> list[InterviewResultSummary]:
        if self.db.get(Vacancy, vacancy_id) is None:
            raise LookupError("vacancy was not found")
        invitations = self.db.scalars(select(InterviewInvitation).where(
            InterviewInvitation.vacancy_id == vacancy_id
        ).order_by(InterviewInvitation.expires_at.desc()))
        return [self._summary(item) for item in invitations]

    def detail(self, vacancy_id: UUID, session_id: UUID) -> InterviewResultDetail:
        vacancy = self.db.get(Vacancy, vacancy_id)
        session = self.db.get(InterviewSession, session_id)
        invitation = self.db.get(InterviewInvitation, session.invitation_id) if session else None
        if not vacancy or not invitation or invitation.vacancy_id != vacancy_id:
            raise LookupError("interview was not found")
        configured = invitation_input(invitation.question_config, invitation.follow_up_after_all_answers)
        question_map = {item.id: (item.text, item.kind.value, False) for item in configured.questions}
        follow_ups = self.db.scalars(select(InterviewFollowUpQuestion).where(
            InterviewFollowUpQuestion.session_id == session_id
        ))
        question_map.update({item.id: (item.text, "spoken", True) for item in follow_ups})
        responses = list(self.db.scalars(select(CandidateResponse).where(
            CandidateResponse.session_id == session_id
        ).order_by(CandidateResponse.start_offset_ms)))
        codes = {item.response_id: item for item in self.db.scalars(select(CodeAnswer).where(
            CodeAnswer.response_id.in_([response.id for response in responses])
        ))} if responses else {}
        answers = []
        for response in responses:
            text, kind, is_follow_up = question_map.get(response.question_id, ("Вопрос недоступен", "spoken", False))
            code = codes.get(response.id)
            answers.append(ResultAnswer(
                response_id=response.id, question_id=response.question_id,
                question_text=text, question_kind=kind, is_follow_up=is_follow_up,
                transcription_status=response.transcription_status.value,
                transcript_text=response.transcript_text,
                start_offset_ms=response.start_offset_ms, end_offset_ms=response.end_offset_ms,
                timed_out=response.timed_out,
                code=ResultCode(language=code.language, source_code=code.source_code) if code else None,
            ))
        recording = self.db.scalar(select(InterviewRecording).where(InterviewRecording.session_id == session_id))
        chunks = list(self.db.scalars(select(InterviewRecordingChunk).where(
            InterviewRecordingChunk.recording_id == recording.id,
            InterviewRecordingChunk.uploaded_at.is_not(None),
        ).order_by(InterviewRecordingChunk.sequence))) if recording else []
        media = chunks
        if recording:
            extension = "mp4" if recording.content_type == "video/mp4" else "webm"
            full_key = f"{recording.storage_key}/full.{extension}"
            object_exists = getattr(self.storage, "object_exists", None)
            if object_exists is not None and object_exists(full_key):
                expires, signature = create_media_signature(
                    vacancy_id, session_id, 0, settings.recruiter_key or ""
                )
                media = [ResultMedia(
                    sequence=0, start_offset_ms=0,
                    end_offset_ms=recording.duration_ms or 0,
                    content_type=recording.content_type,
                    url=(
                        f"/api/recruiter/vacancies/{vacancy_id}/interviews/"
                        f"{session_id}/media/0?expires={expires}&signature={signature}"
                    ),
                )]
        events = list(self.db.scalars(select(InterviewMonitoringEvent).where(
            InterviewMonitoringEvent.session_id == session_id
        ).order_by(InterviewMonitoringEvent.started_at_ms)))
        return InterviewResultDetail(
            summary=self._summary(invitation), vacancy_title=vacancy.title,
            recording_duration_ms=recording.duration_ms if recording else None,
            media=media if media and isinstance(media[0], ResultMedia) else [ResultMedia(
                sequence=item.sequence, start_offset_ms=item.start_offset_ms,
                end_offset_ms=item.end_offset_ms, content_type=item.content_type,
                url=self._signed_media_url(vacancy_id, session_id, item.sequence),
            ) for item in media], answers=answers,
            monitoring_events=[ResultMonitoringEvent(
                id=item.id, response_id=item.response_id, question_id=item.question_id,
                kind=item.kind.value, started_at_ms=item.started_at_ms,
                ended_at_ms=item.ended_at_ms, review_status=item.review_status.value,
                evidence_url=self.storage.create_download_url(item.evidence_storage_key) if item.evidence_storage_key else None,
            ) for item in events],
        )

    @staticmethod
    def _signed_media_url(vacancy_id: UUID, session_id: UUID, sequence: int) -> str:
        expires, signature = create_media_signature(
            vacancy_id, session_id, sequence, settings.recruiter_key or ""
        )
        return (
            f"/api/recruiter/vacancies/{vacancy_id}/interviews/{session_id}/"
            f"media/{sequence}?expires={expires}&signature={signature}"
        )
