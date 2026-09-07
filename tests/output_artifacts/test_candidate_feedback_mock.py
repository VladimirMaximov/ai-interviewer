import json
import unittest
from pathlib import Path


MOCK_PATH = (
    Path(__file__).resolve().parents[2]
    / "outputs"
    / "ai-technical-interview"
    / "candidate-feedback-mock.json"
)


class CandidateFeedbackMockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(MOCK_PATH.read_text(encoding="utf-8"))

    def test_mock_is_synthetic_and_not_a_hiring_decision(self) -> None:
        self.assertEqual("synthetic", self.payload["data_classification"])
        self.assertFalse(self.payload["assessment"]["is_hiring_decision"])
        self.assertTrue(self.payload["publication"]["requires_human_review"])

    def test_potential_candidate_receives_a_reviewed_alternative(self) -> None:
        self.assertEqual(
            "potential", self.payload["internal_routing"]["candidate_pool"]
        )
        alternative = self.payload["candidate_feedback"]["alternative_vacancy"]
        self.assertTrue(alternative["vacancy_id"])
        self.assertFalse(alternative["is_automatic_transfer"])
        self.assertTrue(
            self.payload["publication"]["alternative_vacancy_must_be_active"]
        )

    def test_candidate_projection_does_not_leak_internal_routing(self) -> None:
        candidate_projection = json.dumps(
            self.payload["candidate_feedback"], ensure_ascii=False
        ).casefold()
        for prohibited in ("blacklist", "candidate_pool", "window_switch"):
            self.assertNotIn(prohibited, candidate_projection)

    def test_feedback_references_only_declared_evidence(self) -> None:
        evidence_ids = {item["id"] for item in self.payload["evidence"]}
        feedback = self.payload["candidate_feedback"]
        referenced_ids = {
            evidence_id
            for section in (feedback["strengths"], feedback["growth_areas"])
            for item in section
            for evidence_id in item["evidence_ids"]
        }
        self.assertTrue(referenced_ids)
        self.assertLessEqual(referenced_ids, evidence_ids)

    def test_integrity_events_do_not_affect_score_or_restrictions(self) -> None:
        integrity = self.payload["integrity_signals"]
        self.assertEqual("none", integrity["score_impact"])
        self.assertEqual("none", integrity["restriction_impact"])
        self.assertFalse(self.payload["internal_routing"]["automatic_blacklist_allowed"])


if __name__ == "__main__":
    unittest.main()
