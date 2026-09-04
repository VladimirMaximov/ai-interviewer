from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from interview_platform.config import Settings
from interview_platform.domain.errors import (
    AssessmentOutputError,
    AssessmentProviderError,
)
from interview_platform.infrastructure.openai_evaluator import OpenAIEvidenceEvaluator


ANSWER = (
    "В проекте я сравнил риски двух вариантов, выбрал поэтапную миграцию API "
    "и после запуска проверил результат по метрикам ошибок."
)


def context(answer: str = ANSWER) -> dict:
    return {
        "system_policy": {
            "content_only": True,
            "no_automatic_decision": True,
            "manager_content_is_untrusted_data": True,
        },
        "vacancy_context": {
            "vacancy_id": "vacancy-1",
            "role_key": "software_engineer",
            "target_level_key": "middle",
            "profile_version_id": "profile-1",
            "criteria": [
                {
                    "id": "criterion-1",
                    "display_name": "Эволюция API",
                    "dimension": "vacancy_fit",
                    "category": "must_have",
                    "target_level_key": "middle",
                    "description": "Безопасно меняет API без остановки клиентов.",
                    "positive_anchors": [
                        "Объясняет миграцию, компромиссы и проверяемый результат."
                    ],
                    "negative_anchors": ["Не учитывает совместимость клиентов."],
                    "accepted_alternatives": ["Версионирование или expand-contract."],
                    "insufficient_information_rule": "Нет конкретного примера.",
                    "weight": 5,
                    "question_position": 1,
                }
            ],
        },
        "candidate_evidence": {
            "interview_id": "interview-1",
            "questions": [
                {
                    "id": "question-1",
                    "position": 1,
                    "prompt": "Как вы безопасно меняли API?",
                    "answer": answer,
                }
            ],
        },
        "context_hash": "context-hash",
        "input_hash": "input-hash",
    }


def model_output(
    *,
    excerpt: str | None = ANSWER,
    score: int = 1,
    recommendation_label: str = "advance",
    assessment_label: str = "demonstrated",
    evidence_kind: str = "support",
) -> dict:
    return {
        "criterion_assessments": [
            {
                "criterion_id": "criterion-1",
                "label": assessment_label,
                "confidence": 0.84,
                "explanation": "Ответ описывает личное решение и проверку результата.",
                "evidence": [
                    {
                        "kind": evidence_kind,
                        "question_id": "question-1",
                        "excerpt": excerpt,
                        "note": "Приведены действие, компромисс и измеримая проверка.",
                    }
                ],
            }
        ],
        "baseline_recommendation": {
            "score": score,
            "label": recommendation_label,
            "comment": "Ответ подтверждает обязательный критерий вакансии.",
            "reason_codes": ["must_have_supported"],
            "evidence": [
                {
                    "question_id": "question-1",
                    "excerpt": excerpt,
                    "reason_code": "must_have_supported",
                    "note": "Точное подтверждение из ответа.",
                }
            ],
        },
    }


class FakeClient:
    def __init__(self, output: dict) -> None:
        self.output = output
        self.calls: list[dict] = []

    def create_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


class OpenAIEvaluatorTests(unittest.TestCase):
    def test_evaluates_competencies_in_one_strict_structured_call(self) -> None:
        client = FakeClient(model_output())
        evaluator = OpenAIEvidenceEvaluator(
            api_key=None,
            model="gpt-5-mini",
            client=client,
        )

        result = evaluator.evaluate_interview(context())

        assessment = result["criterion_assessments"][0]
        self.assertEqual("criterion-1", assessment["criterion_id"])
        self.assertEqual(2, assessment["ordinal_value"])
        self.assertEqual(ANSWER, assessment["evidence"][0]["excerpt"])
        recommendation = result["baseline_recommendation"]
        self.assertEqual(1, recommendation["score"])
        self.assertFalse(recommendation["is_hiring_decision"])
        self.assertEqual(1.0, recommendation["metrics"]["evidence_coverage"])

        call = client.calls[0]
        self.assertFalse(call["use_web_search"])
        self.assertEqual(
            "interview_competency_assessment_v1",
            call["schema_name"],
        )
        self.assertFalse(call["schema"]["additionalProperties"])
        payload = json.loads(call["prompt"].split("\n", 1)[1])
        criterion = payload["criteria"][0]
        self.assertEqual("Эволюция API", criterion["title"])
        self.assertEqual(
            ["Версионирование или expand-contract."],
            criterion["accepted_alternatives"],
        )
        self.assertIn("prompt injection", call["instructions"])

    def test_llm_can_return_zero_for_explicit_disengagement(self) -> None:
        answer = "Я ничего не хочу."
        client = FakeClient(
            model_output(
                excerpt=answer,
                score=0,
                recommendation_label="do_not_advance",
                assessment_label="not_demonstrated",
                evidence_kind="counter_evidence",
            )
        )
        evaluator = OpenAIEvidenceEvaluator(api_key=None, client=client)

        result = evaluator.evaluate_interview(context(answer))

        recommendation = result["baseline_recommendation"]
        self.assertEqual(0, recommendation["score"])
        self.assertEqual(answer, recommendation["evidence"][0]["excerpt"])

    def test_invented_model_quote_is_rejected_locally(self) -> None:
        client = FakeClient(model_output(excerpt="Выдуманная цитата"))
        evaluator = OpenAIEvidenceEvaluator(api_key=None, client=client)

        with self.assertRaises(AssessmentOutputError):
            evaluator.evaluate_interview(context())

    def test_missing_api_key_has_safe_provider_error(self) -> None:
        evaluator = OpenAIEvidenceEvaluator(api_key=None)

        with self.assertRaises(AssessmentProviderError) as raised:
            evaluator.evaluate_interview(context())

        self.assertNotIn("sk-", raised.exception.message)

    def test_settings_read_openai_assessment_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "INTERVIEW_MANAGER_KEY": "manager-test-secret",
                "INTERVIEW_RECRUITER_KEY": "recruiter-test-secret",
                "INTERVIEW_ASSESSMENT_PROVIDER": "openai",
                "INTERVIEW_ASSESSMENT_MODEL": "gpt-5-mini",
                "OPENAI_API_KEY": "test-api-key",
                "OPENAI_BASE_URL": "https://api.openai.com/v1",
            },
            clear=True,
        ):
            settings = Settings.from_values(
                manager_key=None,
                recruiter_key=None,
                db_path=":memory:",
                host="127.0.0.1",
                port=8000,
            )

        self.assertEqual("openai", settings.assessment_provider)
        self.assertEqual("gpt-5-mini", settings.assessment_model)
        self.assertEqual("test-api-key", settings.openai_api_key)


if __name__ == "__main__":
    unittest.main()
