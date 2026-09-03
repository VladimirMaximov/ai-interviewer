from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.application.vacancy_services import VacancyService
from interview_platform.domain.competencies import load_framework
from interview_platform.domain.errors import ValidationError
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository


ROOT = Path(__file__).resolve().parents[1]


class VacancyProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = SQLiteHiringRepository(Path(self.directory.name) / "hiring.sqlite3")
        self.service = VacancyService(
            self.repository,
            load_framework(ROOT / "interview_platform/data/competency_framework.v1.json"),
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _draft(self):
        vacancy = self.service.create_vacancy(
            title="Python Platform Engineer",
            role_key="software_engineer",
            target_level_key="middle",
            owner_actor_id="manager-1",
        )
        source = self.service.add_context_source(
            vacancy["id"],
            source_type="pasted_text",
            display_name="manager brief",
            text="Нужно проектировать API и безопасно развивать контракты без остановки клиентов.",
            actor_id="manager-1",
        )
        draft = self.service.draft_profile(
            vacancy["id"],
            source_ids=[source["id"]],
            actor_id="manager-1",
        )
        return vacancy, source, draft

    def test_drafts_criteria_with_provenance_and_approves_immutable_version(self) -> None:
        vacancy, source, draft = self._draft()

        self.assertEqual("draft", draft["status"])
        self.assertEqual([source["id"]], draft["source_ids"])
        self.assertTrue(draft["criteria"][0]["source_fragment_ids"])
        self.assertTrue(draft["criteria"][0]["question_prompt"])

        approved = self.service.approve_profile(
            vacancy["id"], draft["id"], actor_id="manager-1"
        )
        self.assertEqual("approved", approved["status"])
        self.assertEqual(64, len(approved["content_hash"]))
        self.assertEqual(approved["id"], self.service.get_vacancy(vacancy["id"])["active_profile_version_id"])

        second = self.service.draft_profile(
            vacancy["id"], source_ids=[source["id"]], actor_id="manager-1"
        )
        self.assertEqual(2, second["version"])
        self.assertEqual("approved", self.service.get_profile(approved["id"])["status"])

    def test_prohibited_voice_criterion_blocks_approval(self) -> None:
        vacancy, _, draft = self._draft()
        criteria = draft["criteria"]
        criteria[0]["description"] = "Кандидат уверенно звучит и говорит без акцента."
        updated = self.service.update_profile(
            draft["id"],
            summary=draft["summary"],
            criteria=criteria,
            actor_id="manager-1",
        )

        with self.assertRaises(ValidationError) as context:
            self.service.approve_profile(vacancy["id"], updated["id"], actor_id="manager-1")
        issue_codes = {item["code"] for item in context.exception.details["issues"]}
        self.assertIn("prohibited_trait", issue_codes)

    def test_markdown_file_is_utf8_and_source_bounded(self) -> None:
        vacancy = self.service.create_vacancy(
            title="Backend",
            role_key="software_engineer",
            target_level_key="junior",
            owner_actor_id="manager-1",
        )
        source = self.service.add_context_source(
            vacancy["id"],
            source_type="file",
            display_name="requirements.md",
            text="# Требование\nПишет тесты и объясняет компромиссы.".encode(),
            actor_id="manager-1",
            media_type="text/markdown",
        )

        self.assertEqual("ready", source["status"])
        self.assertEqual("file", source["source_type"])
        self.assertGreaterEqual(len(source["fragments"]), 1)


if __name__ == "__main__":
    unittest.main()
