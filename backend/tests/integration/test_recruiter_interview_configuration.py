import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
from app.api.hiring_context import get_hiring_context_service, require_recruiter
from app.main import app
from app.models.interview import Base, InterviewInvitation
from app.services.hiring_context import HiringContextService


def three_blocks() -> dict:
    def block(key: str, title: str, *, coding: bool = False) -> dict:
        return {
            "id": str(uuid4()),
            "key": key,
            "title": title,
            "topic": key,
            "questions": [
                {
                    "id": str(uuid4()),
                    "text": f"Synthetic {title} question",
                    "kind": "coding" if coding else "spoken",
                    "language": "python" if coding else None,
                    "follow_up_after_answer": True,
                    "time_limit_seconds": 120,
                }
            ],
        }

    return {
        "schema_version": 1,
        "live_coding_enabled": True,
        "blocks": [
            block("hard_skills", "Hard skills", coding=True),
            block("soft_skills", "Soft skills"),
            block("work_experience", "Experience"),
        ],
    }


class RecruiterInterviewConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        app.dependency_overrides[get_hiring_context_service] = (
            lambda: HiringContextService(self.sessions())
        )
        app.dependency_overrides[require_recruiter] = lambda: "synthetic-recruiter"
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.engine.dispose()

    def create_vacancy(self) -> str:
        response = self.client.post(
            "/recruiter/vacancies",
            content="Synthetic Python role",
            headers={
                "Content-Type": "text/plain",
                "X-Vacancy-Title": "Synthetic developer",
                "X-Document-Filename": "vacancy.txt",
                "Idempotency-Key": "integrated-vacancy-001",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def test_configuration_is_copied_into_invitation_snapshot(self) -> None:
        vacancy_id = self.create_vacancy()
        configuration = three_blocks()
        saved = self.client.put(
            f"/recruiter/vacancies/{vacancy_id}/interview-configuration",
            json=configuration,
        )
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(len(saved.json()["blocks"]), 3)
        invitation_response = self.client.post(
            f"/recruiter/vacancies/{vacancy_id}/invitations",
            json={"candidate_alias": "synthetic"},
        )
        self.assertEqual(invitation_response.status_code, 201)
        self.assertIn("?token=", invitation_response.json()["candidate_url"])

        configuration["blocks"][0]["questions"][0]["text"] = "Edited later"
        self.client.put(
            f"/recruiter/vacancies/{vacancy_id}/interview-configuration",
            json=configuration,
        )
        with self.sessions() as db:
            invitation = db.scalar(select(InterviewInvitation))
            self.assertEqual(
                invitation.question_config["blocks"][0]["questions"][0]["text"],
                "Synthetic Hard skills question",
            )

    def test_malformed_block_order_is_rejected(self) -> None:
        vacancy_id = self.create_vacancy()
        configuration = three_blocks()
        configuration["blocks"].reverse()
        response = self.client.put(
            f"/recruiter/vacancies/{vacancy_id}/interview-configuration",
            json=configuration,
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
