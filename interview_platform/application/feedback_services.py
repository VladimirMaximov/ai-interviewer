"""Use cases for staged feedback and candidate-safe publication."""

from __future__ import annotations

from typing import Any

from interview_platform.domain.errors import NotFoundError, ValidationError
from interview_platform.domain.feedback import (
    append_feedback_revision,
    candidate_feedback_projection,
    create_feedback_entry,
    publish_feedback_revision,
)


class FeedbackService:
    def __init__(self, repository, interview_service) -> None:
        self.repository = repository
        self.interview_service = interview_service

    def create_preliminary_draft(
        self,
        interview_id: str,
        assessment_run_id: str,
        *,
        idempotency_key: str | None = None,
    ) -> dict:
        self.interview_service.get_manager_interview(interview_id)
        run = self.repository.get_assessment_run(assessment_run_id)
        if run is None or run["interview_id"] != interview_id:
            raise NotFoundError("assessment run not found")
        strengths: list[str] = []
        growth_areas: list[str] = []
        gaps: list[str] = []
        evidence_ids: list[str] = []
        for result in run.get("criterion_assessments", []):
            label = result.get("label")
            name = result.get("criterion_name", result.get("criterion_id", "Критерий"))
            if label in {"demonstrated", "strongly_demonstrated"}:
                strengths.append(f"{name}: подтверждено ответом кандидата.")
            elif label == "insufficient_information":
                gaps.append(f"{name}: недостаточно информации.")
            else:
                growth_areas.append(f"{name}: требуется более конкретный пример.")
            evidence_ids.extend(
                item.get("id", "") for item in result.get("evidence", []) if item.get("id")
            )
        return self.create_entry(
            interview_id,
            stage="post_async_assessment",
            source_kind="ai_assisted",
            actor_id="system",
            assessment_scope=[
                "Предварительная проверка корпоративных компетенций и соответствия вакансии"
            ],
            strengths=strengths,
            growth_areas=growth_areas,
            evidence_gaps=gaps,
            limitations=[
                "Черновик сформирован детерминированным POC-evaluator и требует проверки человеком."
            ],
            next_steps="Менеджер проверит доказательства и решит, публиковать ли этот фидбэк.",
            internal_notes=f"assessment_run_id={assessment_run_id}",
            assessment_evidence_ids=evidence_ids,
            idempotency_key=idempotency_key,
        )

    def create_entry(
        self,
        interview_id: str,
        *,
        stage: str,
        source_kind: str,
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
        idempotency_key: str | None = None,
    ) -> dict:
        self.interview_service.get_manager_interview(interview_id)
        scope = f"create_feedback:{interview_id}"
        if idempotency_key is not None:
            if len(idempotency_key.strip()) < 8 or len(idempotency_key) > 128:
                raise ValidationError("idempotency key must contain 8 to 128 characters")
            previous = self.repository.get_idempotent_result(idempotency_key, scope)
            if previous is not None:
                return previous
        existing = self.repository.list_feedback_entries(interview_id)
        if correction_of_revision_id is not None:
            published_ids = {
                revision["id"]
                for item in existing
                for revision in item.get("revisions", [])
                if revision.get("status") == "published"
            }
            if correction_of_revision_id not in published_ids:
                raise ValidationError("correction must reference a published revision")
        entry = create_feedback_entry(
            interview_id=interview_id,
            stage=stage,
            source_kind=source_kind,
            sequence=len(existing) + 1,
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
        self.repository.save_feedback_entry(entry)
        if idempotency_key is not None:
            self.repository.save_idempotent_result(idempotency_key, scope, entry)
        return entry

    def add_revision(
        self, interview_id: str, entry_id: str, *, actor_id: str, content: dict[str, Any]
    ) -> dict:
        entry = self._entry(interview_id, entry_id)
        updated = append_feedback_revision(entry, actor_id=actor_id, content=content)
        self.repository.save_feedback_entry(updated)
        return updated

    def publish_revision(
        self,
        interview_id: str,
        entry_id: str,
        revision_id: str,
        *,
        actor_id: str,
    ) -> dict:
        entry = self._entry(interview_id, entry_id)
        updated = publish_feedback_revision(entry, revision_id, actor_id=actor_id)
        self.repository.save_feedback_entry(updated)
        return updated

    def list_entries(self, interview_id: str) -> list[dict]:
        self.interview_service.get_manager_interview(interview_id)
        return self.repository.list_feedback_entries(interview_id)

    def candidate_timeline(self, invitation_token: str) -> dict[str, Any]:
        interview = self.interview_service.get_candidate_interview(invitation_token)
        visible = [
            candidate_feedback_projection(entry)
            for entry in self.repository.list_feedback_entries(interview.id)
        ]
        return {
            "interview_id": interview.id,
            "status": (
                "published" if any(item is not None for item in visible) else "pending_review"
            ),
            "feedback_entries": [item for item in visible if item is not None],
        }

    def _entry(self, interview_id: str, entry_id: str) -> dict:
        self.interview_service.get_manager_interview(interview_id)
        entry = self.repository.get_feedback_entry(entry_id)
        if entry is None or entry["interview_id"] != interview_id:
            raise NotFoundError("feedback entry not found")
        return entry
