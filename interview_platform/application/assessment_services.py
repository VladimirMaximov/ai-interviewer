"""Assessment run orchestration independent of HTTP and SQLite."""

from __future__ import annotations

from interview_platform.domain.assessment import complete_assessment_run
from interview_platform.domain.errors import ConflictError, NotFoundError, ValidationError
from interview_platform.domain.hiring import new_id, utc_now
from interview_platform.domain.models import InterviewStatus

from .context import AssessmentContextAssembler


class AssessmentService:
    def __init__(self, repository, interview_service, evaluator) -> None:
        self.repository = repository
        self.interview_service = interview_service
        self.evaluator = evaluator
        self.context_assembler = AssessmentContextAssembler()

    def create_run(
        self,
        interview_id: str,
        *,
        reason: str,
        idempotency_key: str,
        integrity_signals: list[dict] | None = None,
    ) -> dict:
        if reason not in {"initial", "manual_retry", "model_change", "policy_replay", "calibration"}:
            raise ValidationError("assessment reason is invalid")
        if not isinstance(idempotency_key, str) or len(idempotency_key.strip()) < 8:
            raise ValidationError("idempotency key must contain at least 8 characters")
        existing = self.repository.get_assessment_by_idempotency(idempotency_key)
        if existing is not None:
            if existing["interview_id"] != interview_id:
                raise ConflictError("idempotency key belongs to another interview")
            return existing
        assignment = self.repository.get_assignment(interview_id)
        if assignment is None:
            raise NotFoundError("vacancy-aware interview assignment not found")
        snapshot = self.repository.get_snapshot(assignment["context_snapshot_id"])
        if snapshot is None:
            raise NotFoundError("assessment context snapshot not found")
        interview = self.interview_service.get_manager_interview(interview_id)
        if interview.status not in {InterviewStatus.SUBMITTED, InterviewStatus.REVIEWED}:
            raise ConflictError("assessment requires a submitted interview")
        bundle = self.context_assembler.build(snapshot, interview)
        if hasattr(self.evaluator, "evaluate_interview"):
            evaluation = self.evaluator.evaluate_interview(bundle)
            results = evaluation["criterion_assessments"]
            baseline_recommendation = evaluation["baseline_recommendation"]
        else:
            results = self.evaluator.evaluate(bundle)
            baseline_recommendation = self.evaluator.recommend(bundle, results)
        answers = {question.id: interview.answers[question.id].content for question in interview.questions}
        previous = self.repository.list_assessment_runs(interview_id)
        created_at = utc_now()
        run = complete_assessment_run(
            run_id=new_id(),
            interview_id=interview_id,
            context_snapshot_id=snapshot["id"],
            context_hash=snapshot["context_hash"],
            run_number=len(previous) + 1,
            reason=reason,
            idempotency_key=idempotency_key,
            evaluator_id=self.evaluator.evaluator_id,
            model_id=self.evaluator.model_id,
            prompt_id=self.evaluator.prompt_id,
            input_hash=bundle["input_hash"],
            raw_results=results,
            baseline_recommendation=baseline_recommendation,
            answers=answers,
            created_at=created_at,
            integrity_signals=integrity_signals,
        )
        self.repository.save_assessment_run(run)
        return run

    def list_runs(self, interview_id: str) -> list[dict]:
        self.interview_service.get_manager_interview(interview_id)
        return self.repository.list_assessment_runs(interview_id)

    def get_run(self, interview_id: str, run_id: str) -> dict:
        run = self.repository.get_assessment_run(run_id)
        if run is None or run["interview_id"] != interview_id:
            raise NotFoundError("assessment run not found")
        return run
