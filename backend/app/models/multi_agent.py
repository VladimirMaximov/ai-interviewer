"""Persistence models for the durable multi-agent interview harness."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.multi_agent import (
    AgentOperationStatus,
    AgentRunStatus,
    AgentSessionStatus,
    FeedbackReleaseStatus,
    RestrictionType,
)
from app.models.interview import Base


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    __table_args__ = (
        UniqueConstraint("invitation_id", name="uq_agent_session_invitation"),
        UniqueConstraint(
            "vacancy_id",
            "created_by",
            "idempotency_key",
            name="uq_agent_session_request",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_invitations.id"), index=True
    )
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    interview_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_sessions.id"), nullable=True
    )
    resume_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("candidate_resumes.id"), nullable=True
    )
    resume_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resume_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manager_brief_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("manager_brief_drafts.id"), nullable=True
    )
    manager_brief_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manager_brief_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vacancy_hash: Mapped[str] = mapped_column(String(64))
    criteria_version: Mapped[str] = mapped_column(String(80))
    scale_version: Mapped[str] = mapped_column(String(80))
    aggregation_version: Mapped[str] = mapped_column(String(80))
    policy_version: Mapped[str] = mapped_column(String(80))
    policy_payload: Mapped[dict] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[AgentSessionStatus] = mapped_column(
        Enum(
            AgentSessionStatus,
            values_callable=lambda items: [item.value for item in items],
            name="agentsessionstatus",
        )
    )
    created_by: Mapped[str] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentOperation(Base):
    __tablename__ = "agent_operations"
    __table_args__ = (
        UniqueConstraint(
            "agent_session_id",
            "purpose",
            "idempotency_key",
            name="uq_agent_operation_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_sessions.id"), index=True
    )
    purpose: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    input_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[AgentOperationStatus] = mapped_column(
        Enum(
            AgentOperationStatus,
            values_callable=lambda items: [item.value for item in items],
            name="agentoperationstatus",
        )
    )
    output_artifact_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint(
            "operation_id", "attempt", name="uq_agent_run_operation_attempt"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    operation_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_operations.id"), index=True
    )
    attempt: Mapped[int] = mapped_column(Integer)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            values_callable=lambda items: [item.value for item in items],
            name="agentrunstatus",
        )
    )
    contract_version: Mapped[str] = mapped_column(String(80))
    model_id: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(120))
    prompt_id: Mapped[str] = mapped_column(String(120))
    input_hash: Mapped[str] = mapped_column(String(64))
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentArtifact(Base):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_agent_artifact_operation"),
        UniqueConstraint(
            "agent_session_id",
            "kind",
            "content_hash",
            name="uq_agent_artifact_content",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    agent_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_sessions.id"), index=True
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent_operations.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(80), index=True)
    schema_version: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CandidateFeedbackRelease(Base):
    __tablename__ = "candidate_feedback_releases"
    __table_args__ = (
        UniqueConstraint(
            "feedback_artifact_id", name="uq_candidate_feedback_release_artifact"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_invitations.id"), index=True
    )
    agent_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_sessions.id"), index=True
    )
    feedback_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_artifacts.id"), index=True
    )
    status: Mapped[FeedbackReleaseStatus] = mapped_column(
        Enum(
            FeedbackReleaseStatus,
            values_callable=lambda items: [item.value for item in items],
            name="feedbackreleasestatus",
        )
    )
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class RankingSnapshot(Base):
    __tablename__ = "ranking_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "vacancy_id", "input_hash", name="uq_ranking_snapshot_input"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id"), index=True)
    compatibility_key: Mapped[str] = mapped_column(String(64), index=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RankingEntry(Base):
    __tablename__ = "ranking_entries"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "rank", name="uq_ranking_entry_rank"),
        UniqueConstraint(
            "snapshot_id", "agent_session_id", name="uq_ranking_entry_session"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("ranking_snapshots.id"), index=True
    )
    agent_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_sessions.id"), index=True
    )
    profile_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent_artifacts.id"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    overall_value: Mapped[float] = mapped_column(Float)
    coverage: Mapped[float] = mapped_column(Float)
    tie_break_key: Mapped[str] = mapped_column(String(64))


class RestrictionDecision(Base):
    __tablename__ = "restriction_decisions"
    __table_args__ = (
        UniqueConstraint("supersedes_id", name="uq_restriction_superseded_once"),
        CheckConstraint(
            "decision_type = 'cleared' OR evidence_references IS NOT NULL",
            name="ck_restriction_evidence",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invitation_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_invitations.id"), index=True
    )
    decision_type: Mapped[RestrictionType] = mapped_column(
        Enum(
            RestrictionType,
            values_callable=lambda items: [item.value for item in items],
            name="restrictiontype",
        )
    )
    reason: Mapped[str] = mapped_column(String(2_000))
    evidence_references: Mapped[list[str]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    supersedes_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("restriction_decisions.id"), nullable=True
    )
