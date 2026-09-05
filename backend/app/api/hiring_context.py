"""Recruiter vacancy uploads, candidate resumes, and agent-context API."""

from __future__ import annotations

import secrets
from typing import Annotated, Iterator, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.errors import invalid_invitation
from app.application.document_extraction import MAX_DOCUMENT_BYTES
from app.config import settings
from app.interview_config import InterviewInput
from app.domain.hiring_context import (
    ApplicationView,
    CandidateConsentRequiredError,
    DocumentTooLargeError,
    HiringContextConflictError,
    HiringContextError,
    HiringContextNotFoundError,
    HiringContextValidationError,
    InterviewAgentContext,
    InvitationCreated,
    ResumeView,
    VacancyView,
)
from app.services.interview_results import InterviewResultDetail, InterviewResultSummary


recruiter_router = APIRouter(prefix="/recruiter", tags=["hiring-context"])
candidate_document_router = APIRouter(prefix="/candidate", tags=["candidate-resume"])
DOCUMENT_BODY_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            media_type: {
                "schema": {
                    "type": "string",
                    "format": "binary",
                    "maxLength": MAX_DOCUMENT_BYTES,
                }
            }
            for media_type in (
                "text/plain",
                "text/markdown",
                "application/pdf",
                (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            )
        },
    }
}


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_alias: str | None = Field(default=None, max_length=120)
    expires_in_hours: int = Field(default=72, ge=1, le=720)


class VacancyList(BaseModel):
    vacancies: list[VacancyView]


class ApplicationList(BaseModel):
    applications: list[ApplicationView]


class InterviewResultList(BaseModel):
    interviews: list[InterviewResultSummary]


class HiringContextWorkflow(Protocol):
    def close(self) -> None: ...

    def create_vacancy(
        self,
        *,
        title: str,
        document: bytes,
        filename: str,
        media_type: str,
        actor_id: str,
        idempotency_key: str,
    ) -> VacancyView: ...

    def list_vacancies(self) -> list[VacancyView]: ...

    def get_vacancy(self, vacancy_id: UUID) -> VacancyView: ...

    def get_interview_configuration(self, vacancy_id: UUID) -> InterviewInput: ...

    def set_interview_configuration(
        self, vacancy_id: UUID, configuration: InterviewInput
    ) -> InterviewInput: ...

    def create_invitation(
        self,
        *,
        vacancy_id: UUID,
        actor_id: str,
        candidate_alias: str | None,
        expires_in_hours: int,
    ) -> InvitationCreated: ...

    def upload_resume(
        self,
        *,
        secret: str,
        document: bytes,
        filename: str,
        media_type: str,
        idempotency_key: str,
    ) -> ResumeView | None: ...

    def recruiter_upload_resume(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        document: bytes,
        filename: str,
        media_type: str,
        idempotency_key: str,
    ) -> ResumeView: ...

    def candidate_resume(self, secret: str) -> ResumeView | None: ...

    def list_applications(self, vacancy_id: UUID) -> list[ApplicationView]: ...

    def build_agent_context(
        self, *, vacancy_id: UUID, invitation_id: UUID
    ) -> InterviewAgentContext: ...


def require_recruiter(
    x_recruiter_key: Annotated[
        str | None, Header(alias="X-Recruiter-Key")
    ] = None,
    x_recruiter_id: Annotated[
        str | None, Header(alias="X-Recruiter-Id")
    ] = None,
) -> str:
    if not settings.recruiter_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Recruiter API is not configured.",
        )
    if x_recruiter_key is None or not secrets.compare_digest(
        x_recruiter_key, settings.recruiter_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Recruiter credentials are invalid.",
        )
    actor_id = (x_recruiter_id or settings.recruiter_id).strip()
    if not actor_id or len(actor_id) > 120:
        raise HTTPException(
            status_code=422,
            detail="Recruiter actor id is invalid.",
        )
    return actor_id


def get_hiring_context_service(request: Request) -> Iterator[HiringContextWorkflow]:
    service = request.app.state.hiring_context_service_factory()
    try:
        yield service
    finally:
        service.close()


def get_interview_results_service(request: Request) -> Iterator[object]:
    service = request.app.state.interview_results_service_factory()
    try:
        yield service
    finally:
        service.close()


