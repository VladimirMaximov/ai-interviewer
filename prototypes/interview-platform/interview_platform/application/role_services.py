"""Use cases enforcing recruiter/manager separation beyond the web UI."""

from __future__ import annotations

from typing import Any

from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.domain.models import (
    EvidenceKind,
    Interview,
    InterviewStatus,
    ManagerDecision,
    PublicationStatus,
)
from interview_platform.domain.roles import (
    ManagerReview,
    RecruiterDecision,
    RecruiterReview,
    ReviewEvidence,
)

from .ports import Clock, IdentifierGenerator
from .role_ports import RoleReviewRepository
from .services import InterviewService, SystemClock, UUIDIdentifierGenerator


class RoleService:
    def __init__(
        self,
        interviews: InterviewService,
        reviews: RoleReviewRepository,
        *,
        clock: Clock | None = None,
        identifiers: IdentifierGenerator | None = None,
    ) -> None:
        self.interviews = interviews
        self.reviews = reviews
        self.clock = clock or SystemClock()
        self.identifiers = identifiers or UUIDIdentifierGenerator()

    def list_for_recruiter(self) -> list[Interview]:
        return self.interviews.list_interviews()

    def get_for_recruiter(self, interview_id: str) -> Interview:
        return self.interviews.get_manager_interview(interview_id)

    def recruiter_review(self, interview_id: str) -> RecruiterReview | None:
        self.get_for_recruiter(interview_id)
        return self.reviews.get_recruiter_review(interview_id)

    def save_recruiter_review(
        self,
        interview_id: str,
        *,
        candidate_summary: str,
        strengths: list[str],
        risks: list[str],
        next_steps: str,
        internal_notes: str,
        recruiter_decision: str,
        assigned_manager: str | None,
        evidence: list[dict[str, Any]],
        publish: bool,
    ) -> RecruiterReview:
        interview = self.get_for_recruiter(interview_id)
        if interview.status not in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
            raise ConflictError("recruiter review requires a submitted interview")
        if not isinstance(strengths, list) or not isinstance(risks, list):
            raise ValidationError("strengths and risks must be lists")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError("recruiter review requires evidence")
        if not isinstance(publish, bool):
            raise ValidationError("publish must be a boolean")
        try:
            decision = RecruiterDecision(recruiter_decision)
        except ValueError as exc:
            raise ValidationError("recruiter_decision is invalid") from exc

        previous = self.reviews.get_recruiter_review(interview_id)
        if previous and previous.publication_status is PublicationStatus.PUBLISHED and not publish:
            raise ConflictError("published recruiter feedback cannot become a draft")
        review_id = previous.id if previous else self.identifiers.new_id()
        evidence_items = tuple(
            self._evidence(review_id, interview, raw) for raw in evidence
        )
        now = self.clock.now()
        normalized_manager = assigned_manager.strip() if isinstance(assigned_manager, str) else None
        normalized_manager = normalized_manager or None
        review = RecruiterReview(
            id=review_id,
            interview_id=interview.id,
            candidate_summary=candidate_summary,
            strengths=tuple(strengths),
            risks=tuple(risks),
            next_steps=next_steps,
            internal_notes=internal_notes,
            recruiter_decision=decision,
            assigned_manager=normalized_manager,
            publication_status=(
                PublicationStatus.PUBLISHED if publish else PublicationStatus.DRAFT
            ),
            evidence=evidence_items,
            version=(previous.version + 1) if previous else 1,
            published_at=now if publish else None,
            updated_at=now,
        )
        if previous and previous.assigned_manager != normalized_manager:
            self.reviews.clear_manager_review(interview_id)
        self.reviews.save_recruiter_review(review)
        return review

    def list_for_manager(self, manager_id: str) -> list[Interview]:
        interview_ids = set(self.reviews.assigned_interview_ids(manager_id))
        return [
            interview
            for interview in self.interviews.list_interviews()
            if interview.id in interview_ids
        ]

    def get_for_manager(self, interview_id: str, manager_id: str) -> Interview:
        review = self.reviews.get_recruiter_review(interview_id)
        if review is None or review.assigned_manager != manager_id:
            raise NotFoundError("interview not found")
        return self.interviews.get_manager_interview(interview_id)

    def manager_review(self, interview_id: str, manager_id: str) -> ManagerReview | None:
        self.get_for_manager(interview_id, manager_id)
        return self.reviews.get_manager_review(interview_id)

    def save_manager_review(
        self,
        interview_id: str,
        manager_id: str,
        *,
        manager_decision: str,
        notes: str,
    ) -> ManagerReview:
        self.get_for_manager(interview_id, manager_id)
        try:
            decision = ManagerDecision(manager_decision)
        except ValueError as exc:
            raise ValidationError("manager_decision is invalid") from exc
        previous = self.reviews.get_manager_review(interview_id)
        review = ManagerReview(
            id=previous.id if previous else self.identifiers.new_id(),
            interview_id=interview_id,
            manager_id=manager_id,
            manager_decision=decision,
            notes=notes,
            reviewed_at=self.clock.now(),
        )
        self.reviews.save_manager_review(review)
        return review

    def candidate_feedback(self, token: str) -> dict | None:
        interview = self.interviews.get_candidate_interview(token)
        review = self.reviews.get_recruiter_review(interview.id)
        if review is None or review.publication_status is not PublicationStatus.PUBLISHED:
            return None
        return {
            "candidate_summary": review.candidate_summary,
            "strengths": list(review.strengths),
            "next_steps": review.next_steps,
            "published_at": review.published_at.isoformat(),
            "version": review.version,
        }

    def _evidence(
        self,
        review_id: str,
        interview: Interview,
        raw: dict[str, Any],
    ) -> ReviewEvidence:
        if not isinstance(raw, dict):
            raise ValidationError("each evidence item must be an object")
        try:
            kind = EvidenceKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("evidence kind is invalid") from exc
        question_id = str(raw.get("question_id", ""))
        if question_id not in {question.id for question in interview.questions}:
            raise ValidationError("evidence question belongs to another interview")
        evidence = ReviewEvidence(
            id=self.identifiers.new_id(),
            review_id=review_id,
            kind=kind,
            question_id=question_id,
            excerpt=raw.get("excerpt"),
            note=str(raw.get("note", "")),
        )
        if kind is EvidenceKind.ANSWER_EXCERPT:
            answer = interview.answers.get(question_id)
            if answer is None or evidence.excerpt not in answer.content:
                raise ValidationError("evidence excerpt must occur in the stored answer")
        return evidence
