from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.__main__ import (
    build_hiring_services,
    seed_vacancy_assessment_demo,
)
from interview_platform.application.services import InterviewService
from interview_platform.config import Settings
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub


class VacancySeedTests(unittest.TestCase):
    def test_synthetic_vacancy_seed_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.sqlite3"
            interview_repository = SQLiteInterviewRepository(path)
            hiring_repository = SQLiteHiringRepository(path)
            try:
                interviews = InterviewService(interview_repository, TextCaptureStub())
                settings = Settings(
                    manager_key="seed-test-secret",
                    recruiter_key="seed-recruiter-secret",
                    db_path=path,
                    assessment_provider="deterministic",
                )
                hiring = build_hiring_services(settings, hiring_repository, interviews)
                first = seed_vacancy_assessment_demo(hiring, interview_repository)
                second = seed_vacancy_assessment_demo(hiring, interview_repository)
                self.assertEqual(first["vacancy"]["id"], second["vacancy"]["id"])
                self.assertEqual(first["snapshot"]["id"], second["snapshot"]["id"])
                self.assertEqual(first["assessment_run_ids"], second["assessment_run_ids"])
                self.assertEqual([1, 0, -1], first["baseline_scores"])
                self.assertEqual(3, len(interview_repository.list_interviews()))
            finally:
                hiring_repository.close()
                interview_repository.close()


if __name__ == "__main__":
    unittest.main()
