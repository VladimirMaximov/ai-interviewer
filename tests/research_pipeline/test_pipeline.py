import tempfile
import unittest
from pathlib import Path

from product_engineering.pipeline import (
    PipelineConfig,
    ProductEngineeringPipeline,
    normalize_and_rank_hypotheses,
    normalize_pain_map,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def create_json(self, **kwargs):
        stage = kwargs["schema_name"]
        self.calls.append(stage)
        responses = {
            "product_research": {
                "direction": "test market",
                "products": [
                    {
                        "name": "Acme",
                        "url": "https://example.com/",
                        "what_it_sells": "Planning software",
                        "commercial_evidence": "Pricing is available",
                        "source_urls": ["https://example.com/pricing"],
                    }
                ],
            },
            "product_description": {
                "name": "Acme",
                "summary": "Planning software for operators.",
                "category": "Planning",
                "audience_clues": ["Operators"],
                "key_features": ["Forecasting"],
                "value_proposition": "Plan with less manual work.",
                "pricing_signals": ["Paid plans"],
                "evidence_gaps": [],
            },
            "customer_segments": {
                "segments": [
                    {"name": "Operations Teams", "description": "Plan work faster."}
                ]
            },
            "ideal_customer_profile": {"customer_type": "B2B"},
            "synthetic_interview": {
                "evidence_type": "synthetic",
                "questions": [],
            },
            "pain_map": {
                "segment": "Operations Teams",
                "evidence_type": "synthetic",
                "pains": [
                    {
                        "pain": "Manual planning",
                        "evidence_quotes": ["Q2/A2: It takes hours"],
                        "severity": 5,
                        "frequency": 4,
                        "reach": 3,
                        "confidence": 2,
                        "priority_score": 10,
                        "root_cause": "Fragmented tools",
                        "current_workarounds": ["Spreadsheets"],
                        "desired_outcome": "Faster plans",
                        "related_jtbd": ["Create a plan"],
                        "opportunity_notes": "Automate setup",
                    }
                ],
            },
            "jobs_to_be_done": {"segment": "Operations Teams", "jtbd": []},
            "value_proposition_canvas": {
                "product": "https://example.com/",
                "segment": "Operations Teams",
            },
            "product_hypotheses": {
                "hypotheses": [
                    {
                        "id": 1,
                        "description": "Guided setup",
                        "rationale": "Reduce manual planning",
                        "metric_to_validate": "Activation rate",
                        "expected_outcome": "Higher activation",
                        "reach": 500,
                        "impact": 2,
                        "confidence": 0.9,
                        "effort": 2.2,
                        "rationale_reach": "Medium segment",
                        "rationale_impact": "Activation impact",
                        "rationale_confidence": "Synthetic interview",
                        "rationale_effort": "Medium UX work",
                    },
                    {
                        "id": 2,
                        "description": "New copy",
                        "rationale": "Clarify value",
                        "metric_to_validate": "Click-through rate",
                        "expected_outcome": "More trials",
                        "reach": 100,
                        "impact": 1,
                        "confidence": 0.5,
                        "effort": 0.5,
                        "rationale_reach": "Low segment",
                        "rationale_impact": "Trial impact",
                        "rationale_confidence": "Assumption",
                        "rationale_effort": "Copy change",
                    },
                ]
            },
            "lean_canvas": {
                "unique_value_proposition": "Planning without spreadsheet busywork"
            },
        }
        return responses[stage]


class PipelineTests(unittest.TestCase):
    def test_recalculates_pain_score(self) -> None:
        data = {
            "pains": [
                {
                    "severity": 5,
                    "frequency": 4,
                    "reach": 3,
                    "confidence": 2,
                    "priority_score": 10,
                }
            ]
        }
        normalized = normalize_pain_map(data)
        self.assertEqual(normalized["pains"][0]["priority_score"], 40)

    def test_rice_is_deterministic_and_caps_synthetic_confidence(self) -> None:
        ranked = normalize_and_rank_hypotheses(
            {
                "hypotheses": [
                    {"id": 1, "reach": 100, "impact": 2, "confidence": 0.9, "effort": 2.2},
                    {"id": 2, "reach": 100, "impact": 1, "confidence": 0.5, "effort": 0.5},
                ]
            }
        )
        self.assertEqual(ranked[0]["id"], 2)
        first = next(item for item in ranked if item["id"] == 1)
        self.assertEqual(first["confidence"], 0.7)
        self.assertEqual(first["effort"], 2.0)
        self.assertEqual(first["rice_score"], 70.0)

    def test_end_to_end_checkpoints_are_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            config = PipelineConfig(
                direction="test market", max_products=1, max_segments=1
            )
            client = FakeClient()

            def fetcher(url, timeout):
                return {
                    "url": url,
                    "requested_url": url,
                    "title": "Acme",
                    "description": "Planning software",
                    "lang": "en",
                    "h1": ["Plan faster"],
                    "h2": [],
                    "h3": [],
                    "h4": [],
                }

            pipeline = ProductEngineeringPipeline(
                client=client,
                config=config,
                run_dir=run_dir,
                fetcher=fetcher,
            )
            result = pipeline.run()
            self.assertEqual(result["products"][0]["candidate"]["url"], "https://example.com/")
            self.assertEqual(result["products"][0]["segment_analyses"][0]["pain_map"]["pains"][0]["priority_score"], 40)
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertEqual(len(client.calls), 10)

            resumed_client = FakeClient()
            resumed = ProductEngineeringPipeline(
                client=resumed_client,
                config=config,
                run_dir=run_dir,
                fetcher=fetcher,
            )
            resumed.run()
            self.assertEqual(resumed_client.calls, [])


if __name__ == "__main__":
    unittest.main()
