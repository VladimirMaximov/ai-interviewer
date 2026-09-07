from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit
from wsgiref.util import setup_testing_defaults

from interview_platform.application.assessment_services import AssessmentService
from interview_platform.application.feedback_services import FeedbackService
from interview_platform.application.hiring_services import HiringServices
from interview_platform.application.ranking_services import DecisionService, RankingService
from interview_platform.application.services import InterviewService
from interview_platform.application.vacancy_services import VacancyService
from interview_platform.domain.competencies import load_framework
from interview_platform.infrastructure.evaluation_stubs import DeterministicEvidenceEvaluator
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub
from interview_platform.web.app import create_app


ROOT = Path(__file__).resolve().parents[2]


class VacancyAssessmentAPITests(unittest.TestCase):
    manager_key = "vacancy-api-test-secret"

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "api.sqlite3"
        self.interview_repository = SQLiteInterviewRepository(path)
        self.hiring_repository = SQLiteHiringRepository(path)
        self.capture = TextCaptureStub()
        self.interviews = InterviewService(self.interview_repository, self.capture)
        vacancies = VacancyService(
            self.hiring_repository,
            load_framework(
                ROOT
                / "prototypes/interview-platform/interview_platform/data/competency_framework.v1.json"
            ),
            interview_service=self.interviews,
        )
        hiring = HiringServices(
            vacancies=vacancies,
            assessments=AssessmentService(
                self.hiring_repository,
                self.interviews,
                DeterministicEvidenceEvaluator(),
            ),
            rankings=RankingService(self.hiring_repository, self.interviews),
            decisions=DecisionService(self.hiring_repository, self.interviews),
            feedback=FeedbackService(self.hiring_repository, self.interviews),
        )
        self.app = create_app(
            self.interviews,
            self.capture,
            manager_key=self.manager_key,
            hiring=hiring,
        )

    def tearDown(self) -> None:
        self.hiring_repository.close()
        self.interview_repository.close()
        self.directory.cleanup()

    def request(
        self,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        body: bytes | None = None,
        content_type: str | None = None,
        manager: bool = False,
        idempotency_key: str | None = None,
    ) -> tuple[int, dict]:
        environ: dict = {}
        setup_testing_defaults(environ)
        parsed = urlsplit(path)
        environ.update(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": parsed.path,
                "QUERY_STRING": parsed.query,
                "HTTP_HOST": "testserver",
                "wsgi.url_scheme": "http",
            }
        )
        if data is not None:
            body = json.dumps(data).encode()
            content_type = "application/json"
        body = body or b""
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input"] = io.BytesIO(body)
        if content_type:
            environ["CONTENT_TYPE"] = content_type
        if manager:
            environ["HTTP_X_MANAGER_KEY"] = self.manager_key
            environ["HTTP_X_ACTOR_ID"] = "manager-api-test"
        if idempotency_key:
            environ["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split()[0])

        response = b"".join(self.app(environ, start_response))
        return captured["status"], json.loads(response) if response else {}

    def test_author_assess_rank_decide_and_publish_candidate_safe_feedback(self) -> None:
        status, framework = self.request(
            "GET",
            "/api/manager/competency-frameworks/current?role_key=software_engineer&level_key=middle",
            manager=True,
        )
        self.assertEqual(200, status)
        self.assertEqual("software_engineer", framework["role_profiles"][0]["role_key"])

        status, vacancy = self.request(
            "POST",
            "/api/manager/vacancies",
            manager=True,
            data={
                "title": "Python API Developer",
                "role_key": "software_engineer",
                "target_level_key": "middle",
                "owner_actor_id": "manager-api-test",
            },
        )
        self.assertEqual(201, status)
        vacancy_id = vacancy["id"]
        status, source = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/context-sources",
            manager=True,
            data={
                "source_type": "phrase",
                "display_name": "Hiring manager brief",
                "text": "Нужен опыт безопасной эволюции API с проверяемым результатом.",
            },
        )
        self.assertEqual(201, status)

        boundary = "vacancy-test-boundary"
        multipart = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="expectations.md"\r\n'
            "Content-Type: text/markdown\r\n\r\n"
            "Опыт проектирования наблюдаемых фоновых задач.\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        status, file_source = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/context-sources",
            manager=True,
            body=multipart,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        self.assertEqual(201, status)
        self.assertEqual("file", file_source["source_type"])

        status, profile = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/profile-drafts",
            manager=True,
            idempotency_key="draft-profile-001",
            data={"context_source_ids": [source["id"], file_source["id"]]},
        )
        self.assertEqual(201, status)
        _, repeated_profile = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/profile-drafts",
            manager=True,
            idempotency_key="draft-profile-001",
            data={"context_source_ids": [source["id"], file_source["id"]]},
        )
        self.assertEqual(profile["id"], repeated_profile["id"])
        status, profile = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/profile-versions/{profile['id']}/approve",
            manager=True,
            idempotency_key="approve-profile-001",
            data={"confirm_no_automatic_rejection": True},
        )
        self.assertEqual(200, status)
        self.assertEqual("approved", profile["status"])

        status, snapshot = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/assessment-contexts",
            manager=True,
            idempotency_key="assessment-context-001",
            data={"vacancy_profile_version_id": profile["id"]},
        )
        self.assertEqual(201, status)
        _, repeated_snapshot = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/assessment-contexts",
            manager=True,
            idempotency_key="assessment-context-001",
            data={"vacancy_profile_version_id": profile["id"]},
        )
        self.assertEqual(snapshot["id"], repeated_snapshot["id"])
        status, invitation = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/interviews",
            manager=True,
            data={
                "candidate_alias": "synthetic-api-candidate",
                "assessment_context_snapshot_id": snapshot["id"],
            },
        )
        self.assertEqual(201, status)
        token = invitation["invitation_token"]
        interview_id = invitation["interview_id"]

        candidate_path = f"/api/candidate/interviews/{token}"
        self.request("POST", candidate_path + "/start", data={"consent": True})
        _, candidate = self.request("GET", candidate_path)
        for question in candidate["questions"]:
            self.request(
                "PUT",
                candidate_path + f"/answers/{question['id']}",
                data={
                    "content": (
                        "В проекте я выбрал поэтапную миграцию, описал компромиссы, "
                        "добавил метрики и проверил результат после запуска."
                    )
                },
            )
        self.request("POST", candidate_path + "/complete")

        status, run = self.request(
            "POST",
            f"/api/manager/interviews/{interview_id}/assessment-runs",
            manager=True,
            idempotency_key="assessment-run-api-001",
            data={"reason": "initial"},
        )
        self.assertEqual(202, status)
        self.assertEqual(
            {"corporate_competency", "vacancy_fit"},
            {item["dimension"] for item in run["dimension_summaries"]},
        )
        self.assertEqual(1, run["baseline_recommendation"]["score"])
        self.assertTrue(run["baseline_recommendation"]["comment"])
        self.assertFalse(run["baseline_recommendation"]["is_hiring_decision"])

        status, ranking = self.request(
            "POST",
            f"/api/manager/vacancies/{vacancy_id}/ranking-snapshots",
            manager=True,
            idempotency_key="ranking-api-001",
            data={"assessment_run_ids": [run["id"]]},
        )
        self.assertEqual(201, status)
        self.assertEqual(1, ranking["entries"][0]["rank"])
        status, decision = self.request(
            "POST",
            f"/api/manager/interviews/{interview_id}/decisions",
            manager=True,
            idempotency_key="decision-api-001",
            data={
                "actor_role": "hiring_manager",
                "decision": "hold",
                "reason": "Нужен отдельный разговор с техническим экспертом.",
            },
        )
        self.assertEqual(201, status)
        self.assertEqual("hold", decision["decision"])

        status, entry = self.request(
            "POST",
            f"/api/manager/interviews/{interview_id}/feedback-entries",
            manager=True,
            idempotency_key="feedback-api-001",
            data={
                "stage": "post_human_review",
                "source_kind": "human_authored",
                "assessment_scope": ["Архитектурное мышление"],
                "strengths": ["Называет компромиссы"],
                "growth_areas": ["Добавить показатели нагрузки"],
                "evidence_gaps": [],
                "limitations": ["Одно асинхронное интервью"],
                "next_steps": "Обсудить решение с экспертом.",
                "internal_notes": "rank=1; decision=hold; never expose",
                "assessment_evidence_ids": [],
            },
        )
        self.assertEqual(201, status)
        _, repeated_entry = self.request(
            "POST",
            f"/api/manager/interviews/{interview_id}/feedback-entries",
            manager=True,
            idempotency_key="feedback-api-001",
            data={
                "stage": "post_human_review",
                "source_kind": "human_authored",
                "assessment_scope": ["Архитектурное мышление"],
                "strengths": ["Называет компромиссы"],
                "growth_areas": ["Добавить показатели нагрузки"],
                "evidence_gaps": [],
                "limitations": ["Одно асинхронное интервью"],
                "next_steps": "Обсудить решение с экспертом.",
                "internal_notes": "rank=1; decision=hold; never expose",
                "assessment_evidence_ids": [],
            },
        )
        self.assertEqual(entry["id"], repeated_entry["id"])
        revision_id = entry["revisions"][0]["id"]
        status, _ = self.request(
            "POST",
            f"/api/manager/interviews/{interview_id}/feedback-entries/{entry['id']}/revisions/{revision_id}/publish",
            manager=True,
            idempotency_key="publish-feedback-001",
        )
        self.assertEqual(200, status)
        status, timeline = self.request(
            "GET", candidate_path + "/feedback-timeline"
        )
        self.assertEqual(200, status)
        serialized = json.dumps(timeline, ensure_ascii=False)
        self.assertEqual(1, len(timeline["feedback_entries"]))
        self.assertNotIn("internal_notes", serialized)
        self.assertNotIn("rank=1", serialized)
        self.assertNotIn("decision=hold", serialized)

    def test_vacancy_manager_page_is_available(self) -> None:
        status, _ = self.request("GET", "/api/manager/vacancies", manager=True)
        self.assertEqual(200, status)


if __name__ == "__main__":
    unittest.main()
