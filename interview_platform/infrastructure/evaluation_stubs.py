"""Deterministic evidence evaluator used by the local, synthetic POC."""

from __future__ import annotations

from interview_platform.domain.assessment import AssessmentLabel, LABEL_VALUES
from interview_platform.domain.baseline_recommendation import build_baseline_recommendation
from interview_platform.domain.hiring import new_id


class DeterministicEvidenceEvaluator:
    evaluator_id = "deterministic-evidence-v1"
    model_id = "deterministic-stub"
    prompt_id = "deterministic-evidence-evaluator-v1"

    def evaluate(self, context_bundle: dict) -> list[dict]:
        questions_by_position = {
            item["position"]: item
            for item in context_bundle["candidate_evidence"]["questions"]
        }
        results = []
        for criterion in context_bundle["vacancy_context"]["criteria"]:
            question = questions_by_position[criterion["question_position"]]
            answer = question.get("answer")
            if not answer:
                label = AssessmentLabel.INSUFFICIENT_INFORMATION
                evidence = [
                    {
                        "id": new_id(),
                        "kind": "information_gap",
                        "question_id": question["id"],
                        "excerpt": None,
                        "note": criterion.get(
                            "insufficient_information_rule",
                            "Нет ответа для проверки критерия.",
                        ),
                    }
                ]
                confidence = 0.0
                explanation = "Недостаточно информации для оценки критерия."
            else:
                lowered = answer.casefold()
                if any(marker in lowered for marker in ("не знаю", "нет опыта", "не делал")):
                    label = AssessmentLabel.NOT_DEMONSTRATED
                elif len(answer.strip()) < 40:
                    label = AssessmentLabel.PARTIALLY_DEMONSTRATED
                elif len(answer.strip()) < 140:
                    label = AssessmentLabel.DEMONSTRATED
                else:
                    label = AssessmentLabel.STRONGLY_DEMONSTRATED
                excerpt = answer[:280]
                evidence = [
                    {
                        "id": new_id(),
                        "kind": "support"
                        if label is not AssessmentLabel.NOT_DEMONSTRATED
                        else "counter_evidence",
                        "question_id": question["id"],
                        "excerpt": excerpt,
                        "note": "Детерминированный POC оценивает полноту конкретного текстового ответа.",
                    }
                ]
                confidence = 0.75
                explanation = (
                    "Ответ содержит проверяемый фрагмент; итоговый label сформирован "
                    "детерминированным POC-правилом, а не моделью найма."
                )
            results.append(
                {
                    "id": new_id(),
                    "dimension": criterion["dimension"],
                    "criterion_id": criterion["id"],
                    "criterion_title": criterion["display_name"],
                    "label": label.value,
                    "ordinal_value": LABEL_VALUES[label],
                    "confidence": confidence,
                    "explanation": explanation,
                    "weight": int(criterion.get("weight", 1)),
                    "category": criterion.get("category"),
                    "evidence": evidence,
                }
            )
        return results

    def recommend(self, context_bundle: dict, results: list[dict]) -> dict:
        """Build the POC's non-binding 1/0/-1 recommendation."""

        return build_baseline_recommendation(context_bundle, results)
