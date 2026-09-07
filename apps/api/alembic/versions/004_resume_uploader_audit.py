"""Record whether a candidate or recruiter uploaded each resume version.

Revision ID: 004_resume_uploader_audit
Revises: 003_vacancy_resume_context
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "004_resume_uploader_audit"
down_revision = "003_vacancy_resume_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("candidate_resumes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "uploaded_by_role",
                sa.String(length=20),
                nullable=False,
                server_default="candidate",
            )
        )
        batch_op.add_column(
            sa.Column(
                "uploaded_by_actor_id",
                sa.String(length=120),
                nullable=True,
            )
        )

    with op.batch_alter_table("candidate_resumes") as batch_op:
        batch_op.create_check_constraint(
            "ck_candidate_resume_uploader_role",
            "uploaded_by_role IN ('candidate', 'recruiter')",
        )
        batch_op.create_check_constraint(
            "ck_candidate_resume_uploader_actor",
            "(uploaded_by_role = 'candidate' AND uploaded_by_actor_id IS NULL) OR "
            "(uploaded_by_role = 'recruiter' AND uploaded_by_actor_id IS NOT NULL)",
        )
        batch_op.alter_column("uploaded_by_role", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("candidate_resumes") as batch_op:
        batch_op.drop_constraint(
            "ck_candidate_resume_uploader_actor", type_="check"
        )
        batch_op.drop_constraint(
            "ck_candidate_resume_uploader_role", type_="check"
        )
        batch_op.drop_column("uploaded_by_actor_id")
        batch_op.drop_column("uploaded_by_role")
