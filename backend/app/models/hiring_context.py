"""Persistence models for uploaded vacancies and candidate resumes."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.hiring_context import VacancyStatus
from app.models.interview import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_vacancy_creator_idempotency_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    source_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(
            VacancyStatus,
            values_callable=lambda items: [item.value for item in items],
            name="vacancystatus",
        ),
        default=VacancyStatus.ACTIVE,
    )
    created_by: Mapped[str] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CandidateResume(Base):
    __tablename__ = "candidate_resumes"
    __table_args__ = (
        UniqueConstraint(
            "invitation_id",
            "version",
            name="uq_candidate_resume_version",
        ),
        UniqueConstraint(
            "invitation_id",
            "idempotency_key",
            name="uq_candidate_resume_idempotency_key",
        ),
        CheckConstraint(
            "uploaded_by_role IN ('candidate', 'recruiter')",
            name="ck_candidate_resume_uploader_role",
        ),
        CheckConstraint(
            "(uploaded_by_role = 'candidate' AND uploaded_by_actor_id IS NULL) OR "
            "(uploaded_by_role = 'recruiter' AND uploaded_by_actor_id IS NOT NULL)",
            name="ck_candidate_resume_uploader_actor",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_invitations.id"), index=True
    )
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    source_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(Integer)
    extracted_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    uploaded_by_role: Mapped[str] = mapped_column(String(20))
    uploaded_by_actor_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
