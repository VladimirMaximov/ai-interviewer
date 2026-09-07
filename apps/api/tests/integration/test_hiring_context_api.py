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


class UnusedStorage:
    """Consent and resume endpoints do not touch interview audio storage."""


class HiringContextApiTests(unittest.TestCase):
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
        app.dependency_overrides[require_recruiter] = lambda: "recruiter-api-test"
        self.candidate_db = self.sessions()
        self.candidate_workflow = SqlCandidateWorkflow(
            self.candidate_db, UnusedStorage()
        )
        app.dependency_overrides[get_workflow] = lambda: self.candidate_workflow
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.candidate_db.close()
        self.engine.dispose()

    def test_vacancy_invitation_resume_and_context_journey(self) -> None:
        vacancy_response = self.client.post(
            "/recruiter/vacancies",
            content="Python, FastAPI, PostgreSQL",
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "X-Vacancy-Title": "Backend developer",
                "X-Document-Filename": "vacancy.txt",
                "Idempotency-Key": "vacancy-api-001",
            },
        )
        self.assertEqual(vacancy_response.status_code, 201, vacancy_response.text)
        vacancy_id = vacancy_response.json()["id"]

        invitation_response = self.client.post(
            f"/recruiter/vacancies/{vacancy_id}/invitations",
            json={
                "candidate_alias": "synthetic-candidate",
                "expires_in_hours": 24,
            },
        )
        self.assertEqual(
            invitation_response.status_code, 201, invitation_response.text
        )
        invitation = invitation_response.json()

        candidate_view = self.client.get(
            f"/candidate/{invitation['candidate_token']}"
        )
        self.assertEqual(candidate_view.status_code, 200, candidate_view.text)
        self.assertEqual(candidate_view.json()["vacancy_id"], vacancy_id)
        self.assertEqual(
            candidate_view.json()["vacancy_title"], "Backend developer"
        )
        consent = self.client.post(
            f"/candidate/{invitation['candidate_token']}/consent"
        )
        self.assertEqual(consent.status_code, 200, consent.text)
        self.assertTrue(consent.json()["consented"])

        resume_response = self.client.post(
            f"/candidate/{invitation['candidate_token']}/resume",
            content="Five years of Python experience",
            headers={
                "Content-Type": "text/plain",
                "X-Document-Filename": "resume.txt",
                "Idempotency-Key": "resume-api-001",
            },
        )
        self.assertEqual(resume_response.status_code, 201, resume_response.text)
        self.assertEqual(resume_response.json()["vacancy_id"], vacancy_id)
        self.assertEqual(resume_response.json()["uploaded_by_role"], "candidate")
        refreshed_view = self.client.get(
            f"/candidate/{invitation['candidate_token']}"
        )
        self.assertTrue(refreshed_view.json()["resume_uploaded"])

        applications = self.client.get(
            f"/recruiter/vacancies/{vacancy_id}/applications"
        )
        self.assertEqual(applications.status_code, 200, applications.text)
        self.assertEqual(len(applications.json()["applications"]), 1)
        self.assertNotIn(
            invitation["candidate_token"], applications.text
        )

        context = self.client.get(
            f"/recruiter/vacancies/{vacancy_id}/applications/"
            f"{invitation['invitation_id']}/agent-context"
        )
        self.assertEqual(context.status_code, 200, context.text)
        payload = context.json()
        self.assertEqual(payload["vacancy"]["source_kind"], "vacancy")
        self.assertEqual(payload["resume"]["source_kind"], "resume")
        self.assertTrue(payload["policy"]["interview_scores_require_answer_evidence"])

    def test_resume_requires_consent_and_bad_document_is_rejected(self) -> None:
        vacancy = self.client.post(
            "/recruiter/vacancies",
            content="Python",
            headers={
                "Content-Type": "text/plain",
                "X-Vacancy-Title": "Developer",
                "X-Document-Filename": "vacancy.txt",
                "Idempotency-Key": "vacancy-api-002",
            },
        ).json()
        invitation = self.client.post(
            f"/recruiter/vacancies/{vacancy['id']}/invitations",
            json={},
        ).json()

        no_consent = self.client.post(
            f"/candidate/{invitation['candidate_token']}/resume",
            content="Candidate resume",
            headers={
                "Content-Type": "text/plain",
                "X-Document-Filename": "resume.txt",
                "Idempotency-Key": "resume-api-002",
            },
        )
        self.assertEqual(no_consent.status_code, 409)
        self.assertEqual(
            no_consent.json()["error"]["code"], "candidate_consent_required"
        )

        recruiter_upload = self.client.post(
            f"/recruiter/vacancies/{vacancy['id']}/applications/"
            f"{invitation['invitation_id']}/resume",
            content="Resume supplied by recruiter",
            headers={
                "Content-Type": "text/plain",
                "X-Document-Filename": "resume.txt",
                "Idempotency-Key": "recruiter-resume-api-001",
            },
        )
        self.assertEqual(recruiter_upload.status_code, 201, recruiter_upload.text)
        self.assertEqual(
            recruiter_upload.json()["uploaded_by_role"], "recruiter"
        )
        self.assertEqual(recruiter_upload.json()["version"], 1)

        mismatched_vacancy = self.client.post(
            f"/recruiter/vacancies/{uuid4()}/applications/"
            f"{invitation['invitation_id']}/resume",
            content="Wrong vacancy",
            headers={
                "Content-Type": "text/plain",
                "X-Document-Filename": "resume.txt",
                "Idempotency-Key": "recruiter-resume-api-002",
            },
        )
        self.assertEqual(mismatched_vacancy.status_code, 404)

        unsupported = self.client.post(
            "/recruiter/vacancies",
            content=b"binary",
            headers={
                "Content-Type": "application/octet-stream",
                "X-Vacancy-Title": "Broken",
                "X-Document-Filename": "vacancy.exe",
                "Idempotency-Key": "vacancy-api-003",
            },
        )
        self.assertEqual(unsupported.status_code, 422)
        self.assertEqual(
            unsupported.json()["error"]["code"], "unsupported_document_type"
        )


if __name__ == "__main__":
    unittest.main()
