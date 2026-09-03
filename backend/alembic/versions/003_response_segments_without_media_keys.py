"""Store new answers as time intervals in the continuous recording.

Revision ID: 003_response_segments
Revises: 002_continuous_recording
"""

from alembic import op


revision = "003_response_segments"
down_revision = "002_continuous_recording"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("candidate_responses", "storage_key", nullable=True)


def downgrade() -> None:
    op.alter_column("candidate_responses", "storage_key", nullable=False)
