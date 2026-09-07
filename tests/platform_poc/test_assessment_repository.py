from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository


class AssessmentRepositoryTests(unittest.TestCase):
    def test_assessment_round_trip_keeps_dimensions_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "round-trip.sqlite3"
            repository = SQLiteHiringRepository(path)
            repository.save_vacancy(
                {
                    "id": "vacancy-1",
                    "status": "active",
                    "role_key": "software_engineer",
                    "target_level_key": "middle",
                    "active_profile_version_id": "profile-1",
                    "created_at": "2026-09-03T09:00:00+00:00",
                    "updated_at": "2026-09-03T09:00:00+00:00",
                }
            )
            repository.save_profile(
                {
                    "id": "profile-1",
                    "vacancy_id": "vacancy-1",
                    "version": 1,
                    "status": "approved",
                    "content_hash": "p" * 64,
                    "created_at": "2026-09-03T09:00:00+00:00",
                }
            )
            repository.save_snapshot(
                {
                    "id": "snapshot-1",
                    "vacancy_id": "vacancy-1",
                    "profile_version_id": "profile-1",
                    "context_hash": "s" * 64,
                    "created_at": "2026-09-03T09:00:00+00:00",
                }
            )
            payload = {
                "id": "run-1",
                "interview_id": "interview-1",
                "context_snapshot_id": "snapshot-1",
                "idempotency_key": "round-trip-key",
                "status": "completed",
                "compatibility_key": "c" * 64,
                "criterion_assessments": [
                    {
                        "dimension": "vacancy_fit",
                        "criterion_id": "criterion-1",
                        "label": "demonstrated",
                        "ordinal_value": 2,
                        "evidence": [{"excerpt": "exact"}],
                    }
                ],
                "dimension_summaries": [{"dimension": "vacancy_fit", "score": 66.67}],
                "created_at": "2026-09-03T10:00:00+00:00",
            }
            repository.save_assessment_run(payload)
            repository.close()

            reopened = SQLiteHiringRepository(path)
            self.assertEqual(payload, reopened.get_assessment_run("run-1"))
            self.assertEqual(payload, reopened.get_assessment_by_idempotency("round-trip-key"))
            reopened.close()


if __name__ == "__main__":
    unittest.main()
