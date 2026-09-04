"""Candidate-facing invitation and response API contract."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator

from app.api.errors import invalid_invitation
from app.domain.proctoring import MonitoringEventKind, MonitoringReviewStatus
from app.models.interview import TranscriptionStatus

router = APIRouter(prefix="/candidate", tags=["candidate"])


class InvitationView(BaseModel):
    session_id: UUID
    consented: bool
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    resume_uploaded: bool = False


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


class MonitoringEvidenceGrantRequest(BaseModel):
    client_event_id: UUID
    response_id: UUID
    question_id: UUID
    content_type: str = Field(pattern=r"^video/(webm|mp4)$")


class MonitoringEvidenceGrant(BaseModel):
    client_event_id: UUID
    upload_url: str


class MonitoringEventRequest(BaseModel):
    client_event_id: UUID
    response_id: UUID
    question_id: UUID
    kind: Literal[
        MonitoringEventKind.FACE_MISSING,
        MonitoringEventKind.MULTIPLE_FACES,
        MonitoringEventKind.FACE_DETECTION_UNAVAILABLE,
    ]
    started_at_ms: int = Field(ge=0, le=14_400_000)
    ended_at_ms: int = Field(gt=0, le=14_400_000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    detector_name: str = Field(min_length=1, max_length=120)
    detector_version: str = Field(min_length=1, max_length=80)
    evidence_content_type: str | None = Field(
        default=None, pattern=r"^video/(webm|mp4)$"
    )
    evidence_checksum: str | None = Field(
        default=None, min_length=16, max_length=128
    )

    @model_validator(mode="after")
    def validate_interval_and_evidence(self) -> "MonitoringEventRequest":
        if self.ended_at_ms <= self.started_at_ms:
            raise ValueError("event end must be after its start")
        if bool(self.evidence_content_type) != bool(self.evidence_checksum):
            raise ValueError(
                "evidence content type and checksum must be supplied together"
            )
        return self


class MonitoringEventView(BaseModel):
    id: UUID
    kind: MonitoringEventKind
    started_at_ms: int
    ended_at_ms: int
    review_status: MonitoringReviewStatus


class CandidateWorkflow(Protocol):
    def resolve(self, secret: str) -> InvitationView | None: ...
    def consent(self, secret: str) -> InvitationView | None: ...

    def create_upload_grant(
        self, secret: str, request: UploadGrantRequest
    ) -> UploadGrant | None: ...

    def confirm_upload(
        self, secret: str, request: ConfirmUploadRequest
    ) -> TranscriptView | None: ...

    def transcript(
        self, secret: str, response_id: UUID
    ) -> TranscriptView | None: ...

    def create_monitoring_evidence_grant(
        self, secret: str, request: MonitoringEvidenceGrantRequest
    ) -> MonitoringEvidenceGrant | None: ...

    def record_monitoring_event(
        self, secret: str, request: MonitoringEventRequest
    ) -> MonitoringEventView | None: ...


def get_workflow(request: Request) -> CandidateWorkflow:
    return request.app.state.workflow_factory()


@router.get("/{secret}", response_model=InvitationView)
def resolve_invitation(
    secret: str, workflow: CandidateWorkflow = Depends(get_workflow)
) -> InvitationView:
    return workflow.resolve(secret) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/consent", response_model=InvitationView)
def record_consent(
    secret: str, workflow: CandidateWorkflow = Depends(get_workflow)
) -> InvitationView:
    return workflow.consent(secret) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/upload-grants", response_model=UploadGrant)
def request_upload_grant(
    secret: str,
    request: UploadGrantRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> UploadGrant:
    return workflow.create_upload_grant(secret, request) or (_ for _ in ()).throw(
        invalid_invitation()
    )


@router.post("/{secret}/responses/confirm", response_model=TranscriptView)
def confirm_upload(
    secret: str,
    request: ConfirmUploadRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> TranscriptView:
    return workflow.confirm_upload(secret, request) or (_ for _ in ()).throw(
        invalid_invitation()
    )


@router.get(
    "/{secret}/responses/{response_id}/transcript",
    response_model=TranscriptView,
)
def transcript_status(
    secret: str,
    response_id: UUID,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> TranscriptView:
    return workflow.transcript(secret, response_id) or (_ for _ in ()).throw(
        invalid_invitation()
    )


@router.post(
    "/{secret}/monitoring-evidence-grants",
    response_model=MonitoringEvidenceGrant,
)
def request_monitoring_evidence_grant(
    secret: str,
    request: MonitoringEvidenceGrantRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> MonitoringEvidenceGrant:
    return workflow.create_monitoring_evidence_grant(secret, request) or (
        _ for _ in ()
    ).throw(invalid_invitation())


@router.post(
    "/{secret}/monitoring-events",
    response_model=MonitoringEventView,
)
def record_monitoring_event(
    secret: str,
    request: MonitoringEventRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> MonitoringEventView:
    return workflow.record_monitoring_event(secret, request) or (
        _ for _ in ()
    ).throw(invalid_invitation())
