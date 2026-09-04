"""Compatible ranking and role-separated human decision use cases."""

from __future__ import annotations

from interview_platform.domain.decisions import create_human_decision
from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.domain.hiring import new_id
from interview_platform.domain.ranking import build_ranking_snapshot


class RankingService:
    def __init__(self, repository, interview_service) -> None:
        self.repository = repository
        self.interview_service = interview_service

    def create_snapshot(
        self,
        vacancy_id: str,
        *,
        assessment_run_ids: list[str],
        idempotency_key: str,
    ) -> dict:
        if len(idempotency_key.strip()) < 8:
            raise ValidationError("idempotency key must contain at least 8 characters")
        existing = self.repository.get_ranking_by_idempotency(idempotency_key)
        if existing is not None:
            if existing["vacancy_id"] != vacancy_id:
                raise ConflictError("idempotency key belongs to another vacancy")
            return existing
        runs = []
        snapshots = []
        for run_id in assessment_run_ids:
            run = self.repository.get_assessment_run(run_id)
            if run is None:
                raise NotFoundError("assessment run not found")
            assignment = self.repository.get_assignment(run["interview_id"])
            if assignment is None or assignment["vacancy_id"] != vacancy_id:
                raise ValidationError("assessment run does not belong to vacancy")
            interview = self.interview_service.get_manager_interview(run["interview_id"])
            runs.append({**run, "candidate_alias": interview.candidate_alias})
            snapshot = self.repository.get_snapshot(run["context_snapshot_id"])
            if snapshot is None:
                raise NotFoundError("assessment context snapshot not found")
            snapshots.append(snapshot)
        if not runs:
            raise ValidationError("assessment_run_ids cannot be empty")
        context_ids = {item["id"] for item in snapshots}
        if len(context_ids) != 1:
            raise ValidationError(
                "ranking requires the same assessment context snapshot",
                details={"context_snapshot_ids": sorted(context_ids)},
            )
        result = build_ranking_snapshot(
            vacancy_id,
            runs,
            snapshots[0]["ranking_policy"],
            snapshot_id=new_id(),
        )
        self.repository.save_ranking_snapshot(result, idempotency_key)
        return result

    def get_snapshot(self, vacancy_id: str, snapshot_id: str) -> dict:
        value = self.repository.get_ranking_snapshot(snapshot_id)
        if value is None or value["vacancy_id"] != vacancy_id:
            raise NotFoundError("ranking snapshot not found")
        return value

    def list_snapshots(self, vacancy_id: str) -> list[dict]:
        return self.repository.list_ranking_snapshots(vacancy_id)


class DecisionService:
    def __init__(self, repository, interview_service) -> None:
        self.repository = repository
        self.interview_service = interview_service

    def create_decision(
        self,
        interview_id: str,
        *,
        actor_id: str,
        actor_role: str,
        decision: str,
        reason: str,
        idempotency_key: str,
        evidence_reference_ids: list[str] | None = None,
        supersedes_decision_id: str | None = None,
    ) -> dict:
        self.interview_service.get_manager_interview(interview_id)
        if len(idempotency_key.strip()) < 8:
            raise ValidationError("idempotency key must contain at least 8 characters")
        existing = self.repository.get_decision_by_idempotency(idempotency_key)
        if existing is not None:
            if existing["interview_id"] != interview_id:
                raise ConflictError("idempotency key belongs to another interview")
            return existing
        history = self.repository.list_decisions(interview_id)
        if supersedes_decision_id is not None:
            previous = next(
                (item for item in history if item["id"] == supersedes_decision_id),
                None,
            )
            if previous is None:
                raise ValidationError("superseded decision not found")
            if previous["actor_role"] != actor_role:
                raise ValidationError("decision can supersede only the same actor role")
        result = create_human_decision(
            interview_id=interview_id,
            actor_id=actor_id,
            actor_role=actor_role,
            decision=decision,
            reason=reason,
            evidence_reference_ids=evidence_reference_ids,
            supersedes_decision_id=supersedes_decision_id,
        )
        self.repository.save_decision(result, idempotency_key)
        return result

    def list_decisions(self, interview_id: str) -> list[dict]:
        self.interview_service.get_manager_interview(interview_id)
        return self.repository.list_decisions(interview_id)
