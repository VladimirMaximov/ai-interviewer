"""Deterministic compatible-only candidate ranking."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .hiring import canonical_hash, utc_now


def _summary(run: dict[str, Any], dimension: str) -> dict[str, Any]:
    for item in run.get("dimension_summaries", []):
        if item.get("dimension") == dimension:
            return item
    return {"dimension": dimension, "score": None, "evidence_coverage": 0.0}


def build_ranking_snapshot(
    vacancy_id: str,
    runs: list[dict[str, Any]],
    policy: dict[str, Any],
    *,
    snapshot_id: str,
) -> dict[str, Any]:
    if not runs:
        raise ValidationError("ranking requires at least one assessment run")
    if any(run.get("status") != "completed" for run in runs):
        raise ValidationError("ranking accepts completed assessment runs only")
    compatibility_keys = {run.get("compatibility_key") for run in runs}
    if len(compatibility_keys) != 1 or None in compatibility_keys:
        raise ValidationError(
            "assessment runs are not compatible",
            details={"compatibility_keys": sorted(str(item) for item in compatibility_keys)},
        )
    primary_dimension = policy.get("primary_dimension", "vacancy_fit")
    secondary_dimension = policy.get("secondary_dimension", "corporate_competency")
    coverage_floor = float(policy.get("minimum_evidence_coverage", 0.5))
    precision = int(policy.get("display_precision", 2))

    ranked = []
    additional = []
    for run in runs:
        primary = _summary(run, primary_dimension)
        secondary = _summary(run, secondary_dimension) if secondary_dimension else {}
        coverage = float(primary.get("evidence_coverage", 0.0))
        entry = {
            "assessment_run_id": run["id"],
            "interview_id": run["interview_id"],
            "candidate_alias": run.get("candidate_alias", "synthetic-candidate"),
            "group": "ranked",
            "rank": None,
            "primary_dimension": primary_dimension,
            "primary_value": primary.get("score"),
            "secondary_dimension": secondary_dimension,
            "secondary_value": secondary.get("score"),
            "evidence_coverage": coverage,
            "contributions": [
                {
                    "criterion_id": item["criterion_id"],
                    "dimension": item["dimension"],
                    "value": item.get("ordinal_value"),
                    "note": item.get("explanation", ""),
                }
                for item in run.get("criterion_assessments", [])
                if item.get("dimension") in {primary_dimension, secondary_dimension}
            ],
        }
        if coverage < coverage_floor or primary.get("score") is None:
            entry["group"] = "additional_review"
            entry["explanation"] = "Недостаточно evidence для корректной позиции в рейтинге."
            additional.append(entry)
        else:
            entry["explanation"] = "Позиция рассчитана только по заранее утверждённым измерениям."
            ranked.append(entry)

    def sort_key(item: dict[str, Any]):
        primary = round(float(item["primary_value"]), precision)
        secondary = item.get("secondary_value")
        secondary_value = round(float(secondary), precision) if secondary is not None else -1.0
        return (-primary, -secondary_value, item["assessment_run_id"])

    ranked.sort(key=sort_key)
    previous_values = None
    for index, entry in enumerate(ranked, start=1):
        values = (
            round(float(entry["primary_value"]), precision),
            round(float(entry["secondary_value"]), precision)
            if entry.get("secondary_value") is not None
            else None,
        )
        if values != previous_values:
            current_rank = index
        entry["rank"] = current_rank
        if previous_values == values:
            entry["explanation"] += " Результат равен другому кандидату; позиция общая."
        previous_values = values
    additional.sort(key=lambda item: item["assessment_run_id"])
    return {
        "id": snapshot_id,
        "vacancy_id": vacancy_id,
        "ranking_policy": policy,
        "compatibility_key": next(iter(compatibility_keys)),
        "entries": ranked + additional,
        "created_at": utc_now(),
        "content_hash": canonical_hash({"policy": policy, "entries": ranked + additional}),
    }
