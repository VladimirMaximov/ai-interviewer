"""Record answers closed by a question time limit."""
from alembic import op
import sqlalchemy as sa
revision = "013_response_timeout"
down_revision = "012_runtime_evaluation_evidence"
branch_labels = None
depends_on = None
def upgrade() -> None:
    # A default is needed while adding a non-nullable column to an existing
    # table.  ``batch_alter_table`` also makes the follow-up alteration work
    # under SQLite, used by the integration suite (SQLite has no ALTER COLUMN).
    op.add_column(
        "candidate_responses",
        sa.Column("timed_out", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.alter_column(
            "timed_out",
            existing_type=sa.Boolean(),
            server_default=None,
        )
def downgrade() -> None:
    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.drop_column("timed_out")
