"""Persist both voice and source-code evidence for runtime evaluation.

Revision ID: 012_runtime_evaluation_evidence
Revises: 011_code_answers
"""

from alembic import op
import sqlalchemy as sa


revision = "012_runtime_evaluation_evidence"
down_revision = "011_code_answers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runtime_evaluation_jobs", sa.Column("spoken_text", sa.Text(), nullable=True))
    op.add_column("runtime_evaluation_jobs", sa.Column("source_code", sa.Text(), nullable=True))
    op.add_column("runtime_evaluation_jobs", sa.Column("language", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("runtime_evaluation_jobs", "language")
    op.drop_column("runtime_evaluation_jobs", "source_code")
    op.drop_column("runtime_evaluation_jobs", "spoken_text")
