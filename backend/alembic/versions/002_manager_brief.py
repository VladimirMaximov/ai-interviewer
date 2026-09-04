"""Add agent-generated manager briefs and immutable run lineage.

Revision ID: 002_manager_brief
Revises: 001_interview_core
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "002_manager_brief"
down_revision = "001_interview_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    operation_status = sa.Enum(
        "running",
        "succeeded",
        "failed",
        name="managerbriefoperationstatus",
    )
    run_status = sa.Enum(
        "running",
        "succeeded",
        "invalid_output",
        "provider_failed",
        name="managerbriefagentrunstatus",
    )
    brief_status = sa.Enum(
        "draft",
        "validation_failed",
        "approved",
        "superseded",
        name="managerbriefstatus",
    )

    op.create_table(
        "manager_brief_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", operation_status, nullable=False),
        sa.Column("output_draft_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "vacancy_id",
            "idempotency_key",
            name="uq_manager_brief_operation_key",
        ),
    )
    op.create_index(
        "ix_manager_brief_operations_vacancy_id",
        "manager_brief_operations",
        ["vacancy_id"],
    )

    op.create_table(
        "manager_brief_agent_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", run_status, nullable=False),
        sa.Column("model_id", sa.String(length=120), nullable=False),
        sa.Column("model_version", sa.String(length=120), nullable=False),
        sa.Column("prompt_id", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("output_hash", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["manager_brief_operations.id"],
        ),
        sa.UniqueConstraint(
            "operation_id",
            "attempt",
            name="uq_manager_brief_agent_attempt",
        ),
    )
    op.create_index(
        "ix_manager_brief_agent_runs_operation_id",
        "manager_brief_agent_runs",
        ["operation_id"],
    )

    op.create_table(
        "manager_brief_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", brief_status, nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_fragments", sa.JSON(), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("unresolved_fields", sa.JSON(), nullable=False),
        sa.Column("validation_issues", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["manager_brief_agent_runs.id"],
        ),
        sa.UniqueConstraint(
            "vacancy_id",
            "version",
            name="uq_manager_brief_draft_version",
        ),
    )
    op.create_index(
        "ix_manager_brief_drafts_vacancy_id",
        "manager_brief_drafts",
        ["vacancy_id"],
    )
    op.create_index(
        "ix_manager_brief_drafts_agent_run_id",
        "manager_brief_drafts",
        ["agent_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manager_brief_drafts_agent_run_id",
        table_name="manager_brief_drafts",
    )
    op.drop_index(
        "ix_manager_brief_drafts_vacancy_id",
        table_name="manager_brief_drafts",
    )
    op.drop_table("manager_brief_drafts")
    op.drop_index(
        "ix_manager_brief_agent_runs_operation_id",
        table_name="manager_brief_agent_runs",
    )
    op.drop_table("manager_brief_agent_runs")
    op.drop_index(
        "ix_manager_brief_operations_vacancy_id",
        table_name="manager_brief_operations",
    )
    op.drop_table("manager_brief_operations")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="managerbriefstatus").drop(bind, checkfirst=True)
        sa.Enum(name="managerbriefagentrunstatus").drop(bind, checkfirst=True)
        sa.Enum(name="managerbriefoperationstatus").drop(bind, checkfirst=True)
