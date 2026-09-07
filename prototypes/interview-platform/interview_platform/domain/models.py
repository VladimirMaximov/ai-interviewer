"""Framework-independent interview aggregate and invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .errors import ConflictError, ValidationError


class InterviewStatus(StrEnum):
    INVITED = "invited"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ManagerDecision(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"


class EvidenceKind(StrEnum):
    ANSWER_EXCERPT = "answer_excerpt"
    INSUFFICIENT_INFORMATION = "insufficient_information"


def _required_text(value: str, name: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string", details={"field": name})
    result = value.strip()
    if not result:
        raise ValidationError(f"{name} is required", details={"field": name})
    if len(result) > maximum:
        raise ValidationError(
            f"{name} is too long",
            details={"field": name, "maximum": maximum},
        )
    return result


def _text_list(values: tuple[str, ...] | list[str], name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or any(not isinstance(item, str) for item in values):
        raise ValidationError(f"{name} must be a list of strings", details={"field": name})
    result = tuple(item.strip() for item in values if item.strip())
    if any(len(item) > 1_000 for item in result):
        raise ValidationError(f"{name} item is too long", details={"field": name})
    return result


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    interview_id: str
    prompt: str
    position: int
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "prompt", _required_text(self.prompt, "prompt", 1_000))
        if self.position < 1:
            raise ValidationError("question position must be positive")


@dataclass(frozen=True, slots=True)
class Answer:
    interview_id: str
    question_id: str
    capture_kind: str
    content: str
    media_reference: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", _required_text(self.content, "content", 10_000))
        if not self.capture_kind:
            raise ValidationError("capture_kind is required")


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    feedback_id: str
    kind: EvidenceKind
    question_id: str
    excerpt: str | None
    note: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "note", _required_text(self.note, "note", 2_000))
        if self.excerpt is not None and not isinstance(self.excerpt, str):
            raise ValidationError("excerpt must be a string or null")
        excerpt = self.excerpt.strip() if self.excerpt else None
        object.__setattr__(self, "excerpt", excerpt)
        if self.kind is EvidenceKind.ANSWER_EXCERPT and not excerpt:
            raise ValidationError("answer evidence requires an excerpt")
        if self.kind is EvidenceKind.INSUFFICIENT_INFORMATION and excerpt:
            raise ValidationError("insufficient information evidence cannot include an excerpt")


@dataclass(frozen=True, slots=True)
class Feedback:
    id: str
    interview_id: str
    candidate_summary: str
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    next_steps: str
    internal_notes: str
    ai_recommendation: str | None
    recruiter_decision: str | None
    manager_decision: ManagerDecision
    publication_status: PublicationStatus
    evidence: tuple[Evidence, ...]
    version: int
    published_at: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_summary",
            _required_text(self.candidate_summary, "candidate_summary", 4_000),
        )
        object.__setattr__(self, "next_steps", _required_text(self.next_steps, "next_steps", 2_000))
        if not isinstance(self.internal_notes, str):
            raise ValidationError("internal_notes must be a string")
        if len(self.internal_notes) > 4_000:
            raise ValidationError("internal_notes is too long")
        object.__setattr__(self, "strengths", _text_list(self.strengths, "strengths"))
        object.__setattr__(self, "risks", _text_list(self.risks, "risks"))
        if not self.evidence:
            raise ValidationError("feedback requires at least one evidence item")
        if self.version < 1:
            raise ValidationError("feedback version must be positive")
        if self.ai_recommendation is not None or self.recruiter_decision is not None:
            raise ValidationError("POC cannot create AI or recruiter decisions")
        if self.publication_status is PublicationStatus.PUBLISHED and self.published_at is None:
            raise ValidationError("published feedback requires published_at")


@dataclass(slots=True)
class Interview:
    id: str
    candidate_alias: str
    position_title: str
    invitation_token_digest: str
    questions: tuple[Question, ...]
    status: InterviewStatus
    evidence_type: str
    consent_given_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    answers: dict[str, Answer] = field(default_factory=dict)
    feedback: Feedback | None = None

    def __post_init__(self) -> None:
        self.candidate_alias = _required_text(self.candidate_alias, "candidate_alias", 120)
        self.position_title = _required_text(self.position_title, "position_title", 120)
        if self.evidence_type != "synthetic":
            raise ValidationError("POC interviews must be marked synthetic")
        if not self.questions:
            raise ValidationError("interview requires at least one question")
        if len(self.questions) > 20:
            raise ValidationError("interview cannot contain more than 20 questions")
        positions = [question.position for question in self.questions]
        if len(positions) != len(set(positions)):
            raise ValidationError("question positions must be unique")
        if any(question.interview_id != self.id for question in self.questions):
            raise ValidationError("question belongs to another interview")

    def start(self, *, consent: bool, now: datetime) -> None:
        if self.status is InterviewStatus.IN_PROGRESS:
            return
        if self.status is not InterviewStatus.INVITED:
            raise ConflictError("interview can no longer be started")
        if not consent:
            raise ValidationError("consent is required", details={"field": "consent"})
        self.consent_given_at = now
        self.started_at = now
        self.updated_at = now
        self.status = InterviewStatus.IN_PROGRESS

    def save_answer(
        self,
        *,
        question_id: str,
        capture_kind: str,
        content: str,
        media_reference: str | None,
        now: datetime,
    ) -> None:
        if self.status is not InterviewStatus.IN_PROGRESS:
            raise ConflictError("answers can only be saved while interview is in progress")
        if question_id not in {question.id for question in self.questions}:
            raise ValidationError("question does not belong to interview")
        self.answers[question_id] = Answer(
            interview_id=self.id,
            question_id=question_id,
            capture_kind=capture_kind,
            content=content,
            media_reference=media_reference,
            updated_at=now,
        )
        self.updated_at = now

    def complete(self, *, now: datetime) -> None:
        if self.status is not InterviewStatus.IN_PROGRESS:
            raise ConflictError("only an interview in progress can be submitted")
        missing = [
            question.id
            for question in self.questions
            if question.required and question.id not in self.answers
        ]
        if missing:
            raise ConflictError(
                "required questions are unanswered",
                details={"missing_question_ids": missing},
            )
        self.status = InterviewStatus.SUBMITTED
        self.submitted_at = now
        self.updated_at = now

    def set_feedback(self, feedback: Feedback, *, now: datetime) -> None:
        if self.status not in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
            raise ConflictError("feedback requires a submitted interview")
        if self.status is InterviewStatus.REVIEWED and (
            feedback.publication_status is not PublicationStatus.PUBLISHED
        ):
            raise ConflictError("published feedback cannot be replaced by a draft")
        if feedback.interview_id != self.id:
            raise ValidationError("feedback belongs to another interview")

        questions = {question.id for question in self.questions}
        for evidence in feedback.evidence:
            if evidence.feedback_id != feedback.id:
                raise ValidationError("evidence belongs to another feedback version")
            if evidence.question_id not in questions:
                raise ValidationError("evidence question belongs to another interview")
            if evidence.kind is EvidenceKind.ANSWER_EXCERPT:
                answer = self.answers.get(evidence.question_id)
                if answer is None or evidence.excerpt not in answer.content:
                    raise ValidationError("evidence excerpt must occur in the stored answer")

        self.feedback = feedback
        self.updated_at = now
        if feedback.publication_status is PublicationStatus.PUBLISHED:
            self.status = InterviewStatus.REVIEWED
            self.reviewed_at = self.reviewed_at or now
