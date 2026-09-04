"""Append-only, human-owned hiring decisions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .hiring import ActorRole, new_id, required_text, utc_now


class DecisionValue(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"
    REQUEST_MORE_EVIDENCE = "request_more_evidence"


def create_human_decision(
    *,
    interview_id: str,
    actor_id: str,
    actor_role: str,
    decision: str,
    reason: str,
    evidence_reference_ids: list[str] | None = None,
    supersedes_decision_id: str | None = None,
) -> dict[str, Any]:
    try:
        role = ActorRole(actor_role)
    except ValueError as exc:
        raise ValidationError("actor_role is invalid") from exc
    if role is ActorRole.SYSTEM:
        raise ValidationError("automated actors cannot create hiring decisions")
    try:
        value = DecisionValue(decision)
    except ValueError as exc:
        raise ValidationError("decision is invalid") from exc
    return {
        "id": new_id(),
        "interview_id": required_text(interview_id, "interview_id", 160),
        "actor_id": required_text(actor_id, "actor_id", 120),
        "actor_role": role.value,
        "decision": value.value,
        "reason": required_text(reason, "reason", 4_000),
        "evidence_reference_ids": list(evidence_reference_ids or []),
        "supersedes_decision_id": supersedes_decision_id,
        "created_at": utc_now(),
    }
