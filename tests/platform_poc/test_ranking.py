from __future__ import annotations

import random
import unittest

from interview_platform.domain.errors import ValidationError
from interview_platform.domain.ranking import build_ranking_snapshot


def run(run_id: str, fit: float | None, competency: float, coverage: float, key: str = "same"):
    return {
        "id": run_id,
        "interview_id": f"interview-{run_id}",
        "status": "completed",
        "compatibility_key": key,
        "candidate_alias": f"synthetic-{run_id}",
        "dimension_summaries": [
            {"dimension": "vacancy_fit", "score": fit, "evidence_coverage": coverage},
            {"dimension": "corporate_competency", "score": competency, "evidence_coverage": 1.0},
        ],
        "criterion_assessments": [],
    }


class RankingTests(unittest.TestCase):
    policy = {
        "version": 1,
        "primary_dimension": "vacancy_fit",
        "secondary_dimension": "corporate_competency",
        "minimum_evidence_coverage": 0.5,
        "display_precision": 2,
    }

    def test_ranking_is_deterministic_preserves_ties_and_groups_low_coverage(self) -> None:
        runs = [
            run("a", 80.0, 70.0, 1.0),
            run("b", 80.0, 70.0, 1.0),
            run("c", 99.0, 90.0, 0.25),
            run("d", 60.0, 95.0, 1.0),
        ]
        first = build_ranking_snapshot("vacancy-1", runs, self.policy, snapshot_id="ranking-1")
        random.shuffle(runs)
        second = build_ranking_snapshot("vacancy-1", runs, self.policy, snapshot_id="ranking-1")

        self.assertEqual(first["entries"], second["entries"])
        by_run = {item["assessment_run_id"]: item for item in first["entries"]}
        self.assertEqual(1, by_run["a"]["rank"])
        self.assertEqual(1, by_run["b"]["rank"])
        self.assertEqual("additional_review", by_run["c"]["group"])
        self.assertIsNone(by_run["c"]["rank"])
        self.assertEqual(3, by_run["d"]["rank"])

    def test_incompatible_runs_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            build_ranking_snapshot(
                "vacancy-1",
                [run("a", 80.0, 70.0, 1.0), run("b", 70.0, 80.0, 1.0, key="other")],
                self.policy,
                snapshot_id="ranking-1",
            )


if __name__ == "__main__":
    unittest.main()
