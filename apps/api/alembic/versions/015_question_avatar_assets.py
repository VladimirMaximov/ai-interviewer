"""Store private pre-rendered avatar assets per question."""
from alembic import op
import sqlalchemy as sa

revision = "015_question_avatar_assets"
down_revision = "014_merge_agent_interview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_avatar_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), sa.ForeignKey("interview_invitations.id"), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("renderer", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("audio_storage_key", sa.String(512)),
        sa.Column("video_storage_key", sa.String(512), unique=True),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invitation_id", "question_id", name="uq_avatar_question"),
    )
    op.create_index("ix_question_avatar_assets_invitation_id", "question_avatar_assets", ["invitation_id"])
    op.create_index("ix_question_avatar_assets_question_id", "question_avatar_assets", ["question_id"])


def downgrade() -> None:
    op.drop_table("question_avatar_assets")
