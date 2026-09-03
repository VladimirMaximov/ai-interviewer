"""Persistence model definitions; audio bytes live only in object storage."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
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


class InterviewInvitation(Base):
    __tablename__ = "interview_invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[InvitationStatus] = mapped_column(Enum(InvitationStatus, values_callable=lambda items: [item.value for item in items]), default=InvitationStatus.ACTIVE)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(ForeignKey("interview_invitations.id"), unique=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CandidateResponse(Base):
    __tablename__ = "candidate_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    question_id: Mapped[UUID] = mapped_column(index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    content_type: Mapped[str] = mapped_column(String(128))
    checksum: Mapped[str] = mapped_column(String(128))
    transcription_status: Mapped[TranscriptionStatus] = mapped_column(
        Enum(TranscriptionStatus, values_callable=lambda items: [item.value for item in items]), default=TranscriptionStatus.PENDING
    )
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
