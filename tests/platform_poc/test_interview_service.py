from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from interview_platform.application.services import InterviewService
from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
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
        return f"service-id-{self.value}"


class InterviewServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteInterviewRepository(Path(self.directory.name) / "service.sqlite3")
        self.service = InterviewService(
            self.repository,
            TextCaptureStub(),
            clock=MutableClock(),
            identifiers=SequentialIds(),
        )
        self.token = "service-invitation-token-value-000001"
        self.created = self.service.create_interview(
            candidate_alias="synthetic-service",
            position_title="Python Developer",
            questions=[
                {"prompt": "Explain a decision", "required": True},
                {"prompt": "Optional context", "required": False},
            ],
            invitation_token=self.token,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _submit(self) -> str:
        question_id = self.created.interview.questions[0].id
        self.service.start_interview(self.token, consent=True)
        self.service.save_answer(
            self.token,
            question_id=question_id,
            content="I compared latency and consistency before choosing PostgreSQL.",
        )
        self.service.complete_interview(self.token)
        return question_id

    def _feedback(self, question_id: str, *, publish: bool, summary: str = "Clear reasoning"):
        return self.service.save_feedback(
            self.created.interview.id,
            candidate_summary=summary,
            strengths=["Names trade-offs"],
            risks=["Limited scale evidence"],
            next_steps="Discuss production incidents.",
            internal_notes="Manager-only note",
            manager_decision="advance",
            evidence=[
                {
                    "kind": "answer_excerpt",
                    "question_id": question_id,
                    "excerpt": "latency and consistency",
                    "note": "Supports architecture reasoning",
                }
            ],
            publish=publish,
        )

    def test_candidate_can_resume_and_submit_only_after_required_answers(self) -> None:
        started = self.service.start_interview(self.token, consent=True)
        resumed = self.service.start_interview(self.token, consent=True)
        self.assertEqual(started.started_at, resumed.started_at)

        with self.assertRaises(ConflictError):
            self.service.complete_interview(self.token)

        question_id = self.created.interview.questions[0].id
        saved = self.service.save_answer(self.token, question_id=question_id, content="My answer")
        completed = self.service.complete_interview(self.token)
        self.assertEqual("text_stub", saved.answers[question_id].capture_kind)
        self.assertEqual("submitted", completed.status.value)

    def test_invalid_token_has_generic_not_found_error(self) -> None:
        with self.assertRaises(NotFoundError) as context:
            self.service.get_candidate_interview("not-a-real-token")
        self.assertEqual("interview not found", context.exception.message)

    def test_draft_feedback_does_not_change_submitted_status(self) -> None:
        question_id = self._submit()
        interview = self._feedback(question_id, publish=False)

        self.assertEqual("submitted", interview.status.value)
        self.assertEqual("draft", interview.feedback.publication_status.value)
        self.assertIsNone(interview.feedback.ai_recommendation)
        self.assertIsNone(interview.feedback.recruiter_decision)

    def test_publication_moves_to_reviewed_and_increments_versions(self) -> None:
        question_id = self._submit()
        first = self._feedback(question_id, publish=False)
        second = self._feedback(question_id, publish=True, summary="Published reasoning")
        third = self._feedback(question_id, publish=True, summary="Updated published reasoning")

        self.assertEqual(1, first.feedback.version)
        self.assertEqual(2, second.feedback.version)
        self.assertEqual(3, third.feedback.version)
        self.assertEqual("reviewed", third.status.value)
        self.assertIsNotNone(third.feedback.published_at)

    def test_feedback_rejects_invented_excerpt(self) -> None:
        question_id = self._submit()
        with self.assertRaises(ValidationError):
            self.service.save_feedback(
                self.created.interview.id,
                candidate_summary="Summary",
                strengths=[],
                risks=[],
                next_steps="Next",
                internal_notes="",
                manager_decision="hold",
                evidence=[
                    {
                        "kind": "answer_excerpt",
                        "question_id": question_id,
                        "excerpt": "invented words",
                        "note": "Invalid evidence",
                    }
                ],
                publish=True,
            )


if __name__ == "__main__":
    unittest.main()
