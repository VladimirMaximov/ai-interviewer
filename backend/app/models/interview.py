"""Persistence model definitions; audio bytes live only in object storage."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.proctoring import MonitoringEventKind, MonitoringReviewStatus, VoiceProfileStatus


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class InvitationStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    SUBMITTED = "submitted"


class TranscriptionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FollowUpStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    PRESENTED = "presented"
    ANSWERED = "answered"
    SKIPPED = "skipped"
    FAILED = "failed"


class RuntimeEvaluationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class AvatarAssetStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TimelineEventType(StrEnum):
    AVATAR_STARTED = "avatar_started"
    AVATAR_FINISHED = "avatar_finished"
    RECORDING_STARTED = "recording_started"
    QUESTION_SHOWN = "question_shown"
    ANSWER_SAVED = "answer_saved"
    NEXT_QUESTION_CLICKED = "next_question_clicked"
    INTERVIEW_SUBMITTED = "interview_submitted"
    PAGE_HIDDEN = "page_hidden"
    PAGE_VISIBLE = "page_visible"
    WINDOW_BLURRED = "window_blurred"
    WINDOW_FOCUSED = "window_focused"
    PAGE_COPY = "page_copy"


class InterviewInvitation(Base):
    __tablename__ = "interview_invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    vacancy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vacancies.id"), index=True, nullable=True
    )
    candidate_alias: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=InvitationStatus.ACTIVE,
    )
    # Server-owned input contract for the candidate question sequence. It holds
    # no candidate answers or media and survives UI changes.
    question_config: Mapped[dict | list[dict] | None] = mapped_column(JSON, nullable=True)
    follow_up_after_all_answers: Mapped[bool] = mapped_column(Boolean, default=False)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_invitations.id"), unique=True
    )
    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CandidateResponse(Base):
    __tablename__ = "candidate_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    question_id: Mapped[UUID] = mapped_column(index=True)
    # Legacy per-answer uploads may have a key. New responses point to an
    # interval in InterviewRecording instead, so a key is intentionally null.
    storage_key: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    content_type: Mapped[str] = mapped_column(String(128))
    checksum: Mapped[str] = mapped_column(String(128))
    transcription_status: Mapped[TranscriptionStatus] = mapped_column(
        Enum(
            TranscriptionStatus,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=TranscriptionStatus.PENDING,
    )
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    start_offset_ms: Mapped[int | None] = mapped_column(nullable=True)
    end_offset_ms: Mapped[int | None] = mapped_column(nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)


class InterviewMonitoringEvent(Base):
    """A bounded media interval requiring review, never a hiring decision."""

    __tablename__ = "interview_monitoring_events"
    __table_args__ = (CheckConstraint("started_at_ms >= 0 AND ended_at_ms > started_at_ms", name="ck_monitoring_event_interval"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    response_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_responses.id"), index=True)
    question_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[MonitoringEventKind] = mapped_column(Enum(MonitoringEventKind, values_callable=lambda items: [item.value for item in items]))
    started_at_ms: Mapped[int] = mapped_column(Integer)
    ended_at_ms: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    detector_name: Mapped[str] = mapped_column(String(120))
    detector_version: Mapped[str] = mapped_column(String(80))
    evidence_storage_key: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    evidence_content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_status: Mapped[MonitoringReviewStatus] = mapped_column(Enum(MonitoringReviewStatus, values_callable=lambda items: [item.value for item in items]), default=MonitoringReviewStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewVoiceProfile(Base):
    """Profile readiness and references; no biometric embedding is persisted."""

    __tablename__ = "interview_voice_profiles"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), unique=True, index=True)
    first_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidate_responses.id"), nullable=True)
    second_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidate_responses.id"), nullable=True)
    status: Mapped[VoiceProfileStatus] = mapped_column(Enum(VoiceProfileStatus, values_callable=lambda items: [item.value for item in items]), default=VoiceProfileStatus.COLLECTING)
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detector_name: Mapped[str] = mapped_column(String(120))
    detector_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionAvatarAsset(Base):
    """A private pre-rendered talking-head video for one interview question."""

    __tablename__ = "question_avatar_assets"
    __table_args__ = (UniqueConstraint("invitation_id", "question_id", name="uq_avatar_question"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(ForeignKey("interview_invitations.id"), index=True)
    question_id: Mapped[UUID] = mapped_column(index=True)
    renderer: Mapped[str] = mapped_column(String(64))
    status: Mapped[AvatarAssetStatus] = mapped_column(
        Enum(AvatarAssetStatus, values_callable=lambda values: [value.value for value in values]),
        default=AvatarAssetStatus.PENDING,
    )
    audio_storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    video_storage_key: Mapped[str | None] = mapped_column(String(512), unique=True, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewRecording(Base):
    __tablename__ = "interview_recordings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), unique=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(128))
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Duration is derived from confirmed media offsets, not browser wall-clock time.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class InterviewRecordingChunk(Base):
    """One independently uploaded ten-second fragment of a recording."""

    __tablename__ = "interview_recording_chunks"
    __table_args__ = (UniqueConstraint("recording_id", "sequence", name="uq_recording_chunk_sequence"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recording_id: Mapped[UUID] = mapped_column(ForeignKey("interview_recordings.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(128))
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    end_offset_ms: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewTimelineEvent(Base):
    __tablename__ = "interview_timeline_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question_id: Mapped[UUID | None] = mapped_column(nullable=True)
    event_type: Mapped[TimelineEventType] = mapped_column(Enum(TimelineEventType, values_callable=lambda items: [item.value for item in items]))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recording_offset_ms: Mapped[int] = mapped_column()


class InterviewFollowUpQuestion(Base):
    """A future agent may enqueue one optional clarification for a response."""

    __tablename__ = "interview_follow_up_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    source_response_id: Mapped[UUID | None] = mapped_column(ForeignKey("candidate_responses.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[FollowUpStatus] = mapped_column(
        Enum(FollowUpStatus, values_callable=lambda items: [item.value for item in items]), default=FollowUpStatus.PENDING
    )
    transcript_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RuntimeEvaluationJob(Base):
    """One bounded, asynchronous evaluation of a completed base answer."""

    __tablename__ = "runtime_evaluation_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    response_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_responses.id"), unique=True, index=True)
    status: Mapped[RuntimeEvaluationStatus] = mapped_column(
        Enum(RuntimeEvaluationStatus, values_callable=lambda items: [item.value for item in items]),
        default=RuntimeEvaluationStatus.PENDING,
    )
    question_text: Mapped[str] = mapped_column(Text)
    # `answer_text` remains for backwards-compatible audit reads. New jobs
    # record the two evidence channels explicitly below.
    answer_text: Mapped[str] = mapped_column(Text)
    spoken_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CodeAnswer(Base):
    """Candidate-authored source code; it is stored but never executed here."""

    __tablename__ = "code_answers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    response_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_responses.id"), unique=True, index=True)
    language: Mapped[str] = mapped_column(String(64))
    source_code: Mapped[str] = mapped_column(Text)
    start_offset_ms: Mapped[int] = mapped_column(Integer)
    end_offset_ms: Mapped[int] = mapped_column(Integer)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
