"""Candidate-facing invitation and response API contract."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.errors import invalid_invitation
from app.models.interview import TranscriptionStatus

router = APIRouter(prefix="/candidate", tags=["candidate"])


class InvitationView(BaseModel):
    session_id: UUID
    consented: bool


class UploadGrantRequest(BaseModel):
    question_id: UUID
    content_type: str = Field(pattern=r"^audio/")


class UploadGrant(BaseModel):
    response_id: UUID
    storage_key: str
    upload_url: str


class ConfirmUploadRequest(BaseModel):
    response_id: UUID
    checksum: str = Field(min_length=16, max_length=128)


class TranscriptView(BaseModel):
    status: TranscriptionStatus
    text: str | None = None


class CandidateWorkflow(Protocol):
    def resolve(self, secret: str) -> InvitationView | None: ...
    def consent(self, secret: str) -> InvitationView | None: ...
    def create_upload_grant(self, secret: str, request: UploadGrantRequest) -> UploadGrant | None: ...
    def confirm_upload(self, secret: str, request: ConfirmUploadRequest) -> TranscriptView | None: ...
    def transcript(self, secret: str, response_id: UUID) -> TranscriptView | None: ...


def get_workflow(request: Request) -> CandidateWorkflow:
    return request.app.state.workflow_factory()


@router.get("/{secret}", response_model=InvitationView)
def resolve_invitation(secret: str, workflow: CandidateWorkflow = Depends(get_workflow)) -> InvitationView:
    return workflow.resolve(secret) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/consent", response_model=InvitationView)
def record_consent(secret: str, workflow: CandidateWorkflow = Depends(get_workflow)) -> InvitationView:
    return workflow.consent(secret) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/upload-grants", response_model=UploadGrant)
def request_upload_grant(secret: str, request: UploadGrantRequest,
                         workflow: CandidateWorkflow = Depends(get_workflow)) -> UploadGrant:
    return workflow.create_upload_grant(secret, request) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/responses/confirm", response_model=TranscriptView)
def confirm_upload(secret: str, request: ConfirmUploadRequest,
                   workflow: CandidateWorkflow = Depends(get_workflow)) -> TranscriptView:
    return workflow.confirm_upload(secret, request) or (_ for _ in ()).throw(invalid_invitation())


@router.get("/{secret}/responses/{response_id}/transcript", response_model=TranscriptView)
def transcript_status(secret: str, response_id: UUID,
                      workflow: CandidateWorkflow = Depends(get_workflow)) -> TranscriptView:
    return workflow.transcript(secret, response_id) or (_ for _ in ()).throw(invalid_invitation())
