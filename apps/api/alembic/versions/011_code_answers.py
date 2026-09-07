"""Persist live-coding source snapshots linked to recording offsets.

Revision ID: 011_code_answers
Revises: 010_runtime_evaluation_jobs
"""

from alembic import op
import sqlalchemy as sa

revision = "011_code_answers"
down_revision = "010_runtime_evaluation_jobs"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("code_answers", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("response_id", sa.Uuid(), nullable=False), sa.Column("language", sa.String(64), nullable=False), sa.Column("source_code", sa.Text(), nullable=False), sa.Column("start_offset_ms", sa.Integer(), nullable=False), sa.Column("end_offset_ms", sa.Integer(), nullable=False), sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["response_id"], ["candidate_responses.id"]), sa.UniqueConstraint("response_id"))
    op.create_index("ix_code_answers_response_id", "code_answers", ["response_id"])

def downgrade() -> None:
    op.drop_index("ix_code_answers_response_id", table_name="code_answers")
    op.drop_table("code_answers")
