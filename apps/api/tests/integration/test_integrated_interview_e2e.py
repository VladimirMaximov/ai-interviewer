import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
from app.api.candidate import get_workflow
from app.api.hiring_context import get_hiring_context_service, require_recruiter
from app.main import app
from app.models.interview import Base
from app.services.candidate_workflow import SqlCandidateWorkflow
from app.services.hiring_context import HiringContextService


class NoMediaStorage:
    pass


class IntegratedInterviewE2ETests(unittest.TestCase):
    def test_cabinet_snapshot_is_the_candidate_question_plan(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        candidate_db = sessions()
        app.dependency_overrides[get_hiring_context_service] = (
            lambda: HiringContextService(sessions())
        )
        app.dependency_overrides[require_recruiter] = lambda: "synthetic-recruiter"
        app.dependency_overrides[get_workflow] = lambda: SqlCandidateWorkflow(
            candidate_db, NoMediaStorage()
        )
        client = TestClient(app)
        try:
            vacancy = client.post(
                "/recruiter/vacancies",
                content="Synthetic role",
                headers={
                    "Content-Type": "text/plain",
                    "X-Vacancy-Title": "Synthetic role",
                    "X-Document-Filename": "vacancy.txt",
                    "Idempotency-Key": "integrated-e2e-vacancy",
                },
            ).json()
            expected_texts = ["Hard question", "Soft question", "Experience question"]
            keys = ["hard_skills", "soft_skills", "work_experience"]
            blocks = []
            for key, text in zip(keys, expected_texts):
                blocks.append({
                    "id": str(uuid4()), "key": key, "title": key,
                    "topic": key, "questions": [{
                        "id": str(uuid4()), "text": text, "kind": "spoken",
                    }],
                })
            saved = client.put(
                f"/recruiter/vacancies/{vacancy['id']}/interview-configuration",
                json={"schema_version": 1, "blocks": blocks},
            )
            self.assertEqual(saved.status_code, 200, saved.text)
            invitation = client.post(
                f"/recruiter/vacancies/{vacancy['id']}/invitations", json={}
            ).json()
            candidate = client.get(f"/candidate/{invitation['candidate_token']}")
            self.assertEqual(candidate.status_code, 200, candidate.text)
            self.assertEqual(
                [question["text"] for question in candidate.json()["questions"]],
                expected_texts,
            )
            consent = client.post(
                f"/candidate/{invitation['candidate_token']}/consent"
            )
            self.assertEqual(consent.status_code, 200, consent.text)
            self.assertTrue(consent.json()["consented"])
        finally:
            app.dependency_overrides.clear()
            candidate_db.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
