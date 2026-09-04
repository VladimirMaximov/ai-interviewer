"""Independent recruiter and hiring-manager review records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .errors import ValidationError
from .models import EvidenceKind, ManagerDecision, PublicationStatus


class RecruiterDecision(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"


def _text(value: str, field: str, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    result = value.strip()
    if required and not result:
        raise ValidationError(f"{field} is required")
    if len(result) > maximum:
        raise ValidationError(f"{field} is too long")
    return result


def _items(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(not isinstance(item, str) for item in values):
        raise ValidationError(f"{field} must be a list of strings")
    return tuple(_text(item, field, 1_000) for item in values if item.strip())


@dataclass(frozen=True, slots=True)
class ReviewEvidence:
    id: str
    review_id: str
    kind: EvidenceKind
    question_id: str
    excerpt: str | None
    note: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "note", _text(self.note, "evidence note", 2_000))
        if self.excerpt is not None and not isinstance(self.excerpt, str):
            raise ValidationError("evidence excerpt must be a string or null")
        excerpt = self.excerpt.strip() if self.excerpt else None
        object.__setattr__(self, "excerpt", excerpt)
        if self.kind is EvidenceKind.ANSWER_EXCERPT and not excerpt:
            raise ValidationError("answer evidence requires an excerpt")
        if self.kind is EvidenceKind.INSUFFICIENT_INFORMATION and excerpt:
            raise ValidationError("insufficient-information evidence cannot contain an excerpt")


@dataclass(frozen=True, slots=True)
class RecruiterReview:
    id: str
    interview_id: str
    candidate_summary: str
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    next_steps: str
    internal_notes: str
    recruiter_decision: RecruiterDecision
    assigned_manager: str | None
    publication_status: PublicationStatus
    evidence: tuple[ReviewEvidence, ...]
    version: int
    published_at: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_summary",
            _text(self.candidate_summary, "candidate_summary", 4_000),
        )
        object.__setattr__(self, "strengths", _items(self.strengths, "strengths"))
        object.__setattr__(self, "risks", _items(self.risks, "risks"))
        object.__setattr__(self, "next_steps", _text(self.next_steps, "next_steps", 2_000))
        object.__setattr__(
            self,
            "internal_notes",
            _text(self.internal_notes, "internal_notes", 4_000, required=False),
        )
        if self.assigned_manager is not None:
            object.__setattr__(
                self,
                "assigned_manager",
                _text(self.assigned_manager, "assigned_manager", 120),
            )
        if not self.evidence:
            raise ValidationError("recruiter review requires at least one evidence item")
        if any(item.review_id != self.id for item in self.evidence):
            raise ValidationError("evidence belongs to another recruiter review")
        if self.version < 1:
            raise ValidationError("review version must be positive")
        if self.publication_status is PublicationStatus.PUBLISHED and self.published_at is None:
            raise ValidationError("published recruiter review requires published_at")


@dataclass(frozen=True, slots=True)
class ManagerReview:
    id: str
    interview_id: str
    manager_id: str
    manager_decision: ManagerDecision
    notes: str
    reviewed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "manager_id", _text(self.manager_id, "manager_id", 120))
        object.__setattr__(self, "notes", _text(self.notes, "manager notes", 4_000))
