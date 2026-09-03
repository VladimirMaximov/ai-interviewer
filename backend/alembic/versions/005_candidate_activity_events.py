"""Add transparent candidate activity event values.

Revision ID: 005_candidate_activity_events
Revises: 004_recording_chunks
"""

from alembic import op


revision = "005_candidate_activity_events"
down_revision = "004_recording_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("page_hidden", "page_visible", "window_blurred", "window_focused", "page_copy"):
        op.execute(f"ALTER TYPE timelineeventtype ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # PostgreSQL enums cannot safely remove values in place.
    pass
