"""Evidence validation and deterministic multidimensional assessment."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .hiring import canonical_hash, new_id, utc_now


class AssessmentLabel(StrEnum):
    NOT_DEMONSTRATED = "not_demonstrated"
    PARTIALLY_DEMONSTRATED = "partially_demonstrated"
    DEMONSTRATED = "demonstrated"
    STRONGLY_DEMONSTRATED = "strongly_demonstrated"
    INSUFFICIENT_INFORMATION = "insufficient_information"


LABEL_VALUES = {
    AssessmentLabel.NOT_DEMONSTRATED: 0,
    AssessmentLabel.PARTIALLY_DEMONSTRATED: 1,
    AssessmentLabel.DEMONSTRATED: 2,
    AssessmentLabel.STRONGLY_DEMONSTRATED: 3,
    AssessmentLabel.INSUFFICIENT_INFORMATION: None,
}


def validate_result_evidence(result: dict[str, Any], *, answers: dict[str, str]) -> None:
    try:
        label = AssessmentLabel(result["label"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("assessment label is invalid") from exc
    expected_value = LABEL_VALUES[label]
    if result.get("ordinal_value") != expected_value:
        raise ValidationError("ordinal value does not match assessment label")
    evidence = result.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValidationError("criterion assessment requires evidence")

    validated_numeric_evidence = False
    information_gap = False
    for item in evidence:
        question_id = item.get("question_id")
        kind = item.get("kind")
        if question_id not in answers:
            raise ValidationError("assessment evidence question is not in the interview")
        if kind in {"support", "counter_evidence"}:
            excerpt = item.get("excerpt")
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise ValidationError("numeric assessment evidence requires an excerpt")
            if excerpt not in answers[question_id]:
                raise ValidationError("assessment evidence excerpt must occur in the stored answer")
            validated_numeric_evidence = True
        elif kind == "information_gap":
            if item.get("excerpt") not in {None, ""}:
                raise ValidationError("information-gap evidence cannot include an excerpt")
            information_gap = True
        else:
            raise ValidationError("assessment evidence kind is invalid")
    if expected_value is None and not information_gap:
        raise ValidationError("insufficient information requires an information gap")
    if expected_value is not None and not validated_numeric_evidence:
        raise ValidationError("numeric assessment requires validated answer evidence")


def aggregate_dimension(results: list[dict[str, Any]], dimension: str) -> dict[str, Any]:
    applicable = [item for item in results if item.get("dimension") == dimension]
    if not applicable:
        raise ValidationError("assessment dimension has no applicable criteria")
    applicable_weight = sum(int(item["weight"]) for item in applicable)
    assessed = [item for item in applicable if item.get("ordinal_value") is not None]
    assessed_weight = sum(int(item["weight"]) for item in assessed)
    score = None
    if assessed_weight:
        weighted = sum(int(item["weight"]) * int(item["ordinal_value"]) for item in assessed)
        score = round(weighted / (3 * assessed_weight) * 100, 2)
    counts = Counter(item["label"] for item in applicable)
    return {
        "dimension": dimension,
        "score": score,
        "assessed_weight": assessed_weight,
        "applicable_weight": applicable_weight,
        "evidence_coverage": round(assessed_weight / applicable_weight, 4),
        "label_counts": dict(sorted(counts.items())),
        "aggregation_policy_hash": canonical_hash("weighted-ordinal-v1"),
    }


def complete_assessment_run(
    *,
    run_id: str,
    interview_id: str,
    context_snapshot_id: str,
    context_hash: str,
    run_number: int,
    reason: str,
    idempotency_key: str,
    evaluator_id: str,
    model_id: str,
    input_hash: str,
    raw_results: list[dict[str, Any]],
    answers: dict[str, str],
    created_at: str,
    integrity_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    for item in raw_results:
        validate_result_evidence(item, answers=answers)
    dimensions = ["corporate_competency", "vacancy_fit"]
    summaries = [
        aggregate_dimension(raw_results, dimension)
        for dimension in dimensions
        if any(item["dimension"] == dimension for item in raw_results)
    ]
    output = {
        "criterion_assessments": raw_results,
        "dimension_summaries": summaries,
    }
    return {
        "id": run_id,
        "interview_id": interview_id,
        "context_snapshot_id": context_snapshot_id,
        "run_number": run_number,
        "reason": reason,
        "idempotency_key": idempotency_key,
        "status": "completed",
        "evaluator_id": evaluator_id,
        "model_id": model_id,
        "prompt_hash": canonical_hash("deterministic-evidence-evaluator-v1"),
        "input_hash": input_hash,
        "output_hash": canonical_hash(output),
        "compatibility_key": canonical_hash(
            {"context_hash": context_hash, "aggregation_policy": "weighted-ordinal-v1"}
        ),
        **output,
        "integrity_signals": list(integrity_signals or []),
        "failure_code": None,
        "created_at": created_at,
        "completed_at": utc_now(),
    }


def failed_assessment_run(
    *,
    interview_id: str,
    context_snapshot_id: str,
    idempotency_key: str,
    reason: str,
    failure_code: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "id": new_id(),
        "interview_id": interview_id,
        "context_snapshot_id": context_snapshot_id,
        "run_number": 1,
        "reason": reason,
        "idempotency_key": idempotency_key,
        "status": "failed",
        "evaluator_id": "deterministic-evidence-v1",
        "model_id": "deterministic-stub",
        "prompt_hash": None,
        "input_hash": canonical_hash({"interview_id": interview_id}),
        "output_hash": None,
        "compatibility_key": canonical_hash({"context_snapshot_id": context_snapshot_id}),
        "criterion_assessments": [],
        "dimension_summaries": [],
        "integrity_signals": [],
        "failure_code": failure_code,
        "created_at": created_at,
        "completed_at": utc_now(),
    }
