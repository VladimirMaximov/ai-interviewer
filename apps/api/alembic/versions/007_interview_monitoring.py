"""Add evidence-first camera events and adaptive voice-profile state.

Revision ID: 007_interview_monitoring
Revises: 006_candidate_feedback_agent
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "007_interview_monitoring"
down_revision = "006_candidate_feedback_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    event_kind = sa.Enum(
        "face_missing",
        "multiple_faces",
        "face_detection_unavailable",
        "overlapping_speech",
        "additional_speaker",
        "speaker_mismatch",
        name="monitoringeventkind",
    )
    review_status = sa.Enum(
        "pending", "confirmed", "dismissed", name="monitoringreviewstatus"
    )
    profile_status = sa.Enum(
        "collecting", "ready", "not_ready", name="voiceprofilestatus"
    )

    op.create_table(
        "interview_monitoring_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("response_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("kind", event_kind, nullable=False),
        sa.Column("started_at_ms", sa.Integer(), nullable=False),
        sa.Column("ended_at_ms", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("detector_name", sa.String(length=120), nullable=False),
        sa.Column("detector_version", sa.String(length=80), nullable=False),
        sa.Column("evidence_storage_key", sa.String(length=512), nullable=True),
        sa.Column("evidence_content_type", sa.String(length=128), nullable=True),
        sa.Column("evidence_checksum", sa.String(length=128), nullable=True),
        sa.Column("review_status", review_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "started_at_ms >= 0 AND ended_at_ms > started_at_ms",
            name="ck_monitoring_event_interval",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(["response_id"], ["candidate_responses.id"]),
        sa.UniqueConstraint("evidence_storage_key"),
    )
    op.create_index(
        "ix_interview_monitoring_events_session_id",
        "interview_monitoring_events",
        ["session_id"],
    )
    op.create_index(
        "ix_interview_monitoring_events_response_id",
        "interview_monitoring_events",
        ["response_id"],
    )
    op.create_index(
        "ix_interview_monitoring_events_question_id",
        "interview_monitoring_events",
        ["question_id"],
    )

    op.create_table(
        "interview_voice_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("first_response_id", sa.Uuid(), nullable=True),
        sa.Column("second_response_id", sa.Uuid(), nullable=True),
        sa.Column("status", profile_status, nullable=False),
        sa.Column("reason_code", sa.String(length=120), nullable=True),
        sa.Column("detector_name", sa.String(length=120), nullable=False),
        sa.Column("detector_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"]),
        sa.ForeignKeyConstraint(
            ["first_response_id"], ["candidate_responses.id"]
        ),
        sa.ForeignKeyConstraint(
            ["second_response_id"], ["candidate_responses.id"]
        ),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(
        "ix_interview_voice_profiles_session_id",
        "interview_voice_profiles",
        ["session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_voice_profiles_session_id",
        table_name="interview_voice_profiles",
    )
    op.drop_table("interview_voice_profiles")
    op.drop_index(
        "ix_interview_monitoring_events_question_id",
        table_name="interview_monitoring_events",
    )
    op.drop_index(
        "ix_interview_monitoring_events_response_id",
        table_name="interview_monitoring_events",
    )
    op.drop_index(
        "ix_interview_monitoring_events_session_id",
        table_name="interview_monitoring_events",
    )
    op.drop_table("interview_monitoring_events")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="voiceprofilestatus").drop(bind, checkfirst=True)
        sa.Enum(name="monitoringreviewstatus").drop(bind, checkfirst=True)
        sa.Enum(name="monitoringeventkind").drop(bind, checkfirst=True)
