"""Add one continuous interview recording and its immutable timeline.

Revision ID: 002_continuous_recording
Revises: 001_interview_core
"""
from alembic import op
import sqlalchemy as sa

revision = "002_continuous_recording"
down_revision = "001_interview_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    event_type = sa.Enum("recording_started", "question_shown", "answer_saved", "next_question_clicked", "interview_submitted", name="timelineeventtype")
    op.create_table("interview_recordings", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("session_id", sa.Uuid(), nullable=False), sa.Column("storage_key", sa.String(512), nullable=False), sa.Column("content_type", sa.String(128), nullable=False), sa.Column("checksum", sa.String(128)), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]), sa.UniqueConstraint("session_id"), sa.UniqueConstraint("storage_key"))
    op.create_table("interview_timeline_events", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("session_id", sa.Uuid(), nullable=False), sa.Column("question_id", sa.Uuid()), sa.Column("event_type", event_type, nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("recording_offset_ms", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]))
    op.create_index("ix_interview_timeline_events_session_id", "interview_timeline_events", ["session_id"])
    op.add_column("candidate_responses", sa.Column("start_offset_ms", sa.Integer()))
    op.add_column("candidate_responses", sa.Column("end_offset_ms", sa.Integer()))


def downgrade() -> None:
    op.drop_column("candidate_responses", "end_offset_ms"); op.drop_column("candidate_responses", "start_offset_ms")
    op.drop_index("ix_interview_timeline_events_session_id", table_name="interview_timeline_events"); op.drop_table("interview_timeline_events"); op.drop_table("interview_recordings")
