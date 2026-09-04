from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
import app.models.multi_agent  # noqa: F401
from app.api.hiring_context import require_recruiter
from app.api.multi_agent import get_multi_agent_harness
from app.config import settings
from app.domain.hiring_context import VacancyStatus
from app.domain.multi_agent import (
    AgentPurpose,
    AlternativeVacancyMatchOutput,
    AnswerAssessmentOutput,
    CandidateFeedbackOutput,
    IntegrityCheckOutput,
    QuestionPlanOutput,
    ResumeRelevanceOutput,
)
from app.main import app
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    Base,
    CandidateResponse,
    InterviewInvitation,
    InterviewSession,
    InvitationStatus,
    TranscriptionStatus,
)
from app.services.multi_agent_harness import MultiAgentHarness
from app.security.invitations import digest_invitation_secret


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


class ApiAgent:
    model_id = "test-llm"
    model_version = "test-llm-v1"

    def __init__(self, purpose):
        self.purpose = purpose
        self.prompt_id = f"{purpose.value}-api-test"

    def run(self, context):
        if self.purpose is AgentPurpose.RESUME_RELEVANCE:
            evidence_id = context["resume_evidence_catalog"][0]["evidence_id"]
            requirement = next(
                item
                for item in context["requirement_catalog"]
                if "Python" in item["text"]
            )
            return ResumeRelevanceOutput(
                positions=[
                    {
                        "position_id": "position-backend",
                        "employer": None,
                        "role": "backend",
                        "period": None,
                        "project": None,
                        "responsibilities": [],
                        "skills": ["Python"],
                        "achievements": [],
                        "evidence_ids": [evidence_id],
                    }
                ],
                claims=[
                    {
                        "claim_id": "python-claim",
                        "claim_type": "skill",
                        "subject": "Python",
                        "evidence_ids": [evidence_id],
                        "verification_status": "unverified",
                    }
                ],
                experience_matches=[
                    {
                        "experience_label": "Backend",
                        "evidence_ids": [evidence_id],
                        "requirement_id": requirement["requirement_id"],
                        "requirement_origin": requirement["origin"],
                        "relevance": 1,
                        "confidence": 0.9,
                        "explanation": "Совпадение Python.",
                        "position_ids": ["position-backend"],
                        "claim_ids": ["python-claim"],
                    }
                ],
                gaps=[],
            )
        if self.purpose is AgentPurpose.QUESTION_PLAN:
            return QuestionPlanOutput(questions=context["baseline_questions"])
        if self.purpose is AgentPurpose.ANSWER_ASSESSMENT:
            evidence_id = context["answer_evidence_catalog"][0]["evidence_id"]
            return AnswerAssessmentOutput(
                response_id=context["response_id"],
                question_id=context["question_id"],
                observations=[
                    {
                        "criterion_id": criterion["criterion_id"],
                        "dimension": criterion["dimension"],
                        "label": "strong",
                        "value": 1,
                        "confidence": 0.9,
                        "explanation": "Есть конкретный пример.",
                        "evidence": [
                            {"kind": "supporting", "evidence_id": evidence_id}
                        ],
                    }
                    for criterion in context["question"]["criteria"]
                ],
            )
        if self.purpose is AgentPurpose.ALTERNATIVE_VACANCY_MATCH:
            reference = context["candidate_evidence"][0]["evidence_reference"]
            return AlternativeVacancyMatchOutput(
                target_vacancy_id=context["target_vacancy"]["id"],
                candidate_grade="middle",
                target_grade="middle",
                compatibility_status="compatible",
                fit_value=0.8,
                matched_criteria=[
                    context["candidate_evidence"][0]["criterion_id"]
                ],
                matched_terms=["Python"],
                gaps=[],
                evidence_references=[reference],
                explanation="Python подходит альтернативной вакансии.",
            )
        if self.purpose is AgentPurpose.INTEGRITY_CHECK:
            return IntegrityCheckOutput(observations=[], is_restriction=False)
        if self.purpose is AgentPurpose.CANDIDATE_FEEDBACK:
            reference = next(
                item["evidence_reference"]
                for item in context["evidence_catalog"]
                if item["source"] == "answer_assessment"
            )
            allowed = context["allowed_alternative_vacancies"][0]
            return CandidateFeedbackOutput(
                source_profile_artifact_id=context["source_profile_artifact_id"],
                headline="Python backend опыт подтверждён",
                summary="Вы привели применимый технический пример.",
                strengths=[
                    {
                        "title": "Python",
                        "detail": "Вы описали личную реализацию сервиса.",
                        "evidence_references": [reference],
                    }
                ],
                growth_areas=[
                    {
                        "title": "Метрики",
                        "detail": "Результат не был выражен в цифрах.",
                        "action": "Добавьте показатели до и после изменения.",
                        "evidence_references": [reference],
                    }
                ],
                experience_alignment=[
                    {
                        "title": "Python",
                        "detail": "Навык подтверждён ответом.",
                        "status": "confirmed",
                        "evidence_references": [reference],
                    }
                ],
                alternative_vacancy={
                    "vacancy_id": allowed["vacancy_id"],
                    "title": allowed["title"],
                    "matched_areas": allowed["matched_areas"],
                    "message": "Можно рассмотреть эту активную вакансию.",
                    "is_automatic_transfer": False,
                },
                next_steps=["Подготовьте пример с измеримым результатом."],
                limitations=["Оценивались только ответы этого интервью."],
                is_hiring_decision=False,
            )
        raise AssertionError("unexpected agent purpose")


class MultiAgentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.harness = MultiAgentHarness(
            self.db,
            {purpose: ApiAgent(purpose) for purpose in AgentPurpose},
            strong_pool_min_coverage=0.2,
        )
        app.dependency_overrides[get_multi_agent_harness] = lambda: self.harness
        app.dependency_overrides[require_recruiter] = lambda: "recruiter-api-test"
        self.client = TestClient(app)
        self.vacancy = self._vacancy("Backend", "Python PostgreSQL")
        self.alternative = self._vacancy("Platform", "Python services")
        self.candidate_secret = "synthetic-candidate-secret"
        self.invitation = InterviewInvitation(
            token_digest=digest_invitation_secret(self.candidate_secret),
            vacancy_id=self.vacancy.id,
            candidate_alias="synthetic-candidate",
            created_by="recruiter-api-test",
            expires_at=NOW + timedelta(days=1),
            status=InvitationStatus.ACTIVE,
        )
        self.db.add(self.invitation)
        self.db.flush()
        self.resume = CandidateResume(
            invitation_id=self.invitation.id,
            vacancy_id=self.vacancy.id,
            version=1,
            source_filename="resume.txt",
            media_type="text/plain",
            byte_size=20,
            extracted_text="Python backend work",
            content_hash="r" * 64,
            idempotency_key="resume-api-001",
            uploaded_by_role="recruiter",
            uploaded_by_actor_id="recruiter-api-test",
            created_at=NOW,
        )
        self.interview = InterviewSession(
            invitation_id=self.invitation.id,
            consented_at=NOW,
        )
        self.db.add_all([self.resume, self.interview])
        self.db.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _vacancy(self, title, text):
        vacancy = Vacancy(
            title=title,
            source_filename="vacancy.txt",
            media_type="text/plain",
            byte_size=len(text),
            extracted_text=text,
            content_hash=uuid4().hex + uuid4().hex,
            status=VacancyStatus.ACTIVE,
            created_by="recruiter-api-test",
            idempotency_key=f"vacancy-{uuid4()}",
            created_at=NOW,
        )
        self.db.add(vacancy)
        self.db.commit()
        self.db.refresh(vacancy)
        return vacancy

    @property
    def base(self):
        return (
            f"/recruiter/vacancies/{self.vacancy.id}/applications/"
            f"{self.invitation.id}/agent-session"
        )

    def test_full_recruiter_agent_journey_and_restriction_history(self) -> None:
        created = self.client.post(
            self.base,
            headers={"Idempotency-Key": "agent-session-api-001"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        replay = self.client.post(
            self.base,
            headers={"Idempotency-Key": "agent-session-api-001"},
        )
        self.assertEqual(created.json()["id"], replay.json()["id"])

        resume = self.client.post(
            f"{self.base}/resume-analysis",
            headers={"Idempotency-Key": "resume-analysis-api-001"},
        )
        self.assertEqual(resume.status_code, 200, resume.text)
        self.assertEqual(resume.json()["kind"], "resume_relevance")
        plan = self.client.post(
            f"{self.base}/question-plan",
            headers={"Idempotency-Key": "question-plan-api-001"},
        )
        self.assertEqual(plan.status_code, 200, plan.text)
        question_id = plan.json()["payload"]["questions"][0]["question_id"]
        candidate_plan = self.client.get(
            f"/candidate/{self.candidate_secret}/questions"
        )
        self.assertEqual(candidate_plan.status_code, 200, candidate_plan.text)
        self.assertEqual(
            candidate_plan.json()["questions"][0]["question_id"], question_id
        )
        self.assertNotIn("criteria", candidate_plan.text)
        self.assertNotIn("selection_reason", candidate_plan.text)
        response = CandidateResponse(
            session_id=self.interview.id,
            question_id=UUID(question_id),
            storage_key=f"responses/{uuid4()}.webm",
            content_type="audio/webm",
            checksum="d" * 64,
            transcription_status=TranscriptionStatus.COMPLETED,
            transcript_text=(
                "Я лично реализовал Python сервис и измерил результат."
            ),
            created_at=NOW,
        )
        self.db.add(response)
        self.db.commit()
        assessment = self.client.post(
            f"{self.base}/answer-assessments",
            headers={"Idempotency-Key": "answer-assessment-api-001"},
            json={"response_id": str(response.id)},
        )
        self.assertEqual(assessment.status_code, 200, assessment.text)

        final = self.client.post(
            f"{self.base}/finalize",
            headers={"Idempotency-Key": "finalize-profile-api-001"},
        )
        self.assertEqual(final.status_code, 200, final.text)
        payload = final.json()
        self.assertFalse(payload["profile"]["payload"]["is_hiring_decision"])
        self.assertEqual(len(payload["alternative_matches"]), 1)

        pending_feedback = self.client.get(
            f"/candidate/{self.candidate_secret}/feedback"
        )
        self.assertEqual(pending_feedback.status_code, 200)
        self.assertEqual(pending_feedback.json()["status"], "pending_review")
        draft = self.client.post(
            f"{self.base}/candidate-feedback",
            headers={"Idempotency-Key": "candidate-feedback-api-001"},
        )
        self.assertEqual(draft.status_code, 201, draft.text)
        self.assertEqual(draft.json()["status"], "draft")
        still_pending = self.client.get(
            f"/candidate/{self.candidate_secret}/feedback"
        )
        self.assertIsNone(still_pending.json()["feedback"])

        published = self.client.post(
            f"{self.base}/candidate-feedback/{draft.json()['id']}/publish"
        )
        self.assertEqual(published.status_code, 200, published.text)
        candidate_feedback = self.client.get(
            f"/candidate/{self.candidate_secret}/feedback"
        )
        self.assertEqual(candidate_feedback.status_code, 200)
        self.assertEqual(candidate_feedback.json()["status"], "published")
        self.assertEqual(
            candidate_feedback.json()["feedback"]["score"]["value"], 10
        )
        self.assertEqual(
            candidate_feedback.json()["feedback"]["alternative_vacancy"]["title"],
            self.alternative.title,
        )
        for staff_only in (
            "evidence_references",
            "candidate_pool",
            "integrity",
            "blacklist",
        ):
            self.assertNotIn(staff_only, candidate_feedback.text.casefold())

        ranking = self.client.get(f"/recruiter/vacancies/{self.vacancy.id}/ranking")
        self.assertEqual(ranking.status_code, 200, ranking.text)
        self.assertEqual(ranking.json()["entries"][0]["rank"], 1)

        restriction = self.client.post(
            f"/recruiter/applications/{self.invitation.id}/restrictions",
            json={
                "decision_type": "restricted",
                "reason": "Human-reviewed synthetic evidence.",
                "evidence_references": [assessment.json()["id"]],
            },
        )
        self.assertEqual(restriction.status_code, 201, restriction.text)
        self.assertEqual(restriction.json()["created_by"], "recruiter-api-test")
        history = self.client.get(
            f"/recruiter/applications/{self.invitation.id}/restrictions"
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()["decisions"]), 1)
        ranking_after = self.client.get(
            f"/recruiter/vacancies/{self.vacancy.id}/ranking"
        )
        self.assertEqual(ranking_after.json()["entries"], [])

    def test_scoped_session_and_precondition_errors_are_structured(self) -> None:
        missing = self.client.get(
            f"/recruiter/vacancies/{self.vacancy.id}/applications/"
            f"{uuid4()}/agent-session"
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "multi_agent_not_found")

        self.client.post(
            self.base,
            headers={"Idempotency-Key": "agent-session-api-002"},
        )
        early = self.client.post(
            f"{self.base}/question-plan",
            headers={"Idempotency-Key": "question-plan-api-002"},
        )
        self.assertEqual(early.status_code, 409)
        self.assertEqual(early.json()["error"]["code"], "multi_agent_conflict")

    def test_restriction_history_requires_recruiter_authentication(self) -> None:
        original_key = settings.recruiter_key
        app.dependency_overrides.pop(require_recruiter)
        settings.recruiter_key = "synthetic-recruiter-key"
        try:
            path = f"/recruiter/applications/{self.invitation.id}/restrictions"
            unauthorized = self.client.get(path)
            self.assertEqual(unauthorized.status_code, 401)
            authorized = self.client.get(
                path,
                headers={"X-Recruiter-Key": "synthetic-recruiter-key"},
            )
            self.assertEqual(authorized.status_code, 200, authorized.text)
        finally:
            settings.recruiter_key = original_key
            app.dependency_overrides[require_recruiter] = (
                lambda: "recruiter-api-test"
            )


if __name__ == "__main__":
    unittest.main()
