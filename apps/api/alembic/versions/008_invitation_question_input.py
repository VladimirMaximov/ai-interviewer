"""Persist the server-owned question input and follow-up flags.

Revision ID: 008_invitation_question_input
Revises: 007_recording_duration
"""

from alembic import op
import sqlalchemy as sa


revision = "008_invitation_question_input"
down_revision = "007_recording_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_invitations", sa.Column("question_config", sa.JSON(), nullable=True))
    op.add_column("interview_invitations", sa.Column("follow_up_after_all_answers", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("interview_invitations", "follow_up_after_all_answers")
    op.drop_column("interview_invitations", "question_config")
