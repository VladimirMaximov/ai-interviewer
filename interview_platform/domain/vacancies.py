"""Vacancy context, approval, and immutable assessment-snapshot models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ConflictError, ValidationError
from .hiring import canonical_hash, forbidden_criterion_terms, required_text, to_primitive


class VacancyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class SourceType(StrEnum):
    DEFAULT_SELECTION = "default_selection"
    PHRASE = "phrase"
    PASTED_TEXT = "pasted_text"
    FILE = "file"
    SPEECH_TRANSCRIPT = "speech_transcript"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class CriterionCategory(StrEnum):
    MUST_HAVE = "must_have"
    PRIORITY = "priority"
    ADDITIONAL = "additional"


@dataclass(slots=True)
class Vacancy:
    id: str
    title: str
    role_key: str
    target_level_key: str
    owner_actor_id: str
    status: VacancyStatus
    framework_id: str
    active_profile_version_id: str | None
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        self.title = required_text(self.title, "title", 120)
        self.role_key = required_text(self.role_key, "role_key", 120)
        self.target_level_key = required_text(self.target_level_key, "target_level_key", 80)
        self.owner_actor_id = required_text(self.owner_actor_id, "owner_actor_id", 120)

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @classmethod
    def from_dict(cls, value: dict) -> "Vacancy":
        return cls(**{**value, "status": VacancyStatus(value["status"])})


@dataclass(frozen=True, slots=True)
class ContextSource:
    id: str
    vacancy_id: str
    source_type: SourceType
    display_name: str
    media_type: str | None
    extracted_text: str
    content_hash: str
    status: str
    fragments: tuple[dict[str, Any], ...]
    created_by: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @classmethod
    def from_dict(cls, value: dict) -> "ContextSource":
        return cls(
            **{
                **value,
                "source_type": SourceType(value["source_type"]),
                "fragments": tuple(value.get("fragments", [])),
            }
        )


@dataclass(frozen=True, slots=True)
class VacancyCriterion:
    id: str
    code: str
    display_name: str
    description: str
    category: CriterionCategory
    weight: int
    target_depth: str
    positive_anchors: tuple[str, ...]
    negative_anchors: tuple[str, ...]
    accepted_alternatives: tuple[str, ...]
    insufficient_information_rule: str
    linked_competency_ids: tuple[str, ...]
    source_fragment_ids: tuple[str, ...]
    suggestion_confirmed: bool
    question_prompt: str

    def __post_init__(self) -> None:
        required_text(self.display_name, "display_name", 160)
        required_text(self.description, "description", 2_000)
        required_text(self.target_depth, "target_depth", 1_000)
        if not isinstance(self.question_prompt, str) or len(self.question_prompt) > 1_000:
            raise ValidationError("question_prompt must be a string up to 1000 characters")
        if not 1 <= self.weight <= 5:
            raise ValidationError("criterion weight must be between 1 and 5")
        if not self.positive_anchors or not self.negative_anchors:
            raise ValidationError("criterion requires positive and negative anchors")
        required_text(
            self.insufficient_information_rule,
            "insufficient_information_rule",
            1_000,
        )

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @classmethod
    def from_dict(cls, value: dict) -> "VacancyCriterion":
        tuple_fields = (
            "positive_anchors",
            "negative_anchors",
            "accepted_alternatives",
            "linked_competency_ids",
            "source_fragment_ids",
        )
        prepared = dict(value)
        prepared["category"] = CriterionCategory(value["category"])
        for name in tuple_fields:
            prepared[name] = tuple(value.get(name, []))
        return cls(**prepared)


@dataclass(slots=True)
class VacancyProfileVersion:
    id: str
    vacancy_id: str
    framework_id: str
    version: int
    status: ProfileStatus
    summary: str
    criteria: tuple[VacancyCriterion, ...]
    validation_issues: tuple[dict[str, Any], ...]
    source_ids: tuple[str, ...]
    content_hash: str
    created_by: str
    created_at: str
    approved_by: str | None = None
    approved_at: str | None = None

    def __post_init__(self) -> None:
        self.summary = required_text(self.summary, "summary", 4_000)
        if self.version < 1:
            raise ValidationError("profile version must be positive")
        if not self.criteria:
            raise ValidationError("profile requires at least one criterion")

    def validate_for_approval(self) -> tuple[dict[str, Any], ...]:
        issues: list[dict[str, Any]] = []
        seen_codes: set[str] = set()
        for criterion in self.criteria:
            combined = " ".join(
                (
                    criterion.display_name,
                    criterion.description,
                    criterion.target_depth,
                    *criterion.positive_anchors,
                    *criterion.negative_anchors,
                )
            )
            forbidden = forbidden_criterion_terms(combined)
            if forbidden:
                issues.append(
                    {
                        "code": "prohibited_trait",
                        "severity": "blocking",
                        "criterion_id": criterion.id,
                        "message": f"Запрещённые признаки: {', '.join(forbidden)}",
                    }
                )
            if criterion.code in seen_codes:
                issues.append(
                    {
                        "code": "duplicate_code",
                        "severity": "blocking",
                        "criterion_id": criterion.id,
                        "message": "Код критерия дублируется.",
                    }
                )
            seen_codes.add(criterion.code)
            if not criterion.question_prompt.strip():
                issues.append(
                    {
                        "code": "missing_question_coverage",
                        "severity": "blocking",
                        "criterion_id": criterion.id,
                        "message": "Критерий не покрыт вопросом.",
                    }
                )
            if not criterion.source_fragment_ids and not criterion.suggestion_confirmed:
                issues.append(
                    {
                        "code": "unconfirmed_suggestion",
                        "severity": "blocking",
                        "criterion_id": criterion.id,
                        "message": "Системное предложение не подтверждено менеджером.",
                    }
                )
        return tuple(issues)

    def approve(self, *, actor_id: str, approved_at: str) -> None:
        if self.status not in {ProfileStatus.DRAFT, ProfileStatus.VALIDATION_FAILED}:
            raise ConflictError("only a draft profile can be approved")
        issues = self.validate_for_approval()
        self.validation_issues = issues
        if any(item["severity"] == "blocking" for item in issues):
            self.status = ProfileStatus.VALIDATION_FAILED
            raise ValidationError("profile has blocking validation issues", details={"issues": list(issues)})
        self.status = ProfileStatus.APPROVED
        self.approved_by = actor_id
        self.approved_at = approved_at
        self.content_hash = canonical_hash(
            {
                "framework_id": self.framework_id,
                "summary": self.summary,
                "criteria": [item.to_dict() for item in self.criteria],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @classmethod
    def from_dict(cls, value: dict) -> "VacancyProfileVersion":
        prepared = dict(value)
        prepared["status"] = ProfileStatus(value["status"])
        prepared["criteria"] = tuple(
            VacancyCriterion.from_dict(item) for item in value.get("criteria", [])
        )
        prepared["validation_issues"] = tuple(value.get("validation_issues", []))
        prepared["source_ids"] = tuple(value.get("source_ids", []))
        return cls(**prepared)


@dataclass(frozen=True, slots=True)
class AssessmentContextSnapshot:
    id: str
    vacancy_id: str
    framework_id: str
    framework_version: int
    role_key: str
    target_level_key: str
    profile_version_id: str
    profile_version: int
    ranking_policy: dict[str, Any]
    feedback_policy: dict[str, Any]
    criteria: tuple[dict[str, Any], ...]
    questions: tuple[dict[str, Any], ...]
    context_hash: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)

    @classmethod
    def from_dict(cls, value: dict) -> "AssessmentContextSnapshot":
        return cls(
            **{
                **value,
                "criteria": tuple(value.get("criteria", [])),
                "questions": tuple(value.get("questions", [])),
            }
        )
