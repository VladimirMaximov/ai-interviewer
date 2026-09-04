from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from interview_platform.application.services import InterviewService, token_digest
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 3, 12, 0, tzinfo=UTC)


class SequentialIds:
    def __init__(self) -> None:
        self.value = 0

    def new_id(self) -> str:
        self.value += 1
        return f"id-{self.value}"


class RepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "interviews.sqlite3"
        self.repository = SQLiteInterviewRepository(self.path)
        self.service = InterviewService(
            self.repository,
            TextCaptureStub(),
            clock=FixedClock(),
            identifiers=SequentialIds(),
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_round_trip_preserves_questions_answers_and_state(self) -> None:
        token = "repository-test-token-value-0000001"
        created = self.service.create_interview(
            candidate_alias="synthetic-repository",
            position_title="Developer",
            questions=[{"prompt": "Question?", "required": True}],
            invitation_token=token,
        )
        question_id = created.interview.questions[0].id
        self.service.start_interview(token, consent=True)
        self.service.save_answer(token, question_id=question_id, content="Persistent answer")
        self.service.complete_interview(token)

        reloaded = self.repository.get_by_id(created.interview.id)

        self.assertIsNotNone(reloaded)
        self.assertEqual("submitted", reloaded.status.value)
        self.assertEqual("Persistent answer", reloaded.answers[question_id].content)

    def test_raw_invitation_token_is_not_persisted(self) -> None:
        token = "secret-raw-invitation-token-000001"
        self.service.create_interview(
            candidate_alias="synthetic-secret",
            position_title="Developer",
            questions=[{"prompt": "Question?", "required": True}],
            invitation_token=token,
        )

        database_bytes = self.path.read_bytes()

        self.assertNotIn(token.encode("utf-8"), database_bytes)
        self.assertIsNotNone(self.repository.get_by_token_digest(token_digest(token)))

    def test_database_can_be_reopened(self) -> None:
        created = self.service.create_interview(
            candidate_alias="synthetic-reopen",
            position_title="Developer",
            questions=[{"prompt": "Question?", "required": True}],
            invitation_token="reopen-invitation-token-value-00001",
        )
        self.repository.close()
        self.repository = SQLiteInterviewRepository(self.path)

        self.assertEqual("synthetic-reopen", self.repository.get_by_id(created.interview.id).candidate_alias)


if __name__ == "__main__":
    unittest.main()
