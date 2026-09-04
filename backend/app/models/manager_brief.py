"""Persistence models for manager-authored interview context."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.manager_brief import (
    AgentOperationStatus,
    AgentRunStatus,
    ManagerBriefStatus,
)
from app.models.interview import Base


class ManagerBriefOperation(Base):
    """One idempotent request to transform manager wishes into a draft."""

    __tablename__ = "manager_brief_operations"
    __table_args__ = (
        UniqueConstraint(
            "vacancy_id",
            "idempotency_key",
            name="uq_manager_brief_operation_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vacancy_id: Mapped[UUID] = mapped_column(index=True)
    actor_id: Mapped[str] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[AgentOperationStatus] = mapped_column(
        Enum(
            AgentOperationStatus,
            values_callable=lambda items: [item.value for item in items],
            name="managerbriefoperationstatus",
        )
    )
    output_draft_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ManagerBriefAgentRun(Base):
    """Audit record for one provider attempt; terminal attempts are never reused."""

    __tablename__ = "manager_brief_agent_runs"
    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            "attempt",
            name="uq_manager_brief_agent_attempt",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("manager_brief_operations.id"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            values_callable=lambda items: [item.value for item in items],
            name="managerbriefagentrunstatus",
        )
    )
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(120))
    prompt_id: Mapped[str] = mapped_column(String(120))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ManagerBriefDraft(Base):
    """Versioned, editable form generated from one manager source."""

    __tablename__ = "manager_brief_drafts"
    __table_args__ = (
        UniqueConstraint(
            "vacancy_id",
            "version",
            name="uq_manager_brief_draft_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vacancy_id: Mapped[UUID] = mapped_column(index=True)
    version: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ManagerBriefStatus] = mapped_column(
        Enum(
            ManagerBriefStatus,
            values_callable=lambda items: [item.value for item in items],
            name="managerbriefstatus",
        )
    )
    source_text: Mapped[str] = mapped_column(Text)
    source_fragments: Mapped[list[dict]] = mapped_column(JSON)
    fields_payload: Mapped[list[dict]] = mapped_column("fields", JSON)
    unresolved_fields: Mapped[list[dict]] = mapped_column(JSON)
    validation_issues: Mapped[list[dict]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    agent_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("manager_brief_agent_runs.id"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
