"""Persist bounded runtime evaluation jobs.

Revision ID: 010_runtime_evaluation_jobs
Revises: 009_merge_platform_branches
"""

from alembic import op
import sqlalchemy as sa

revision = "010_runtime_evaluation_jobs"
down_revision = "009_merge_platform_branches"
branch_labels = None
depends_on = None

def upgrade() -> None:
    status = sa.Enum("pending", "completed", "failed", name="runtimeevaluationstatus")
    op.create_table("runtime_evaluation_jobs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("response_id", sa.Uuid(), nullable=False), sa.Column("status", status, nullable=False), sa.Column("question_text", sa.Text(), nullable=False), sa.Column("answer_text", sa.Text(), nullable=False), sa.Column("confidence", sa.String(32)), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["response_id"], ["candidate_responses.id"]), sa.UniqueConstraint("response_id"))
    op.create_index("ix_runtime_evaluation_jobs_response_id", "runtime_evaluation_jobs", ["response_id"])

def downgrade() -> None:
    op.drop_index("ix_runtime_evaluation_jobs_response_id", table_name="runtime_evaluation_jobs")
    op.drop_table("runtime_evaluation_jobs")
    sa.Enum(name="runtimeevaluationstatus").drop(op.get_bind(), checkfirst=True)
