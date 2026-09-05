"""Add durable presenter and processing job metadata."""

from alembic import op
import sqlalchemy as sa


revision = "017_integrated_runtime"
down_revision = "016_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vacancies") as batch:
        batch.add_column(sa.Column("interview_config", sa.JSON()))
        batch.add_column(
            sa.Column(
                "interview_config_revision",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
    with op.batch_alter_table("question_avatar_assets") as batch:
        batch.drop_constraint("uq_avatar_question", type_="unique")
        batch.add_column(sa.Column("content_hash", sa.String(64)))
        batch.add_column(sa.Column("question_text_snapshot", sa.Text()))
        batch.add_column(sa.Column("voice_id", sa.String(120)))
        batch.add_column(sa.Column("tts_version", sa.String(120)))
        batch.add_column(sa.Column("portrait_version", sa.String(120)))
        batch.add_column(sa.Column("renderer_version", sa.String(120)))
        batch.add_column(sa.Column("failure_stage", sa.String(40)))
        batch.add_column(sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("ready_at", sa.DateTime(timezone=True)))
        batch.create_unique_constraint(
            "uq_presenter_asset_content",
            ["invitation_id", "question_id", "content_hash"],
        )
        batch.create_index("ix_question_avatar_assets_content_hash", ["content_hash"])

    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(120)),
        sa.UniqueConstraint("idempotency_key", name="uq_processing_job_idempotency"),
    )
    op.create_index("ix_processing_jobs_entity_id", "processing_jobs", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_entity_id", table_name="processing_jobs")
    op.drop_table("processing_jobs")
    with op.batch_alter_table("question_avatar_assets") as batch:
        batch.drop_index("ix_question_avatar_assets_content_hash")
        batch.drop_constraint("uq_presenter_asset_content", type_="unique")
        batch.drop_column("ready_at")
        batch.drop_column("updated_at")
        batch.drop_column("attempt_count")
        batch.drop_column("failure_stage")
        batch.drop_column("renderer_version")
        batch.drop_column("portrait_version")
        batch.drop_column("tts_version")
        batch.drop_column("voice_id")
        batch.drop_column("question_text_snapshot")
        batch.drop_column("content_hash")
        batch.create_unique_constraint(
            "uq_avatar_question", ["invitation_id", "question_id"]
        )
    with op.batch_alter_table("vacancies") as batch:
        batch.drop_column("interview_config_revision")
        batch.drop_column("interview_config")