async def _document_bytes(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_DOCUMENT_BYTES:
                raise DocumentTooLargeError(
                    f"document exceeds {MAX_DOCUMENT_BYTES} bytes"
                )
        except ValueError as error:
            raise HiringContextValidationError(
                "Content-Length header is invalid"
            ) from error
    result = bytearray()
    async for chunk in request.stream():
        result.extend(chunk)
        if len(result) > MAX_DOCUMENT_BYTES:
            raise DocumentTooLargeError(
                f"document exceeds {MAX_DOCUMENT_BYTES} bytes"
            )
    return bytes(result)


@recruiter_router.post(
    "/vacancies",
    response_model=VacancyView,
    status_code=status.HTTP_201_CREATED,
    summary="Upload one vacancy document",
    openapi_extra=DOCUMENT_BODY_OPENAPI,
)
async def upload_vacancy(
    request: Request,
    vacancy_title: Annotated[
        str, Header(alias="X-Vacancy-Title", min_length=1, max_length=200)
    ],
    document_filename: Annotated[
        str, Header(alias="X-Document-Filename", min_length=1, max_length=255)
    ],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
    actor_id: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> VacancyView:
    return service.create_vacancy(
        title=vacancy_title,
        document=await _document_bytes(request),
        filename=document_filename,
        media_type=request.headers.get("content-type", "application/octet-stream"),
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )


@recruiter_router.get("/vacancies", response_model=VacancyList)
def list_vacancies(
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> VacancyList:
    return VacancyList(vacancies=service.list_vacancies())


@recruiter_router.get("/vacancies/{vacancy_id}", response_model=VacancyView)
def get_vacancy(
    vacancy_id: UUID,
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> VacancyView:
    return service.get_vacancy(vacancy_id)


@recruiter_router.get(
    "/vacancies/{vacancy_id}/interview-configuration",
    response_model=InterviewInput,
)
def get_interview_configuration(
    vacancy_id: UUID,
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> InterviewInput:
    return service.get_interview_configuration(vacancy_id)


@recruiter_router.put(
    "/vacancies/{vacancy_id}/interview-configuration",
    response_model=InterviewInput,
)
def set_interview_configuration(
    vacancy_id: UUID,
    payload: InterviewInput,
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> InterviewInput:
    return service.set_interview_configuration(vacancy_id, payload)


@recruiter_router.post(
    "/vacancies/{vacancy_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    vacancy_id: UUID,
    payload: CreateInvitationRequest,
    actor_id: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> InvitationCreated:
    return service.create_invitation(
        vacancy_id=vacancy_id,
        actor_id=actor_id,
        candidate_alias=payload.candidate_alias,
        expires_in_hours=payload.expires_in_hours,
    )


@recruiter_router.get(
    "/vacancies/{vacancy_id}/interviews", response_model=InterviewResultList,
)
def list_interview_results(
    vacancy_id: UUID, _: str = Depends(require_recruiter),
    service: object = Depends(get_interview_results_service),
) -> InterviewResultList:
    try:
        return InterviewResultList(interviews=service.list_for_vacancy(vacancy_id))
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Vacancy was not found") from error


@recruiter_router.get(
    "/vacancies/{vacancy_id}/interviews/{session_id}",
    response_model=InterviewResultDetail,
)
def get_interview_result(
    vacancy_id: UUID, session_id: UUID,
    _: str = Depends(require_recruiter),
    service: object = Depends(get_interview_results_service),
) -> InterviewResultDetail:
    try:
        return service.detail(vacancy_id, session_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="Interview was not found") from error


@recruiter_router.get(
    "/vacancies/{vacancy_id}/applications",
    response_model=ApplicationList,
)
def list_applications(
    vacancy_id: UUID,
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> ApplicationList:
    return ApplicationList(applications=service.list_applications(vacancy_id))


@recruiter_router.post(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/resume",
    response_model=ResumeView,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or replace a candidate resume as a recruiter",
    openapi_extra=DOCUMENT_BODY_OPENAPI,
)
async def upload_resume_as_recruiter(
    vacancy_id: UUID,
    invitation_id: UUID,
    request: Request,
    document_filename: Annotated[
        str, Header(alias="X-Document-Filename", min_length=1, max_length=255)
    ],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
    actor_id: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> ResumeView:
    return service.recruiter_upload_resume(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
        actor_id=actor_id,
        document=await _document_bytes(request),
        filename=document_filename,
        media_type=request.headers.get("content-type", "application/octet-stream"),
        idempotency_key=idempotency_key,
    )


@recruiter_router.get(
    "/vacancies/{vacancy_id}/applications/{invitation_id}/agent-context",
    response_model=InterviewAgentContext,
)
def get_agent_context(
    vacancy_id: UUID,
    invitation_id: UUID,
    _: str = Depends(require_recruiter),
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> InterviewAgentContext:
    return service.build_agent_context(
        vacancy_id=vacancy_id,
        invitation_id=invitation_id,
    )


@candidate_document_router.post(
    "/{secret}/resume",
    response_model=ResumeView,
    status_code=status.HTTP_201_CREATED,
    summary="Upload or replace the resume linked to this invitation",
    openapi_extra=DOCUMENT_BODY_OPENAPI,
)
async def upload_candidate_resume(
    secret: str,
    request: Request,
    document_filename: Annotated[
        str, Header(alias="X-Document-Filename", min_length=1, max_length=255)
    ],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> ResumeView:
    result = service.upload_resume(
        secret=secret,
        document=await _document_bytes(request),
        filename=document_filename,
        media_type=request.headers.get("content-type", "application/octet-stream"),
        idempotency_key=idempotency_key,
    )
    if result is None:
        raise invalid_invitation()
    return result


@candidate_document_router.get("/{secret}/resume", response_model=ResumeView)
def get_candidate_resume(
    secret: str,
    service: HiringContextWorkflow = Depends(get_hiring_context_service),
) -> ResumeView:
    result = service.candidate_resume(secret)
    if result is None:
        raise invalid_invitation()
    return result


async def hiring_context_exception_handler(
    _: Request, error: HiringContextError
) -> JSONResponse:
    if isinstance(error, HiringContextNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, HiringContextConflictError):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(error, HiringContextValidationError):
        http_status = 422
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(error, CandidateConsentRequiredError):
        http_status = status.HTTP_409_CONFLICT
    return JSONResponse(
        status_code=http_status,
        content={"error": {"code": error.code, "message": error.message}},
    )
