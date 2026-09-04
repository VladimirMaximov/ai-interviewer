from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from interview_platform.application.role_services import RoleService
from interview_platform.application.services import InterviewService
from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.sqlite_role_repository import SQLiteRoleReviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 3, 14, 0, tzinfo=UTC)

    def now(self) -> datetime:
        current = self.value
        self.value += timedelta(minutes=1)
        return current


class SequentialIds:
    def __init__(self) -> None:
        self.value = 0

    def new_id(self) -> str:
        self.value += 1
        return f"role-id-{self.value}"


class RoleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "roles.sqlite3"
        self.interview_repository = SQLiteInterviewRepository(database)
        self.role_repository = SQLiteRoleReviewRepository(database)
        self.interviews = InterviewService(
            self.interview_repository,
            TextCaptureStub(),
            clock=MutableClock(),
            identifiers=SequentialIds(),
        )
        self.roles = RoleService(
            self.interviews,
            self.role_repository,
            clock=MutableClock(),
            identifiers=SequentialIds(),
        )
        self.token = "role-service-invitation-token-000001"
        self.created = self.interviews.create_interview(
            candidate_alias="synthetic-role-test",
            position_title="Backend Developer",
            questions=[{"prompt": "Explain a storage decision", "required": True}],
            invitation_token=self.token,
        )
        self.question_id = self.created.interview.questions[0].id

    def tearDown(self) -> None:
        self.role_repository.close()
        self.interview_repository.close()
        self.directory.cleanup()

    def submit(self) -> None:
        self.interviews.start_interview(self.token, consent=True)
        self.interviews.save_answer(
            self.token,
            question_id=self.question_id,
            content="I selected PostgreSQL after comparing consistency and latency.",
        )
        self.interviews.complete_interview(self.token)

    def review_data(
        self, *, manager: str = "manager-a", publish: bool = False
    ) -> dict:
        return {
            "candidate_summary": "Explains an evidence-backed trade-off.",
            "strengths": ["Compares consistency and latency"],
            "risks": ["No migration example"],
            "next_steps": "Discuss a production migration.",
            "internal_notes": "Recruiter context only.",
            "recruiter_decision": "advance",
            "assigned_manager": manager,
            "evidence": [
                {
                    "kind": "answer_excerpt",
                    "question_id": self.question_id,
                    "excerpt": "consistency and latency",
                    "note": "Exact evidence from the submitted answer.",
                }
            ],
            "publish": publish,
        }

    def test_manager_sees_only_recruiter_assignment(self) -> None:
        self.submit()
        self.roles.save_recruiter_review(
            self.created.interview.id, **self.review_data(manager="manager-a")
        )

        self.assertEqual(
            [self.created.interview.id],
            [item.id for item in self.roles.list_for_manager("manager-a")],
        )
        self.assertEqual([], self.roles.list_for_manager("manager-b"))
        with self.assertRaises(NotFoundError):
            self.roles.get_for_manager(self.created.interview.id, "manager-b")

    def test_recruiter_and_manager_decisions_remain_independent(self) -> None:
        self.submit()
        recruiter_review = self.roles.save_recruiter_review(
            self.created.interview.id, **self.review_data()
        )
        manager_review = self.roles.save_manager_review(
            self.created.interview.id,
            "manager-a",
            manager_decision="hold",
            notes="Need deeper system-design evidence.",
        )

        stored_recruiter = self.role_repository.get_recruiter_review(
            self.created.interview.id
        )
        stored_manager = self.role_repository.get_manager_review(
            self.created.interview.id
        )
        self.assertEqual("advance", recruiter_review.recruiter_decision.value)
        self.assertEqual("hold", manager_review.manager_decision.value)
        self.assertEqual("advance", stored_recruiter.recruiter_decision.value)
        self.assertEqual("hold", stored_manager.manager_decision.value)

    def test_candidate_sees_only_published_safe_fields(self) -> None:
        self.submit()
        draft = self.review_data(publish=False)
        self.roles.save_recruiter_review(self.created.interview.id, **draft)
        self.assertIsNone(self.roles.candidate_feedback(self.token))

        published = self.review_data(publish=True)
        self.roles.save_recruiter_review(self.created.interview.id, **published)
        feedback = self.roles.candidate_feedback(self.token)
        self.assertEqual(
            {
                "candidate_summary",
                "strengths",
                "next_steps",
                "published_at",
                "version",
            },
            set(feedback),
        )
        self.assertNotIn("Recruiter context only.", str(feedback))

    def test_reassignment_revokes_access_and_clears_stale_manager_review(self) -> None:
        self.submit()
        self.roles.save_recruiter_review(
            self.created.interview.id, **self.review_data(manager="manager-a")
        )
        self.roles.save_manager_review(
            self.created.interview.id,
            "manager-a",
            manager_decision="advance",
            notes="Proceed.",
        )
        self.roles.save_recruiter_review(
            self.created.interview.id, **self.review_data(manager="manager-b")
        )

        with self.assertRaises(NotFoundError):
            self.roles.get_for_manager(self.created.interview.id, "manager-a")
        self.assertIsNone(
            self.roles.manager_review(self.created.interview.id, "manager-b")
        )

    def test_review_requires_submitted_interview_and_exact_evidence(self) -> None:
        with self.assertRaises(ConflictError):
            self.roles.save_recruiter_review(
                self.created.interview.id, **self.review_data()
            )
        self.submit()
        invalid = self.review_data()
        invalid["evidence"][0]["excerpt"] = "invented excerpt"
        with self.assertRaises(ValidationError):
            self.roles.save_recruiter_review(self.created.interview.id, **invalid)


if __name__ == "__main__":
    unittest.main()
