"""Interview use cases independent of HTTP and SQLite."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from interview_platform.domain.errors import NotFoundError, ValidationError
from interview_platform.domain.models import (
    Evidence,
    EvidenceKind,
    Feedback,
    Interview,
    InterviewStatus,
    ManagerDecision,
    PublicationStatus,
    Question,
)

from .ports import AnswerCapture, Clock, IdentifierGenerator, InterviewRepository, TokenGenerator


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class UUIDIdentifierGenerator:
    def new_id(self) -> str:
        return str(uuid.uuid4())


class SecureTokenGenerator:
    def new_token(self) -> str:
        return secrets.token_urlsafe(32)


@dataclass(frozen=True, slots=True)
class CreatedInterview:
    interview: Interview
    invitation_token: str


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        capture: AnswerCapture,
        *,
        clock: Clock | None = None,
        identifiers: IdentifierGenerator | None = None,
        tokens: TokenGenerator | None = None,
    ) -> None:
        self.repository = repository
        self.capture = capture
        self.clock = clock or SystemClock()
        self.identifiers = identifiers or UUIDIdentifierGenerator()
        self.tokens = tokens or SecureTokenGenerator()

    def create_interview(
        self,
        *,
        candidate_alias: str,
        position_title: str,
        questions: list[dict[str, Any]],
        invitation_token: str | None = None,
    ) -> CreatedInterview:
        if not isinstance(questions, list) or not questions:
            raise ValidationError("questions must be a non-empty list", details={"field": "questions"})
        if len(questions) > 20:
            raise ValidationError("questions cannot contain more than 20 items")
        interview_id = self.identifiers.new_id()
        now = self.clock.now()
        domain_questions = []
        for position, raw in enumerate(questions, start=1):
            if not isinstance(raw, dict):
                raise ValidationError("each question must be an object")
            prompt = raw.get("prompt")
            if not isinstance(prompt, str):
                raise ValidationError("question prompt must be a string")
            required = raw.get("required", True)
            if not isinstance(required, bool):
                raise ValidationError("question required must be a boolean")
            domain_questions.append(
                Question(
                    id=self.identifiers.new_id(),
                    interview_id=interview_id,
                    prompt=prompt,
                    position=position,
                    required=required,
                )
            )
        raw_token = invitation_token or self.tokens.new_token()
        if len(raw_token) < 32:
            raise ValidationError("invitation token must contain at least 32 characters")
        interview = Interview(
            id=interview_id,
            candidate_alias=candidate_alias,
            position_title=position_title,
            invitation_token_digest=token_digest(raw_token),
            questions=tuple(domain_questions),
            status=InterviewStatus.INVITED,
            evidence_type="synthetic",
            consent_given_at=None,
            started_at=None,
            submitted_at=None,
            reviewed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.repository.create(interview)
        return CreatedInterview(interview=interview, invitation_token=raw_token)

    def get_candidate_interview(self, token: str) -> Interview:
        if not token:
            raise NotFoundError("interview not found")
        interview = self.repository.get_by_token_digest(token_digest(token))
        if interview is None:
            raise NotFoundError("interview not found")
        return interview

    def start_interview(self, token: str, *, consent: bool) -> Interview:
        interview = self.get_candidate_interview(token)
        interview.start(consent=consent, now=self.clock.now())
        self.repository.save(interview)
        return interview

    def save_answer(self, token: str, *, question_id: str, content: str) -> Interview:
        interview = self.get_candidate_interview(token)
        captured = self.capture.capture(content)
        interview.save_answer(
            question_id=question_id,
            capture_kind=captured.capture_kind,
            content=captured.content,
            media_reference=captured.media_reference,
            now=self.clock.now(),
        )
        self.repository.save(interview)
        return interview

    def complete_interview(self, token: str) -> Interview:
        interview = self.get_candidate_interview(token)
        interview.complete(now=self.clock.now())
        self.repository.save(interview)
        return interview

    def list_interviews(self) -> list[Interview]:
        return self.repository.list_interviews()

    def get_manager_interview(self, interview_id: str) -> Interview:
        interview = self.repository.get_by_id(interview_id)
        if interview is None:
            raise NotFoundError("interview not found")
        return interview

    def save_feedback(
        self,
        interview_id: str,
        *,
        candidate_summary: str,
        strengths: list[str] | tuple[str, ...],
        risks: list[str] | tuple[str, ...],
        next_steps: str,
        internal_notes: str,
        manager_decision: str,
        evidence: list[dict[str, Any]],
        publish: bool,
    ) -> Interview:
        interview = self.get_manager_interview(interview_id)
        if not isinstance(publish, bool):
            raise ValidationError("publish must be a boolean")
        if not isinstance(strengths, (list, tuple)) or not isinstance(risks, (list, tuple)):
            raise ValidationError("strengths and risks must be lists")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError("feedback requires at least one evidence item")
        try:
            decision = ManagerDecision(manager_decision)
        except ValueError as exc:
            raise ValidationError("manager_decision is invalid") from exc

        now = self.clock.now()
        feedback_id = interview.feedback.id if interview.feedback else self.identifiers.new_id()
        evidence_items = []
        for raw in evidence:
            if not isinstance(raw, dict):
                raise ValidationError("each evidence item must be an object")
            try:
                kind = EvidenceKind(str(raw.get("kind", "")))
            except ValueError as exc:
                raise ValidationError("evidence kind is invalid") from exc
            evidence_items.append(
                Evidence(
                    id=self.identifiers.new_id(),
                    feedback_id=feedback_id,
                    kind=kind,
                    question_id=str(raw.get("question_id", "")),
                    excerpt=raw.get("excerpt"),
                    note=str(raw.get("note", "")),
                )
            )
        publication = PublicationStatus.PUBLISHED if publish else PublicationStatus.DRAFT
        feedback = Feedback(
            id=feedback_id,
            interview_id=interview.id,
            candidate_summary=candidate_summary,
            strengths=tuple(str(item) for item in strengths),
            risks=tuple(str(item) for item in risks),
            next_steps=next_steps,
            internal_notes=internal_notes,
            ai_recommendation=None,
            recruiter_decision=None,
            manager_decision=decision,
            publication_status=publication,
            evidence=tuple(evidence_items),
            version=(interview.feedback.version + 1) if interview.feedback else 1,
            published_at=now if publish else None,
            updated_at=now,
        )
        interview.set_feedback(feedback, now=now)
        self.repository.save(interview)
        return interview
