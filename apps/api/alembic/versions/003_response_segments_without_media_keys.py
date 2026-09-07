"""Store new answers as time intervals in the continuous recording.

Revision ID: 003_response_segments
Revises: 002_continuous_recording
"""

from alembic import op
import sqlalchemy as sa


revision = "003_response_segments"
down_revision = "002_continuous_recording"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.alter_column("storage_key", existing_type=sa.String(length=512), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.alter_column("storage_key", existing_type=sa.String(length=512), nullable=False)
