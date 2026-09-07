"""Safe runtime boundary for a future clarification agent.

The current adapter returns a valid empty decision and makes no external call.
"""

from datetime import datetime, timezone
import logging
from typing import Callable, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.interview_config import QuestionKind, invitation_input
from app.models.interview import (
    CandidateResponse,
    CodeAnswer,
    FollowUpStatus,
    InterviewFollowUpQuestion,
    InterviewInvitation,
    InterviewSession,
    RuntimeEvaluationJob,
    RuntimeEvaluationStatus,
)
from app.domain.multi_agent import AnswerAssessmentOutput


logger = logging.getLogger(__name__)


class RuntimeEvaluationRequest(BaseModel):
    response_id: UUID
    question_id: UUID
    question_text: str
    answer_kind: QuestionKind
    spoken_text: str
    source_code: str | None = None
    language: str | None = None

    @model_validator(mode="after")
    def coding_answer_includes_source(self) -> "RuntimeEvaluationRequest":
        if self.answer_kind is QuestionKind.CODING and not self.source_code:
            raise ValueError("coding answer requires source code")
        return self


class RuntimeEvaluationDecision(BaseModel):
    confidence: float | None = Field(default=None, ge=0, le=1)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=2)


class RuntimeEvaluator(Protocol):
    def evaluate(self, request: RuntimeEvaluationRequest) -> RuntimeEvaluationDecision: ...


class ZeroFollowUpStub:
    def evaluate(self, request: RuntimeEvaluationRequest) -> RuntimeEvaluationDecision:
        return RuntimeEvaluationDecision()


class MultiAgentRuntimeEvaluator:
    """Adapt the durable multi-agent harness to the live interview worker."""

    def __init__(self, harness_factory: Callable[[], object]) -> None:
        self.harness_factory = harness_factory

    def evaluate(self, request: RuntimeEvaluationRequest) -> RuntimeEvaluationDecision:
        harness = self.harness_factory()
        try:
            with harness.db.no_autoflush:
                response = harness.db.get(CandidateResponse, request.response_id)
                interview = harness.db.get(InterviewSession, response.session_id)
                invitation = harness.db.get(InterviewInvitation, interview.invitation_id)
            vacancy_id = invitation.vacancy_id
            invitation_id = invitation.id
            harness.create_session(
                vacancy_id=vacancy_id,
                invitation_id=invitation_id,
                actor_id="interview-runtime",
                idempotency_key=f"runtime-session-{invitation_id}",
            )
            try:
                harness.run_resume_analysis(
                    vacancy_id=vacancy_id,
                    invitation_id=invitation_id,
                    idempotency_key=f"runtime-resume-{invitation_id}",
                )
            except Exception as error:
                if "already" not in str(error).lower():
                    raise
            try:
                harness.run_question_plan(
                    vacancy_id=vacancy_id,
                    invitation_id=invitation_id,
                    idempotency_key=f"runtime-plan-{invitation_id}",
                )
            except Exception as error:
                if "already" not in str(error).lower():
                    raise
            artifact = harness.assess_answer(
                vacancy_id=vacancy_id,
                invitation_id=invitation_id,
                response_id=request.response_id,
                idempotency_key=f"runtime-answer-{request.response_id}",
            )
            assessment = AnswerAssessmentOutput.model_validate(artifact.payload)
            confidences = [item.confidence for item in assessment.observations]
            return RuntimeEvaluationDecision(
                confidence=(sum(confidences) / len(confidences) if confidences else None),
                follow_up_questions=[item.prompt for item in assessment.follow_up or []],
            )
        finally:
            harness.close()


class RuntimeEvaluationService:
    def __init__(self, sessions: sessionmaker, evaluator: RuntimeEvaluator | None = None, presenter_dispatcher: object | None = None, finalizer: Callable[[UUID], None] | None = None) -> None:
        self.sessions, self.evaluator = sessions, evaluator or ZeroFollowUpStub()
        self.presenter_dispatcher = presenter_dispatcher
        self.finalizer = finalizer

    def evaluate_completed_response(self, response_id: UUID) -> None:
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if not response:
                return
            session = db.get(InterviewSession, response.session_id)
            invitation = db.get(InterviewInvitation, session.invitation_id) if session else None
            if not invitation:
                return
            configured = invitation_input(invitation.question_config, invitation.follow_up_after_all_answers)
            question = next((item for item in configured.questions if item.id == response.question_id), None)
            if not question:
                return
            spoken_text = response.transcript_text
            language = None
            source_code = None
            if question.kind is QuestionKind.CODING:
                code_answer = db.scalar(
                    select(CodeAnswer).where(CodeAnswer.response_id == response.id)
                )
                if not code_answer:
                    return
                source_code, language = code_answer.source_code, code_answer.language
            # Both spoken and coding answers retain the candidate's voice. A
            # coding answer is evaluated only once that recording interval has
            # also been transcribed, so no evidence channel is silently lost.
            if not spoken_text:
                return
            job = db.scalar(select(RuntimeEvaluationJob).where(RuntimeEvaluationJob.response_id == response.id))
            if job and job.status is RuntimeEvaluationStatus.COMPLETED:
                return
            if job is None:
                job = RuntimeEvaluationJob(
                    response_id=response.id,
                    status=RuntimeEvaluationStatus.PENDING,
                    question_text=question.text,
                    answer_text=spoken_text,
                    spoken_text=spoken_text,
                    source_code=source_code,
                    language=language,
                    requested_at=datetime.now(timezone.utc),
                )
                db.add(job)
            else:
                job.status = RuntimeEvaluationStatus.PENDING
                job.requested_at = datetime.now(timezone.utc)
                job.completed_at = None
            try:
                decision = self.evaluator.evaluate(RuntimeEvaluationRequest(
                    response_id=response.id, question_id=question.id, question_text=question.text,
                    answer_kind=question.kind,
                    spoken_text=spoken_text,
                    source_code=source_code,
                    language=language,
                ))
                if len(decision.follow_up_questions) > 2 or any(not item.strip() for item in decision.follow_up_questions):
                    raise ValueError("invalid follow-up decision")
                job.confidence = str(decision.confidence) if decision.confidence is not None else None
                existing = list(db.scalars(
                    select(InterviewFollowUpQuestion).where(
                        InterviewFollowUpQuestion.session_id == session.id,
                        InterviewFollowUpQuestion.source_response_id == response.id,
                    )
                ))
                # A source answer has a lifetime budget of two clarifications.
                # The candidate never sees confidence or this internal decision.
                created_follow_ups = []
                for text in decision.follow_up_questions[:max(0, 2 - len(existing))]:
                    follow_up = InterviewFollowUpQuestion(
                        session_id=session.id,
                        source_response_id=response.id,
                        text=text.strip(),
                        status=FollowUpStatus.READY,
                        transcript_snapshot=spoken_text,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(follow_up)
                    created_follow_ups.append(follow_up)
                job.status = RuntimeEvaluationStatus.COMPLETED
            except Exception:
                logger.exception("Runtime answer evaluation failed")
                job.status = RuntimeEvaluationStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            if job.status is RuntimeEvaluationStatus.COMPLETED and self.presenter_dispatcher:
                for follow_up in created_follow_ups:
                    try:
                        self.presenter_dispatcher.enqueue(
                            invitation.id, follow_up.id, follow_up.text
                        )
                    except Exception:
                        pass
            if job.status is RuntimeEvaluationStatus.COMPLETED and self.finalizer:
                self.finalizer(response.id)
