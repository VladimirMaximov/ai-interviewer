"""Persist asynchronous optional clarification questions.

Revision ID: 006_follow_up_questions
Revises: 005_candidate_activity_events
"""

from alembic import op
import sqlalchemy as sa


revision = "006_follow_up_questions"
down_revision = "005_candidate_activity_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status = sa.Enum("pending", "ready", "presented", "answered", "skipped", "failed", name="followupstatus")
    op.create_table(
        "interview_follow_up_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("source_response_id", sa.Uuid()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("transcript_snapshot", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("presented_at", sa.DateTime(timezone=True)),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["source_response_id"], ["candidate_responses.id"]),
    )
    op.create_index("ix_interview_follow_up_questions_session_id", "interview_follow_up_questions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_follow_up_questions_session_id", table_name="interview_follow_up_questions")
    op.drop_table("interview_follow_up_questions")
    sa.Enum(name="followupstatus").drop(op.get_bind(), checkfirst=True)
