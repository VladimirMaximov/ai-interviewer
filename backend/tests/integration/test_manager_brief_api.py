import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.manager import get_manager_brief_service, require_manager
from app.domain.manager_brief import (
    AgentFieldProposal,
    FieldKey,
    FieldOrigin,
    ManagerBriefAgentResult,
)
from app.main import app
from app.models.interview import Base
from app.services.manager_brief import ManagerBriefService


class ApiAgent:
    model_id = "api-stub"
    model_version = "1"
    prompt_id = "manager-brief-v1"

    def draft(
        self, *, vacancy_id: str, fragments: list[dict]
    ) -> ManagerBriefAgentResult:
        return ManagerBriefAgentResult(
            schema_version="manager_brief_v1",
            purpose="manager_brief_draft",
            fields=[
                AgentFieldProposal(
                    field_key=FieldKey.ROLE,
                    value="Python-разработчик",
                    origin=FieldOrigin.MANAGER_SOURCE,
                    source_fragment_ids=[fragments[0]["id"]],
                    source_quotes=["Python-разработчик"],
                    confidence=0.99,
                )
            ],
            unresolved_fields=[],
        )


class ManagerBriefApiTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(engine, expire_on_commit=False)()
        self.service = ManagerBriefService(self.db, ApiAgent())
        app.dependency_overrides[get_manager_brief_service] = lambda: self.service
        app.dependency_overrides[require_manager] = lambda: "manager-api-test"
        self.client = TestClient(app)
        self.vacancy_id = uuid4()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()

    def test_manager_can_generate_edit_and_approve_form(self) -> None:
        created = self.client.post(
            f"/manager/vacancies/{self.vacancy_id}/brief-drafts",
            headers={"Idempotency-Key": "api-brief-001"},
            json={"source_text": "Ищем Python-разработчика"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        draft = created.json()
        self.assertEqual(draft["fields"][0]["field_key"], "role")

        updated = self.client.patch(
            f"/manager/vacancies/{self.vacancy_id}/brief-drafts/{draft['id']}",
            json={
                "expected_revision": draft["revision"],
                "updates": [
                    {
                        "field_key": "seniority",
                        "value": "middle",
                        "confirmation_status": "confirmed",
                    }
                ],
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)

        approved = self.client.post(
            f"/manager/vacancies/{self.vacancy_id}/brief-drafts/{draft['id']}/approve",
            json={
                "expected_revision": updated.json()["revision"],
                "confirm_no_automatic_rejection": True,
            },
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "approved")

        context = self.client.get(
            f"/manager/vacancies/{self.vacancy_id}/approved-brief-context"
        )
        self.assertEqual(context.status_code, 200, context.text)
        self.assertNotIn("source_text", context.json())

    def test_stale_revision_has_conflict_status(self) -> None:
        draft = self.client.post(
            f"/manager/vacancies/{self.vacancy_id}/brief-drafts",
            headers={"Idempotency-Key": "api-brief-002"},
            json={"source_text": "Ищем Python-разработчика"},
        ).json()
        response = self.client.patch(
            f"/manager/vacancies/{self.vacancy_id}/brief-drafts/{draft['id']}",
            json={"expected_revision": draft["revision"] + 1, "updates": []},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "revision_conflict")


if __name__ == "__main__":
    unittest.main()
