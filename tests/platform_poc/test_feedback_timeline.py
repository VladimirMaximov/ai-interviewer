from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.application.assessment_services import AssessmentService
from interview_platform.application.feedback_services import FeedbackService
from interview_platform.application.services import InterviewService
from interview_platform.application.vacancy_services import VacancyService
from interview_platform.domain.competencies import load_framework
from interview_platform.domain.errors import ValidationError
from interview_platform.infrastructure.evaluation_stubs import DeterministicEvidenceEvaluator
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


ROOT = Path(__file__).resolve().parents[2]


class FeedbackTimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        path = Path(self.directory.name) / "feedback.sqlite3"
        self.interview_repository = SQLiteInterviewRepository(path)
        self.hiring_repository = SQLiteHiringRepository(path)
        self.interviews = InterviewService(self.interview_repository, TextCaptureStub())
        self.vacancies = VacancyService(
            self.hiring_repository,
            load_framework(
                ROOT
                / "prototypes/interview-platform/interview_platform/data/competency_framework.v1.json"
            ),
            interview_service=self.interviews,
        )
        self.assessments = AssessmentService(
            self.hiring_repository,
            self.interviews,
            DeterministicEvidenceEvaluator(),
        )
        self.feedback = FeedbackService(self.hiring_repository, self.interviews)

        vacancy = self.vacancies.create_vacancy(
            title="Python Developer",
            role_key="software_engineer",
            target_level_key="middle",
            owner_actor_id="manager-1",
        )
        source = self.vacancies.add_context_source(
            vacancy["id"],
            source_type="phrase",
            display_name="brief",
            text="Нужен опыт проектирования API.",
            actor_id="manager-1",
        )
        profile = self.vacancies.draft_profile(
            vacancy["id"], source_ids=[source["id"]], actor_id="manager-1"
        )
        self.vacancies.approve_profile(vacancy["id"], profile["id"], actor_id="manager-1")
        snapshot = self.vacancies.create_snapshot(vacancy["id"])
        self.token = "feedback-timeline-token-000000000001"
        created = self.vacancies.create_interview(
            vacancy["id"],
            snapshot_id=snapshot["id"],
            candidate_alias="synthetic-feedback",
            invitation_token=self.token,
        )
        self.interview_id = created["interview"].id
        self.interviews.start_interview(self.token, consent=True)
        for question in created["interview"].questions:
            self.interviews.save_answer(
                self.token,
                question_id=question.id,
                content="Я описал конкретную ситуацию, решение, компромисс и проверенный результат.",
            )
        self.interviews.complete_interview(self.token)
        self.run = self.assessments.create_run(
            self.interview_id,
            reason="initial",
            idempotency_key="feedback-assessment-run-1",
        )

    def tearDown(self) -> None:
        self.hiring_repository.close()
        self.interview_repository.close()
        self.directory.cleanup()

    def test_two_published_stages_and_correction_are_append_only_and_candidate_safe(self) -> None:
        preliminary = self.feedback.create_preliminary_draft(self.interview_id, self.run["id"])
        self.assertEqual([], self.feedback.candidate_timeline(self.token)["feedback_entries"])
        self.feedback.publish_revision(
            self.interview_id,
            preliminary["id"],
            preliminary["revisions"][0]["id"],
            actor_id="manager-1",
        )
        human = self.feedback.create_entry(
            self.interview_id,
            stage="post_human_review",
            source_kind="human_authored",
            actor_id="manager-1",
            assessment_scope=["Технический review"],
            strengths=["Аргументирует решения"],
            growth_areas=["Добавить численные метрики"],
            evidence_gaps=[],
            limitations=["Оценка основана на одном интервью"],
            next_steps="Обсудить систему на финальном интервью.",
            internal_notes="rank=1; decision=advance; manager-only",
            assessment_evidence_ids=[],
        )
        self.feedback.publish_revision(
            self.interview_id,
            human["id"],
            human["revisions"][0]["id"],
            actor_id="manager-1",
        )
        correction = self.feedback.create_entry(
            self.interview_id,
            stage="post_human_review",
            source_kind="corrective",
            actor_id="manager-1",
            assessment_scope=["Уточнение"],
            strengths=["Вывод подтверждён"],
            growth_areas=[],
            evidence_gaps=[],
            limitations=[],
            next_steps="Предыдущая формулировка уточнена.",
            internal_notes="private correction",
            assessment_evidence_ids=[],
            correction_of_revision_id=human["revisions"][0]["id"],
        )
        self.feedback.publish_revision(
            self.interview_id,
            correction["id"],
            correction["revisions"][0]["id"],
            actor_id="manager-1",
        )

        manager_history = self.feedback.list_entries(self.interview_id)
        candidate = self.feedback.candidate_timeline(self.token)
        self.assertEqual(3, len(manager_history))
        self.assertEqual(3, len(candidate["feedback_entries"]))
        serialized = str(candidate)
        self.assertNotIn("manager-only", serialized)
        self.assertNotIn("internal_notes", serialized)
        self.assertNotIn("rank", serialized)
        self.assertNotIn("decision", serialized)

    def test_system_actor_cannot_publish_personalized_feedback(self) -> None:
        draft = self.feedback.create_preliminary_draft(self.interview_id, self.run["id"])
        with self.assertRaises(ValidationError):
            self.feedback.publish_revision(
                self.interview_id,
                draft["id"],
                draft["revisions"][0]["id"],
                actor_id="system",
            )


if __name__ == "__main__":
    unittest.main()
