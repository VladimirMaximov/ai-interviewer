"""Candidate-facing invitation and response API contract."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.errors import invalid_invitation
from app.models.interview import TranscriptionStatus
from app.models.interview import FollowUpStatus, TimelineEventType

router = APIRouter(prefix="/candidate", tags=["candidate"])


class InvitationView(BaseModel):
    session_id: UUID
    consented: bool
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    resume_uploaded: bool = False


class UploadGrantRequest(BaseModel):
    question_id: UUID
    content_type: str = Field(pattern=r"^(audio|video)/")


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

class TimelineEventRequest(BaseModel):
    question_id: UUID | None = None
    event_type: TimelineEventType
    recording_offset_ms: int = Field(ge=0)

class RecordingGrant(BaseModel):
    recording_id: UUID
    storage_key: str
    upload_url: str
    content_type: str


class StartRecordingRequest(BaseModel):
    content_type: str = Field(pattern=r"^video/(webm|mp4)$")

class FinishRecordingRequest(BaseModel):
    recording_id: UUID
    checksum: str = Field(min_length=16, max_length=128)


class RecordingChunkGrantRequest(BaseModel):
    recording_id: UUID
    sequence: int = Field(ge=0)
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(gt=0)
    content_type: str = Field(pattern=r"^video/(webm|mp4)$")


class RecordingChunkGrant(BaseModel):
    chunk_id: UUID
    upload_url: str
    content_type: str


class ConfirmRecordingChunkRequest(BaseModel):
    chunk_id: UUID
    checksum: str = Field(min_length=16, max_length=128)


class ResponseSegmentRequest(BaseModel):
    question_id: UUID
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(gt=0)


class ResponseSegmentView(BaseModel):
    response_id: UUID
    status: TranscriptionStatus


class FollowUpQuestionView(BaseModel):
    id: UUID
    source_response_id: UUID | None
    text: str
    status: FollowUpStatus


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
    def record_timeline_event(self, secret: str, request: TimelineEventRequest) -> bool: ...
    def start_recording(self, secret: str, request: StartRecordingRequest) -> RecordingGrant | None: ...
    def finish_recording(self, secret: str, request: FinishRecordingRequest) -> bool: ...
    def create_recording_chunk_grant(self, secret: str, request: RecordingChunkGrantRequest) -> RecordingChunkGrant | None: ...
    def confirm_recording_chunk(self, secret: str, request: ConfirmRecordingChunkRequest) -> bool: ...
    def save_response_segment(self, secret: str, request: ResponseSegmentRequest) -> ResponseSegmentView | None: ...
    def follow_up_questions(self, secret: str) -> list[FollowUpQuestionView] | None: ...


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

@router.post("/{secret}/timeline-events", status_code=204)
def timeline_event(secret: str, request: TimelineEventRequest, workflow: CandidateWorkflow = Depends(get_workflow)) -> None:
    if not workflow.record_timeline_event(secret, request):
        raise invalid_invitation()

@router.post("/{secret}/recording", response_model=RecordingGrant)
def start_recording(secret: str, request: StartRecordingRequest,
                    workflow: CandidateWorkflow = Depends(get_workflow)) -> RecordingGrant:
    return workflow.start_recording(secret, request) or (_ for _ in ()).throw(invalid_invitation())

@router.post("/{secret}/recording/finish", status_code=204)
def finish_recording(secret: str, request: FinishRecordingRequest, workflow: CandidateWorkflow = Depends(get_workflow)) -> None:
    if not workflow.finish_recording(secret, request):
        raise invalid_invitation()


@router.post("/{secret}/recording/chunks", response_model=RecordingChunkGrant)
def request_recording_chunk(secret: str, request: RecordingChunkGrantRequest,
                            workflow: CandidateWorkflow = Depends(get_workflow)) -> RecordingChunkGrant:
    if request.end_offset_ms <= request.start_offset_ms:
        raise invalid_invitation()
    return workflow.create_recording_chunk_grant(secret, request) or (_ for _ in ()).throw(invalid_invitation())


@router.post("/{secret}/recording/chunks/confirm", status_code=204)
def confirm_recording_chunk(secret: str, request: ConfirmRecordingChunkRequest,
                            workflow: CandidateWorkflow = Depends(get_workflow)) -> None:
    if not workflow.confirm_recording_chunk(secret, request):
        raise invalid_invitation()


@router.post("/{secret}/responses/segments", response_model=ResponseSegmentView)
def save_response_segment(secret: str, request: ResponseSegmentRequest,
                          workflow: CandidateWorkflow = Depends(get_workflow)) -> ResponseSegmentView:
    if request.end_offset_ms <= request.start_offset_ms:
        raise invalid_invitation()
    return workflow.save_response_segment(secret, request) or (_ for _ in ()).throw(invalid_invitation())


@router.get("/{secret}/follow-ups", response_model=list[FollowUpQuestionView])
def follow_up_questions(secret: str, workflow: CandidateWorkflow = Depends(get_workflow)) -> list[FollowUpQuestionView]:
    questions = workflow.follow_up_questions(secret)
    return questions if questions is not None else (_ for _ in ()).throw(invalid_invitation())
