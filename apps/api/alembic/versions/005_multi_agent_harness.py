"""Add durable session-scoped multi-agent harness records.

Revision ID: 005_multi_agent_harness
Revises: 004_resume_uploader_audit
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "005_multi_agent_harness"
down_revision = "004_resume_uploader_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session_status = sa.Enum(
        "active", "ready", "failed", name="agentsessionstatus"
    )
    operation_status = sa.Enum(
        "running", "succeeded", "failed", name="agentoperationstatus"
    )
    run_status = sa.Enum(
        "running",
        "succeeded",
        "invalid_output",
        "provider_failed",
        name="agentrunstatus",
    )
    restriction_type = sa.Enum(
        "verified_misrepresentation",
        "restricted",
        "blacklisted",
        "cleared",
        name="restrictiontype",
    )

    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("interview_session_id", sa.Uuid(), nullable=True),
        sa.Column("resume_id", sa.Uuid(), nullable=True),
        sa.Column("resume_version", sa.Integer(), nullable=True),
        sa.Column("resume_hash", sa.String(length=64), nullable=True),
        sa.Column("manager_brief_id", sa.Uuid(), nullable=True),
        sa.Column("manager_brief_version", sa.Integer(), nullable=True),
        sa.Column("manager_brief_hash", sa.String(length=64), nullable=True),
        sa.Column("vacancy_hash", sa.String(length=64), nullable=False),
        sa.Column("criteria_version", sa.String(length=80), nullable=False),
        sa.Column("scale_version", sa.String(length=80), nullable=False),
        sa.Column("aggregation_version", sa.String(length=80), nullable=False),
        sa.Column("policy_version", sa.String(length=80), nullable=False),
        sa.Column("policy_payload", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", session_status, nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invitation_id"], ["interview_invitations.id"]),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"]),
        sa.ForeignKeyConstraint(["interview_session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["resume_id"], ["candidate_resumes.id"]),
        sa.ForeignKeyConstraint(["manager_brief_id"], ["manager_brief_drafts.id"]),
        sa.UniqueConstraint("invitation_id", name="uq_agent_session_invitation"),
        sa.UniqueConstraint(
            "vacancy_id",
            "created_by",
            "idempotency_key",
            name="uq_agent_session_request",
        ),
    )
    op.create_index("ix_agent_sessions_invitation_id", "agent_sessions", ["invitation_id"])
    op.create_index("ix_agent_sessions_vacancy_id", "agent_sessions", ["vacancy_id"])

    op.create_table(
        "agent_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_session_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", operation_status, nullable=False),
        sa.Column("output_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_session_id"], ["agent_sessions.id"]),
        sa.UniqueConstraint(
            "agent_session_id",
            "purpose",
            "idempotency_key",
            name="uq_agent_operation_key",
        ),
    )
    op.create_index(
        "ix_agent_operations_agent_session_id",
        "agent_operations",
        ["agent_session_id"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("prompt_id", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["operation_id"], ["agent_operations.id"]),
        sa.UniqueConstraint(
            "operation_id", "attempt", name="uq_agent_run_operation_attempt"
        ),
    )
    op.create_index("ix_agent_runs_operation_id", "agent_runs", ["operation_id"])

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_session_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_session_id"], ["agent_sessions.id"]),
        sa.ForeignKeyConstraint(["operation_id"], ["agent_operations.id"]),
        sa.UniqueConstraint("operation_id", name="uq_agent_artifact_operation"),
        sa.UniqueConstraint(
            "agent_session_id",
            "kind",
            "content_hash",
            name="uq_agent_artifact_content",
        ),
    )
    op.create_index(
        "ix_agent_artifacts_agent_session_id",
        "agent_artifacts",
        ["agent_session_id"],
    )
    op.create_index("ix_agent_artifacts_operation_id", "agent_artifacts", ["operation_id"])
    op.create_index("ix_agent_artifacts_kind", "agent_artifacts", ["kind"])

    op.create_table(
        "ranking_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("compatibility_key", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"]),
        sa.UniqueConstraint(
            "vacancy_id", "input_hash", name="uq_ranking_snapshot_input"
        ),
    )
    op.create_index("ix_ranking_snapshots_vacancy_id", "ranking_snapshots", ["vacancy_id"])
    op.create_index(
        "ix_ranking_snapshots_compatibility_key",
        "ranking_snapshots",
        ["compatibility_key"],
    )

    op.create_table(
        "ranking_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("agent_session_id", sa.Uuid(), nullable=False),
        sa.Column("profile_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("overall_value", sa.Float(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("tie_break_key", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["ranking_snapshots.id"]),
        sa.ForeignKeyConstraint(["agent_session_id"], ["agent_sessions.id"]),
        sa.ForeignKeyConstraint(["profile_artifact_id"], ["agent_artifacts.id"]),
        sa.UniqueConstraint("snapshot_id", "rank", name="uq_ranking_entry_rank"),
        sa.UniqueConstraint(
            "snapshot_id", "agent_session_id", name="uq_ranking_entry_session"
        ),
    )
    op.create_index("ix_ranking_entries_snapshot_id", "ranking_entries", ["snapshot_id"])
    op.create_index(
        "ix_ranking_entries_agent_session_id",
        "ranking_entries",
        ["agent_session_id"],
    )
    op.create_index(
        "ix_ranking_entries_profile_artifact_id",
        "ranking_entries",
        ["profile_artifact_id"],
    )

    op.create_table(
        "restriction_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("decision_type", restriction_type, nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["invitation_id"], ["interview_invitations.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["restriction_decisions.id"]),
        sa.UniqueConstraint(
            "supersedes_id", name="uq_restriction_superseded_once"
        ),
    )
    op.create_index(
        "ix_restriction_decisions_invitation_id",
        "restriction_decisions",
        ["invitation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_restriction_decisions_invitation_id",
        table_name="restriction_decisions",
    )
    op.drop_table("restriction_decisions")
    op.drop_index("ix_ranking_entries_profile_artifact_id", table_name="ranking_entries")
    op.drop_index("ix_ranking_entries_agent_session_id", table_name="ranking_entries")
    op.drop_index("ix_ranking_entries_snapshot_id", table_name="ranking_entries")
    op.drop_table("ranking_entries")
    op.drop_index("ix_ranking_snapshots_compatibility_key", table_name="ranking_snapshots")
    op.drop_index("ix_ranking_snapshots_vacancy_id", table_name="ranking_snapshots")
    op.drop_table("ranking_snapshots")
    op.drop_index("ix_agent_artifacts_kind", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_operation_id", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_agent_session_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index("ix_agent_runs_operation_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_operations_agent_session_id", table_name="agent_operations")
    op.drop_table("agent_operations")
    op.drop_index("ix_agent_sessions_vacancy_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_invitation_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="restrictiontype").drop(bind, checkfirst=True)
        sa.Enum(name="agentrunstatus").drop(bind, checkfirst=True)
        sa.Enum(name="agentoperationstatus").drop(bind, checkfirst=True)
        sa.Enum(name="agentsessionstatus").drop(bind, checkfirst=True)
