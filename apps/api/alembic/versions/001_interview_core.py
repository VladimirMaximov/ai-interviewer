"""Create the minimal invitation, session, and recorded-response tables.

Revision ID: 001_interview_core
Revises:
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa

revision = "001_interview_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    invitation_status = sa.Enum("active", "revoked", "submitted", name="invitationstatus")
    transcription_status = sa.Enum("pending", "processing", "completed", "failed", name="transcriptionstatus")
    op.create_table(
        "interview_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", invitation_status, nullable=False),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_interview_invitations_token_digest", "interview_invitations", ["token_digest"])
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["invitation_id"], ["interview_invitations.id"]),
        sa.UniqueConstraint("invitation_id"),
    )
    op.create_table(
        "candidate_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("transcription_status", transcription_status, nullable=False),
        sa.Column("transcript_text", sa.Text()),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_candidate_responses_question_id", "candidate_responses", ["question_id"])
    op.create_index("ix_candidate_responses_session_id", "candidate_responses", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_candidate_responses_session_id", table_name="candidate_responses")
    op.drop_index("ix_candidate_responses_question_id", table_name="candidate_responses")
    op.drop_table("candidate_responses")
    op.drop_table("interview_sessions")
    op.drop_index("ix_interview_invitations_token_digest", table_name="interview_invitations")
    op.drop_table("interview_invitations")
