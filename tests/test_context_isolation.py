from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.application.assessment_services import AssessmentService
from interview_platform.application.services import InterviewService
from interview_platform.application.vacancy_services import VacancyService
from interview_platform.domain.competencies import load_framework
from interview_platform.infrastructure.evaluation_stubs import DeterministicEvidenceEvaluator
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


ROOT = Path(__file__).resolve().parents[1]


class ContextIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "isolation.sqlite3"
        self.interview_repository = SQLiteInterviewRepository(path)
        self.hiring_repository = SQLiteHiringRepository(path)
        self.interviews = InterviewService(self.interview_repository, TextCaptureStub())
        self.vacancies = VacancyService(
            self.hiring_repository,
            load_framework(ROOT / "interview_platform/data/competency_framework.v1.json"),
            interview_service=self.interviews,
        )
        self.assessments = AssessmentService(
            self.hiring_repository,
            self.interviews,
            DeterministicEvidenceEvaluator(),
        )

    def tearDown(self) -> None:
        self.hiring_repository.close()
        self.interview_repository.close()
        self.directory.cleanup()

    def _run(self, description: str, suffix: str):
        vacancy = self.vacancies.create_vacancy(
            title=f"Vacancy {suffix}",
            role_key="software_engineer",
            target_level_key="middle",
            owner_actor_id="manager-1",
        )
        source = self.vacancies.add_context_source(
            vacancy["id"],
            source_type="phrase",
            display_name=f"brief-{suffix}",
            text=description,
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
            candidate_alias=f"synthetic-{suffix}",
            invitation_token=f"context-isolation-token-{suffix}-0000000000",
        )
        token = created["invitation_token"]
        self.interviews.start_interview(token, consent=True)
        answer = "Я спроектировал решение, объяснил компромиссы, добавил тесты и проверил результат."
        for question in created["interview"].questions:
            self.interviews.save_answer(token, question_id=question.id, content=answer)
        self.interviews.complete_interview(token)
        run = self.assessments.create_run(
            created["interview"].id,
            reason="initial",
            idempotency_key=f"isolation-run-{suffix}",
        )
        return snapshot, run

    def test_vacancy_context_changes_fit_but_not_corporate_results(self) -> None:
        first_snapshot, first = self._run("Нужно проектировать API.", "a")
        second_snapshot, second = self._run("Нужно оптимизировать потоковые данные.", "b")

        def corporate(run):
            return [
                (item["criterion_id"], item["label"], item["ordinal_value"])
                for item in run["criterion_assessments"]
                if item["dimension"] == "corporate_competency"
            ]

        self.assertEqual(corporate(first), corporate(second))
        self.assertNotEqual(first_snapshot["context_hash"], second_snapshot["context_hash"])
        first_fit = [
            item["criterion_title"]
            for item in first["criterion_assessments"]
            if item["dimension"] == "vacancy_fit"
        ]
        second_fit = [
            item["criterion_title"]
            for item in second["criterion_assessments"]
            if item["dimension"] == "vacancy_fit"
        ]
        self.assertNotEqual(first_fit, second_fit)

    def test_published_profile_change_does_not_mutate_existing_snapshot(self) -> None:
        vacancy, first_snapshot, _ = self._run_with_vacancy(
            "Нужно проектировать совместимые API.", "immutable"
        )
        original = self.vacancies.get_snapshot(first_snapshot["id"])
        source = self.vacancies.add_context_source(
            vacancy["id"],
            source_type="phrase",
            display_name="new brief",
            text="Теперь дополнительно нужен опыт потоковой обработки данных.",
            actor_id="manager-1",
        )
        profile = self.vacancies.draft_profile(
            vacancy["id"], source_ids=[source["id"]], actor_id="manager-1"
        )
        self.vacancies.approve_profile(
            vacancy["id"], profile["id"], actor_id="manager-1"
        )
        second_snapshot = self.vacancies.create_snapshot(vacancy["id"])

        self.assertEqual(original, self.vacancies.get_snapshot(first_snapshot["id"]))
        self.assertNotEqual(original["context_hash"], second_snapshot["context_hash"])

    def _run_with_vacancy(self, description: str, suffix: str):
        snapshot, run = self._run(description, suffix)
        assignment = self.hiring_repository.get_assignment(run["interview_id"])
        vacancy = self.vacancies.get_vacancy(assignment["vacancy_id"])
        return vacancy, snapshot, run


if __name__ == "__main__":
    unittest.main()
