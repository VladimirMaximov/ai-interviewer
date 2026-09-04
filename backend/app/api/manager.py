"""Hiring-manager API for agent-generated, editable interview context."""

from __future__ import annotations

import secrets
from typing import Annotated, Iterator, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.domain.manager_brief import (
    AgentOutputError,
    AgentProviderError,
    ApprovedManagerBriefContext,
    ManagerBriefConflictError,
    ManagerBriefDraftView,
    ManagerBriefError,
    ManagerBriefFieldUpdate,
    ManagerBriefNotFoundError,
    ManagerBriefValidationError,
)


router = APIRouter(prefix="/manager/vacancies", tags=["manager-brief"])


class CreateManagerBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_text: str = Field(min_length=1, max_length=50_000)


class UpdateManagerBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    updates: list[ManagerBriefFieldUpdate] = Field(max_length=9)


class ApproveManagerBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    confirm_no_automatic_rejection: bool


class ManagerBriefList(BaseModel):
    drafts: list[ManagerBriefDraftView]


class ManagerBriefWorkflow(Protocol):
    def create_draft(
        self,
        *,
        vacancy_id: UUID,
        source_text: str,
        actor_id: str,
        idempotency_key: str,
    ) -> ManagerBriefDraftView: ...

    def list_drafts(self, vacancy_id: UUID) -> list[ManagerBriefDraftView]: ...

    def get_draft(self, vacancy_id: UUID, draft_id: UUID) -> ManagerBriefDraftView: ...

    def update_draft(
        self,
        *,
        vacancy_id: UUID,
        draft_id: UUID,
        expected_revision: int,
        actor_id: str,
        updates: list[ManagerBriefFieldUpdate],
    ) -> ManagerBriefDraftView: ...

    def approve_draft(
        self,
        *,
        vacancy_id: UUID,
        draft_id: UUID,
        expected_revision: int,
        actor_id: str,
        confirm_no_automatic_rejection: bool,
    ) -> ManagerBriefDraftView: ...

    def get_approved_context(self, vacancy_id: UUID) -> ApprovedManagerBriefContext: ...


def require_manager(
    x_manager_key: Annotated[str | None, Header(alias="X-Manager-Key")] = None,
    x_manager_id: Annotated[str | None, Header(alias="X-Manager-Id")] = None,
) -> str:
    """Authenticate staff without leaking whether a vacancy or draft exists."""
    if not settings.manager_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Manager API is not configured.",
        )
    if x_manager_key is None or not secrets.compare_digest(
        x_manager_key, settings.manager_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Manager credentials are invalid.",
        )
    actor_id = (x_manager_id or settings.manager_id).strip()
    if not actor_id or len(actor_id) > 120:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Manager actor id is invalid.",
        )
    return actor_id


def get_manager_brief_service(request: Request) -> Iterator[ManagerBriefWorkflow]:
    service = request.app.state.manager_brief_service_factory()
    try:
        yield service
    finally:
        close = getattr(service, "close", None)
        if close is not None:
            close()


@router.post(
    "/{vacancy_id}/brief-drafts",
    response_model=ManagerBriefDraftView,
    status_code=status.HTTP_201_CREATED,
)
def create_manager_brief(
    vacancy_id: UUID,
    payload: CreateManagerBriefRequest,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
    actor_id: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ManagerBriefDraftView:
    return service.create_draft(
        vacancy_id=vacancy_id,
        source_text=payload.source_text,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
    )


@router.get("/{vacancy_id}/brief-drafts", response_model=ManagerBriefList)
def list_manager_briefs(
    vacancy_id: UUID,
    _: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ManagerBriefList:
    return ManagerBriefList(drafts=service.list_drafts(vacancy_id))


@router.get(
    "/{vacancy_id}/brief-drafts/{draft_id}",
    response_model=ManagerBriefDraftView,
)
def get_manager_brief(
    vacancy_id: UUID,
    draft_id: UUID,
    _: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ManagerBriefDraftView:
    return service.get_draft(vacancy_id, draft_id)


@router.patch(
    "/{vacancy_id}/brief-drafts/{draft_id}",
    response_model=ManagerBriefDraftView,
)
def update_manager_brief(
    vacancy_id: UUID,
    draft_id: UUID,
    payload: UpdateManagerBriefRequest,
    actor_id: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ManagerBriefDraftView:
    return service.update_draft(
        vacancy_id=vacancy_id,
        draft_id=draft_id,
        expected_revision=payload.expected_revision,
        actor_id=actor_id,
        updates=payload.updates,
    )


@router.post(
    "/{vacancy_id}/brief-drafts/{draft_id}/approve",
    response_model=ManagerBriefDraftView,
)
def approve_manager_brief(
    vacancy_id: UUID,
    draft_id: UUID,
    payload: ApproveManagerBriefRequest,
    actor_id: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ManagerBriefDraftView:
    return service.approve_draft(
        vacancy_id=vacancy_id,
        draft_id=draft_id,
        expected_revision=payload.expected_revision,
        actor_id=actor_id,
        confirm_no_automatic_rejection=payload.confirm_no_automatic_rejection,
    )


@router.get(
    "/{vacancy_id}/approved-brief-context",
    response_model=ApprovedManagerBriefContext,
)
def get_approved_manager_context(
    vacancy_id: UUID,
    _: str = Depends(require_manager),
    service: ManagerBriefWorkflow = Depends(get_manager_brief_service),
) -> ApprovedManagerBriefContext:
    return service.get_approved_context(vacancy_id)


async def manager_brief_exception_handler(
    _: Request, error: ManagerBriefError
) -> JSONResponse:
    if isinstance(error, ManagerBriefNotFoundError):
        http_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ManagerBriefConflictError):
        http_status = status.HTTP_409_CONFLICT
    elif isinstance(error, ManagerBriefValidationError):
        http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, AgentOutputError):
        http_status = status.HTTP_502_BAD_GATEWAY
    elif isinstance(error, AgentProviderError):
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    details = {}
    if isinstance(error, ManagerBriefValidationError) and error.issues:
        details["issues"] = error.issues
    return JSONResponse(
        status_code=http_status,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": details,
            }
        },
    )
