"""Add human-published candidate feedback releases.

Revision ID: 006_candidate_feedback_agent
Revises: 005_multi_agent_harness
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "006_candidate_feedback_agent"
down_revision = "005_multi_agent_harness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    release_status = sa.Enum(
        "draft", "published", name="feedbackreleasestatus"
    )
    op.create_table(
        "candidate_feedback_releases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_session_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("status", release_status, nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(length=120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["interview_invitations.id"]
        ),
        sa.ForeignKeyConstraint(["agent_session_id"], ["agent_sessions.id"]),
        sa.ForeignKeyConstraint(
            ["feedback_artifact_id"], ["agent_artifacts.id"]
        ),
        sa.UniqueConstraint(
            "feedback_artifact_id",
            name="uq_candidate_feedback_release_artifact",
        ),
    )
    op.create_index(
        "ix_candidate_feedback_releases_invitation_id",
        "candidate_feedback_releases",
        ["invitation_id"],
    )
    op.create_index(
        "ix_candidate_feedback_releases_agent_session_id",
        "candidate_feedback_releases",
        ["agent_session_id"],
    )
    op.create_index(
        "ix_candidate_feedback_releases_feedback_artifact_id",
        "candidate_feedback_releases",
        ["feedback_artifact_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_feedback_releases_feedback_artifact_id",
        table_name="candidate_feedback_releases",
    )
    op.drop_index(
        "ix_candidate_feedback_releases_agent_session_id",
        table_name="candidate_feedback_releases",
    )
    op.drop_index(
        "ix_candidate_feedback_releases_invitation_id",
        table_name="candidate_feedback_releases",
    )
    op.drop_table("candidate_feedback_releases")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="feedbackreleasestatus").drop(bind, checkfirst=True)
