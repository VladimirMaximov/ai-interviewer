"""Recruiter API for the session-scoped multi-agent interview harness."""

from __future__ import annotations

from typing import Annotated, Iterator, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.api.hiring_context import require_recruiter
from app.api.errors import invalid_invitation
from app.domain.multi_agent import (
    AgentSessionView,
    ArtifactView,
    CreateRestrictionRequest,
    CandidateQuestionPlanView,
    CandidateFeedbackDeliveryView,
    CandidateFeedbackReleaseView,
    FinalizationView,
    MultiAgentConflictError,
    MultiAgentError,
    MultiAgentNotFoundError,
    MultiAgentProviderError,
    MultiAgentValidationError,
    RankingView,
    RestrictionDecisionView,
    RestrictionListView,
)


router = APIRouter(prefix="/recruiter", tags=["multi-agent-harness"])
candidate_router = APIRouter(prefix="/candidate", tags=["candidate-questions"])


class AnswerAssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: UUID


class MultiAgentWorkflow(Protocol):
    def close(self) -> None: ...

    def create_session(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        idempotency_key: str,
    ) -> AgentSessionView: ...

    def get_session(
        self, *, vacancy_id: UUID, invitation_id: UUID
    ) -> AgentSessionView: ...

    def candidate_question_plan(
        self, *, secret: str
    ) -> CandidateQuestionPlanView | None: ...

    def candidate_feedback(
        self, *, secret: str
    ) -> CandidateFeedbackDeliveryView | None: ...

    def run_resume_analysis(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView: ...

    def run_question_plan(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView: ...

    def assess_answer(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        response_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView: ...

    def finalize(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> FinalizationView: ...

    def generate_candidate_feedback(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        idempotency_key: str,
    ) -> CandidateFeedbackReleaseView: ...

    def publish_candidate_feedback(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        release_id: UUID,
        actor_id: str,
    ) -> CandidateFeedbackReleaseView: ...

    def build_ranking(self, *, vacancy_id: UUID) -> RankingView: ...

    def create_restriction(
        self,
        *,
        invitation_id: UUID,
        actor_id: str,
        request: CreateRestrictionRequest,
    ) -> RestrictionDecisionView: ...

    def list_restrictions(
        self, *, invitation_id: UUID
    ) -> RestrictionListView: ...


def get_multi_agent_harness(request: Request) -> Iterator[MultiAgentWorkflow]:
    service = request.app.state.multi_agent_harness_factory()
    try:
        yield service
    finally:
        service.close()


@candidate_router.get(
    "/{secret}/questions",
    response_model=CandidateQuestionPlanView,
)
def get_candidate_questions(
    secret: str,
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> CandidateQuestionPlanView:
    result = service.candidate_question_plan(secret=secret)
    if result is None:
        raise invalid_invitation()
    return result


@candidate_router.get(
    "/{secret}/feedback",
    response_model=CandidateFeedbackDeliveryView,
)
def get_candidate_feedback(
    secret: str,
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> CandidateFeedbackDeliveryView:
    result = service.candidate_feedback(secret=secret)
    if result is None:
        raise invalid_invitation()
    return result


IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
]


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session",
    response_model=AgentSessionView,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_session(
    vacancy_id: UUID,
    invitation_id: UUID,
    idempotency_key: IdempotencyKey,
    actor_id: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> AgentSessionView:
    return service.create_session(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session",
    response_model=AgentSessionView,
)
def get_agent_session(
    vacancy_id: UUID,
    invitation_id: UUID,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> AgentSessionView:
    return service.get_session(vacancy_id=vacancy_id, invitation_id=invitation_id)


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/resume-analysis",
    response_model=ArtifactView,
)
def run_resume_analysis(
    vacancy_id: UUID,
    invitation_id: UUID,
    idempotency_key: IdempotencyKey,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> ArtifactView:
    return service.run_resume_analysis(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/question-plan",
    response_model=ArtifactView,
)
def run_question_plan(
    vacancy_id: UUID,
    invitation_id: UUID,
    idempotency_key: IdempotencyKey,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> ArtifactView:
    return service.run_question_plan(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/answer-assessments",
    response_model=ArtifactView,
)
def run_answer_assessment(
    vacancy_id: UUID,
    invitation_id: UUID,
    payload: AnswerAssessmentRequest,
    idempotency_key: IdempotencyKey,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> ArtifactView:
    return service.assess_answer(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        response_id=payload.response_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/finalize",
    response_model=FinalizationView,
)
def finalize_agent_session(
    vacancy_id: UUID,
    invitation_id: UUID,
    idempotency_key: IdempotencyKey,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> FinalizationView:
    return service.finalize(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/candidate-feedback",
    response_model=CandidateFeedbackReleaseView,
    status_code=status.HTTP_201_CREATED,
)
def generate_candidate_feedback(
    vacancy_id: UUID,
    invitation_id: UUID,
    idempotency_key: IdempotencyKey,
    actor_id: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> CandidateFeedbackReleaseView:
    return service.generate_candidate_feedback(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-session/"
    "candidate-feedback/{release_id}/publish",
    response_model=CandidateFeedbackReleaseView,
)
def publish_candidate_feedback(
    vacancy_id: UUID,
    invitation_id: UUID,
    release_id: UUID,
    actor_id: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> CandidateFeedbackReleaseView:
    return service.publish_candidate_feedback(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        release_id=release_id,
        actor_id=actor_id,
    )


@router.get("/vacancies/{vacancy_id}/ranking", response_model=RankingView)
def get_vacancy_ranking(
    vacancy_id: UUID,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> RankingView:
    return service.build_ranking(vacancy_id=vacancy_id)


@router.post(
    "/applications/{invitation_id}/restrictions",
    response_model=RestrictionDecisionView,
    status_code=status.HTTP_201_CREATED,
)
def create_restriction(
    invitation_id: UUID,
    payload: CreateRestrictionRequest,
    actor_id: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> RestrictionDecisionView:
    return service.create_restriction(
        invitation_id=invitation_id,
        actor_id=actor_id,
        request=payload,
    )


@router.get(
    "/applications/{invitation_id}/restrictions",
    response_model=RestrictionListView,
)
def list_restrictions(
    invitation_id: UUID,
    _: str = Depends(require_recruiter),
    service: MultiAgentWorkflow = Depends(get_multi_agent_harness),
) -> RestrictionListView:
    return service.list_restrictions(invitation_id=invitation_id)


async def multi_agent_exception_handler(
    _: Request, error: MultiAgentError
) -> JSONResponse:
    if isinstance(error, MultiAgentNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, MultiAgentConflictError):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(error, MultiAgentValidationError):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, MultiAgentProviderError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": error.code, "message": error.message}},
    )
