"""Add vacancy uploads, matched candidate resumes, and context lineage.

Revision ID: 003_vacancy_resume_context
Revises: 002_manager_brief
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "003_vacancy_resume_context"
down_revision = "002_manager_brief"
branch_labels = None
depends_on = None


def upgrade() -> None:
    vacancy_status = sa.Enum("active", "closed", name="vacancystatus")
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", vacancy_status, nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_vacancy_creator_idempotency_key",
        ),
    )

    with op.batch_alter_table("interview_invitations") as batch_op:
        batch_op.add_column(sa.Column("vacancy_id", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column("candidate_alias", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("created_by", sa.String(length=120), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_interview_invitation_vacancy",
            "vacancies",
            ["vacancy_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_interview_invitations_vacancy_id", ["vacancy_id"]
        )

    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "candidate_resumes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["interview_invitations.id"],
        ),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"]),
        sa.UniqueConstraint(
            "invitation_id",
            "version",
            name="uq_candidate_resume_version",
        ),
        sa.UniqueConstraint(
            "invitation_id",
            "idempotency_key",
            name="uq_candidate_resume_idempotency_key",
        ),
    )
    op.create_index(
        "ix_candidate_resumes_invitation_id",
        "candidate_resumes",
        ["invitation_id"],
    )
    op.create_index(
        "ix_candidate_resumes_vacancy_id",
        "candidate_resumes",
        ["vacancy_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_resumes_vacancy_id", table_name="candidate_resumes"
    )
    op.drop_index(
        "ix_candidate_resumes_invitation_id", table_name="candidate_resumes"
    )
    op.drop_table("candidate_resumes")

    with op.batch_alter_table("candidate_responses") as batch_op:
        batch_op.drop_column("created_at")

    with op.batch_alter_table("interview_invitations") as batch_op:
        batch_op.drop_index("ix_interview_invitations_vacancy_id")
        batch_op.drop_constraint(
            "fk_interview_invitation_vacancy", type_="foreignkey"
        )
        batch_op.drop_column("created_by")
        batch_op.drop_column("candidate_alias")
        batch_op.drop_column("vacancy_id")

    op.drop_table("vacancies")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="vacancystatus").drop(bind, checkfirst=True)
