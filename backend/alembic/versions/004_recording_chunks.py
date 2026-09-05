"""Persist streamed recording chunks instead of one end-of-interview object.

Revision ID: 004_recording_chunks
Revises: 003_response_segments
"""

from alembic import op
import sqlalchemy as sa


revision = "004_recording_chunks"
down_revision = "003_response_segments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_recording_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recording_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("start_offset_ms", sa.Integer(), nullable=False),
        sa.Column("end_offset_ms", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(128)),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["recording_id"], ["interview_recordings.id"]),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("recording_id", "sequence", name="uq_recording_chunk_sequence"),
    )
    op.create_index("ix_interview_recording_chunks_recording_id", "interview_recording_chunks", ["recording_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_recording_chunks_recording_id", table_name="interview_recording_chunks")
    op.drop_table("interview_recording_chunks")
