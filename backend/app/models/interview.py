"""Persistence model definitions; audio bytes live only in object storage."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.proctoring import (
    MonitoringEventKind,
    MonitoringReviewStatus,
    VoiceProfileStatus,
)


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
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
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


class InterviewMonitoringEvent(Base):
    """A bounded media interval requiring review, never a hiring decision."""

    __tablename__ = "interview_monitoring_events"
    __table_args__ = (
        CheckConstraint(
            "started_at_ms >= 0 AND ended_at_ms > started_at_ms",
            name="ck_monitoring_event_interval",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    response_id: Mapped[UUID] = mapped_column(
        ForeignKey("candidate_responses.id"), index=True
    )
    question_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[MonitoringEventKind] = mapped_column(
        Enum(
            MonitoringEventKind,
            values_callable=lambda items: [item.value for item in items],
        )
    )
    started_at_ms: Mapped[int] = mapped_column(Integer)
    ended_at_ms: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    detector_name: Mapped[str] = mapped_column(String(120))
    detector_version: Mapped[str] = mapped_column(String(80))
    evidence_storage_key: Mapped[str | None] = mapped_column(
        String(512), unique=True, nullable=True
    )
    evidence_content_type: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    evidence_checksum: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    review_status: Mapped[MonitoringReviewStatus] = mapped_column(
        Enum(
            MonitoringReviewStatus,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=MonitoringReviewStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewVoiceProfile(Base):
    """Profile readiness and references; no biometric embedding is persisted."""

    __tablename__ = "interview_voice_profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id"), unique=True, index=True
    )
    first_response_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_responses.id"), nullable=True
    )
    second_response_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_responses.id"), nullable=True
    )
    status: Mapped[VoiceProfileStatus] = mapped_column(
        Enum(
            VoiceProfileStatus,
            values_callable=lambda items: [item.value for item in items],
        ),
        default=VoiceProfileStatus.COLLECTING,
    )
    reason_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detector_name: Mapped[str] = mapped_column(String(120))
    detector_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
