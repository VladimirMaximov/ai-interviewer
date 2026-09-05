"""Persist the media-derived duration of each completed recording.

Revision ID: 007_recording_duration
Revises: 006_follow_up_questions
"""

from alembic import op
import sqlalchemy as sa


revision = "007_recording_duration"
down_revision = "006_follow_up_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_recordings", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_recordings", "duration_ms")
