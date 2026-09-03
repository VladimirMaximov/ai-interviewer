"""Append-only, candidate-safe feedback timeline primitives."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .errors import ConflictError, ValidationError
from .hiring import new_id, required_text, utc_now


class FeedbackStage(StrEnum):
    POST_ASYNC_ASSESSMENT = "post_async_assessment"
    POST_HUMAN_REVIEW = "post_human_review"


class FeedbackSourceKind(StrEnum):
    AI_ASSISTED = "ai_assisted"
    HUMAN_AUTHORED = "human_authored"
    CORRECTIVE = "corrective"


class FeedbackStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


CANDIDATE_VISIBLE_FIELDS = (
    "assessment_scope",
    "strengths",
    "growth_areas",
    "evidence_gaps",
    "limitations",
    "next_steps",
)


def _text_list(value: list[str] | tuple[str, ...], name: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{name} must be a list", details={"field": name})
    return [required_text(item, name, 2_000) for item in value]


def create_feedback_revision(
    *,
    revision_number: int,
    actor_id: str,
    assessment_scope: list[str],
    strengths: list[str],
    growth_areas: list[str],
    evidence_gaps: list[str],
    limitations: list[str],
    next_steps: str,
    internal_notes: str,
    assessment_evidence_ids: list[str],
    correction_of_revision_id: str | None = None,
) -> dict[str, Any]:
    if revision_number < 1:
        raise ValidationError("revision_number must be positive")
    if not isinstance(internal_notes, str):
        raise ValidationError("internal_notes must be a string")
    if not isinstance(assessment_evidence_ids, list):
        raise ValidationError("assessment_evidence_ids must be a list")
    return {
        "id": new_id(),
        "revision_number": revision_number,
        "status": FeedbackStatus.DRAFT.value,
        "assessment_scope": _text_list(assessment_scope, "assessment_scope"),
        "strengths": _text_list(strengths, "strengths"),
        "growth_areas": _text_list(growth_areas, "growth_areas"),
        "evidence_gaps": _text_list(evidence_gaps, "evidence_gaps"),
        "limitations": _text_list(limitations, "limitations"),
        "next_steps": required_text(next_steps, "next_steps", 4_000),
        "internal_notes": internal_notes.strip()[:10_000],
        "assessment_evidence_ids": [
            required_text(item, "assessment_evidence_id", 160)
            for item in assessment_evidence_ids
        ],
        "correction_of_revision_id": correction_of_revision_id,
        "created_by": required_text(actor_id, "actor_id", 120),
        "created_at": utc_now(),
        "published_by": None,
        "published_at": None,
    }


def create_feedback_entry(
    *,
    interview_id: str,
    stage: str,
    source_kind: str,
    sequence: int,
    actor_id: str,
    assessment_scope: list[str],
    strengths: list[str],
    growth_areas: list[str],
    evidence_gaps: list[str],
    limitations: list[str],
    next_steps: str,
    internal_notes: str,
    assessment_evidence_ids: list[str],
    correction_of_revision_id: str | None = None,
) -> dict[str, Any]:
    try:
        normalized_stage = FeedbackStage(stage)
        normalized_source = FeedbackSourceKind(source_kind)
    except ValueError as exc:
        raise ValidationError("feedback stage or source kind is invalid") from exc
    if sequence < 1:
        raise ValidationError("feedback sequence must be positive")
    revision = create_feedback_revision(
        revision_number=1,
        actor_id=actor_id,
        assessment_scope=assessment_scope,
        strengths=strengths,
        growth_areas=growth_areas,
        evidence_gaps=evidence_gaps,
        limitations=limitations,
        next_steps=next_steps,
        internal_notes=internal_notes,
        assessment_evidence_ids=assessment_evidence_ids,
        correction_of_revision_id=correction_of_revision_id,
    )
    return {
        "id": new_id(),
        "interview_id": required_text(interview_id, "interview_id", 160),
        "stage": normalized_stage.value,
        "source_kind": normalized_source.value,
        "sequence": sequence,
        "revisions": [revision],
        "created_by": required_text(actor_id, "actor_id", 120),
        "created_at": utc_now(),
    }


def append_feedback_revision(
    entry: dict[str, Any],
    *,
    actor_id: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    revisions = list(entry.get("revisions", []))
    if revisions and revisions[-1]["status"] == FeedbackStatus.DRAFT.value:
        raise ConflictError("publish or discard the current draft before adding a revision")
    revision = create_feedback_revision(
        revision_number=len(revisions) + 1,
        actor_id=actor_id,
        assessment_scope=content.get("assessment_scope", []),
        strengths=content.get("strengths", []),
        growth_areas=content.get("growth_areas", []),
        evidence_gaps=content.get("evidence_gaps", []),
        limitations=content.get("limitations", []),
        next_steps=content.get("next_steps", ""),
        internal_notes=content.get("internal_notes", ""),
        assessment_evidence_ids=content.get("assessment_evidence_ids", []),
        correction_of_revision_id=content.get("correction_of_revision_id"),
    )
    return {**entry, "revisions": [*revisions, revision]}


def publish_feedback_revision(
    entry: dict[str, Any], revision_id: str, *, actor_id: str
) -> dict[str, Any]:
    if actor_id == "system":
        raise ValidationError("personalized feedback requires human publication")
    revisions = [dict(item) for item in entry.get("revisions", [])]
    selected = next((item for item in revisions if item["id"] == revision_id), None)
    if selected is None:
        raise ValidationError("feedback revision not found")
    if selected["status"] == FeedbackStatus.PUBLISHED.value:
        return entry
    if selected is not revisions[-1]:
        raise ConflictError("only the latest draft revision can be published")
    selected["status"] = FeedbackStatus.PUBLISHED.value
    selected["published_by"] = required_text(actor_id, "actor_id", 120)
    selected["published_at"] = utc_now()
    return {**entry, "revisions": revisions}


def candidate_feedback_projection(entry: dict[str, Any]) -> dict[str, Any] | None:
    published = [
        revision
        for revision in entry.get("revisions", [])
        if revision.get("status") == FeedbackStatus.PUBLISHED.value
    ]
    if not published:
        return None
    revision = published[-1]
    return {
        "entry_id": entry["id"],
        "stage": entry["stage"],
        "source_kind": entry["source_kind"],
        "sequence": entry["sequence"],
        "revision_id": revision["id"],
        "revision_number": revision["revision_number"],
        **{field: revision[field] for field in CANDIDATE_VISIBLE_FIELDS},
        "correction_of_revision_id": revision["correction_of_revision_id"],
        "published_at": revision["published_at"],
    }
