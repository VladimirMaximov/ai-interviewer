from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.application.assessment_services import AssessmentService
from interview_platform.application.services import InterviewService
from interview_platform.application.vacancy_services import VacancyService
from interview_platform.domain.assessment import aggregate_dimension, validate_result_evidence
from interview_platform.domain.competencies import load_framework
from interview_platform.domain.errors import ValidationError
from interview_platform.infrastructure.evaluation_stubs import DeterministicEvidenceEvaluator
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


ROOT = Path(__file__).resolve().parents[1]


class AssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "assessment.sqlite3"
        self.interviews = SQLiteInterviewRepository(path)
        self.hiring = SQLiteHiringRepository(path)
        self.interview_service = InterviewService(self.interviews, TextCaptureStub())
        self.vacancies = VacancyService(
            self.hiring,
            load_framework(ROOT / "interview_platform/data/competency_framework.v1.json"),
            interview_service=self.interview_service,
        )
        self.assessments = AssessmentService(
            self.hiring,
            self.interview_service,
            DeterministicEvidenceEvaluator(),
        )

    def tearDown(self) -> None:
        self.hiring.close()
        self.interviews.close()
        self.directory.cleanup()

    def _submitted_interview(self, *, answer_questions: bool = True):
        vacancy = self.vacancies.create_vacancy(
            title="Python API",
            role_key="software_engineer",
            target_level_key="middle",
            owner_actor_id="manager-1",
        )
        source = self.vacancies.add_context_source(
            vacancy["id"],
            source_type="phrase",
            display_name="brief",
            text="Проектирует устойчивые API и объясняет архитектурные компромиссы.",
            actor_id="manager-1",
        )
        profile = self.vacancies.draft_profile(
            vacancy["id"], source_ids=[source["id"]], actor_id="manager-1"
        )
        self.vacancies.approve_profile(vacancy["id"], profile["id"], actor_id="manager-1")
        snapshot = self.vacancies.create_snapshot(vacancy["id"])
        created = self.vacancies.create_interview(
            vacancy["id"],
            snapshot_id=snapshot["id"],
            candidate_alias="synthetic-assessment",
            invitation_token="assessment-token-value-000000000001",
        )
        token = created["invitation_token"]
        self.interview_service.start_interview(token, consent=True)
        if answer_questions:
            for question in created["interview"].questions:
                self.interview_service.save_answer(
                    token,
                    question_id=question.id,
                    content=(
                        "В проекте я сравнил риски, спроектировал контракт API, добавил тесты "
                        "и метрики, согласовал компромисс с командой и проверил результат."
                    ),
                )
            self.interview_service.complete_interview(token)
        return vacancy, snapshot, created

    def test_completed_run_has_separate_dimensions_and_is_idempotent(self) -> None:
        _, _, created = self._submitted_interview()
        first = self.assessments.create_run(
            created["interview"].id,
            reason="initial",
            idempotency_key="assessment-run-001",
        )
        second = self.assessments.create_run(
            created["interview"].id,
            reason="initial",
            idempotency_key="assessment-run-001",
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual("completed", first["status"])
        self.assertEqual([], first["integrity_signals"])
        self.assertEqual(
            {"corporate_competency", "vacancy_fit"},
            {item["dimension"] for item in first["dimension_summaries"]},
        )

    def test_missing_information_has_no_numeric_value_or_zero_penalty(self) -> None:
        results = [
            {
                "dimension": "vacancy_fit",
                "label": "demonstrated",
                "ordinal_value": 2,
                "weight": 3,
            },
            {
                "dimension": "vacancy_fit",
                "label": "insufficient_information",
                "ordinal_value": None,
                "weight": 3,
            },
        ]
        summary = aggregate_dimension(results, "vacancy_fit")

        self.assertEqual(0.5, summary["evidence_coverage"])
        self.assertAlmostEqual(66.67, summary["score"], places=2)

    def test_invented_evidence_excerpt_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_result_evidence(
                {
                    "label": "demonstrated",
                    "ordinal_value": 2,
                    "evidence": [
                        {
                            "kind": "support",
                            "question_id": "q1",
                            "excerpt": "invented words",
                            "note": "invalid",
                        }
                    ],
                },
                answers={"q1": "stored exact answer"},
            )

    def test_invalid_atomic_attempt_can_retry_with_same_idempotency_key(self) -> None:
        _, _, created = self._submitted_interview()

        class RepairableEvaluator(DeterministicEvidenceEvaluator):
            invalid = True

            def evaluate(self, context_bundle):
                results = super().evaluate(context_bundle)
                if self.invalid:
                    results[0]["evidence"][0]["excerpt"] = "invented excerpt"
                return results

        evaluator = RepairableEvaluator()
        service = AssessmentService(self.hiring, self.interview_service, evaluator)
        with self.assertRaises(ValidationError):
            service.create_run(
                created["interview"].id,
                reason="initial",
                idempotency_key="repairable-assessment-001",
            )
        self.assertEqual([], self.hiring.list_assessment_runs(created["interview"].id))

        evaluator.invalid = False
        repaired = service.create_run(
            created["interview"].id,
            reason="initial",
            idempotency_key="repairable-assessment-001",
        )
        self.assertEqual("completed", repaired["status"])


if __name__ == "__main__":
    unittest.main()
