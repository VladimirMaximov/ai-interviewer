"""Merge platform and candidate-interview migration branches.

Revision ID: 009_merge_platform_branches
Revises: 003_vacancy_resume_context, 008_invitation_question_input
"""


revision = "009_merge_platform_branches"
down_revision = ("003_vacancy_resume_context", "008_invitation_question_input")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
