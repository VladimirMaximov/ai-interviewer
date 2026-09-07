"""Persistence boundary for role assignment and human reviews."""

from __future__ import annotations

from typing import Protocol

from interview_platform.domain.roles import ManagerReview, RecruiterReview


class RoleReviewRepository(Protocol):
    def get_recruiter_review(self, interview_id: str) -> RecruiterReview | None: ...

    def save_recruiter_review(self, review: RecruiterReview) -> None: ...

    def assigned_interview_ids(self, manager_id: str) -> list[str]: ...

    def get_manager_review(self, interview_id: str) -> ManagerReview | None: ...

    def save_manager_review(self, review: ManagerReview) -> None: ...

    def clear_manager_review(self, interview_id: str) -> None: ...
