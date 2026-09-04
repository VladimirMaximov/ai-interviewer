from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.application.ranking_services import DecisionService
from interview_platform.application.services import InterviewService
from interview_platform.domain.errors import ValidationError
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


class DecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "decisions.sqlite3"
        self.interview_repository = SQLiteInterviewRepository(path)
        self.hiring_repository = SQLiteHiringRepository(path)
        self.interviews = InterviewService(self.interview_repository, TextCaptureStub())
        self.created = self.interviews.create_interview(
            candidate_alias="synthetic-decision",
            position_title="Backend",
            questions=[{"prompt": "Explain", "required": True}],
            invitation_token="decision-token-value-00000000000001",
        )
        self.service = DecisionService(self.hiring_repository, self.interviews)

    def tearDown(self) -> None:
        self.hiring_repository.close()
        self.interview_repository.close()
        self.directory.cleanup()

    def test_decisions_are_append_only_and_separate_by_role(self) -> None:
        interview_id = self.created.interview.id
        recruiter = self.service.create_decision(
            interview_id,
            actor_id="recruiter-1",
            actor_role="recruiter",
            decision="advance",
            reason="Relevant experience",
            idempotency_key="decision-recruiter-1",
        )
        manager = self.service.create_decision(
            interview_id,
            actor_id="manager-1",
            actor_role="hiring_manager",
            decision="hold",
            reason="Need another example",
            idempotency_key="decision-manager-1",
        )
        replacement = self.service.create_decision(
            interview_id,
            actor_id="manager-1",
            actor_role="hiring_manager",
            decision="advance",
            reason="Example reviewed",
            supersedes_decision_id=manager["id"],
            idempotency_key="decision-manager-2",
        )

        history = self.service.list_decisions(interview_id)
        self.assertEqual(3, len(history))
        self.assertEqual(recruiter["id"], history[0]["id"])
        self.assertEqual(manager["id"], replacement["supersedes_decision_id"])

    def test_system_cannot_create_hiring_decision(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create_decision(
                self.created.interview.id,
                actor_id="system",
                actor_role="system",
                decision="reject",
                reason="Automated result",
                idempotency_key="decision-system-1",
            )


if __name__ == "__main__":
    unittest.main()
