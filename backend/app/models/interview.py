"""Persistence model definitions; audio bytes live only in object storage."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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


class TimelineEventType(StrEnum):
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


class InterviewRecording(Base):
    __tablename__ = "interview_recordings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), unique=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(128))
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
