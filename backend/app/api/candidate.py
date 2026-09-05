"""Candidate-facing invitation and response API contract."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from app.domain.interview_runtime import PresenterState
from pydantic import BaseModel, Field, model_validator

from app.api.errors import invalid_invitation
from app.domain.proctoring import MonitoringEventKind, MonitoringReviewStatus
from app.interview_config import QuestionKind
from app.models.interview import TranscriptionStatus
from app.models.interview import FollowUpStatus, TimelineEventType

router = APIRouter(prefix="/candidate", tags=["candidate"])


class CandidateQuestion(BaseModel):
    id: UUID
    text: str
    kind: QuestionKind
    block_key: str | None = None
    block_title: str | None = None
    time_limit_seconds: int | None = None


class InvitationView(BaseModel):
    session_id: UUID
    consented: bool
    vacancy_id: UUID | None = None
    vacancy_title: str | None = None
    resume_uploaded: bool = False
    questions: list[CandidateQuestion] = []


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
    kind: Literal[MonitoringEventKind.FACE_MISSING, MonitoringEventKind.MULTIPLE_FACES, MonitoringEventKind.FACE_DETECTION_UNAVAILABLE]
    started_at_ms: int = Field(ge=0, le=14_400_000)
    ended_at_ms: int = Field(gt=0, le=14_400_000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    detector_name: str = Field(min_length=1, max_length=120)
    detector_version: str = Field(min_length=1, max_length=80)
    evidence_content_type: str | None = Field(default=None, pattern=r"^video/(webm|mp4)$")
    evidence_checksum: str | None = Field(default=None, min_length=16, max_length=128)

    @model_validator(mode="after")
    def validate_interval_and_evidence(self) -> "MonitoringEventRequest":
        if self.ended_at_ms <= self.started_at_ms:
            raise ValueError("event end must be after its start")
        if bool(self.evidence_content_type) != bool(self.evidence_checksum):
            raise ValueError("evidence content type and checksum must be supplied together")
        return self


class MonitoringEventView(BaseModel):
    id: UUID
    kind: MonitoringEventKind
    started_at_ms: int
    ended_at_ms: int
    review_status: MonitoringReviewStatus

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
    timed_out: bool = False


class ResponseSegmentView(BaseModel):
    response_id: UUID
    status: TranscriptionStatus


class CodeAnswerRequest(BaseModel):
    question_id: UUID
    language: str = Field(min_length=1, max_length=64)
    source_code: str = Field(max_length=100_000)
    start_offset_ms: int = Field(ge=0)
    end_offset_ms: int = Field(gt=0)
    timed_out: bool = False


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
    def save_code_answer(self, secret: str, request: CodeAnswerRequest) -> ResponseSegmentView | None: ...
    def follow_up_questions(self, secret: str) -> list[FollowUpQuestionView] | None: ...
    def question_speech_text(self, secret: str, question_id: UUID) -> str | None: ...
    def avatar_video_url(self, secret: str, question_id: UUID) -> str | None: ...
    def presenter_state(self, secret: str, question_id: UUID) -> PresenterState | None: ...
    def create_monitoring_evidence_grant(self, secret: str, request: MonitoringEvidenceGrantRequest) -> MonitoringEvidenceGrant | None: ...
    def record_monitoring_event(self, secret: str, request: MonitoringEventRequest) -> MonitoringEventView | None: ...


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


@router.get("/{secret}/questions/{question_id}/speech", response_class=Response)
def question_speech(
    secret: str,
    question_id: UUID,
    request: Request,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> Response:
    """Synthesize an authorised question locally; never persist the WAV."""
    text = workflow.question_speech_text(secret, question_id)
    if text is None:
        raise invalid_invitation()
    provider = request.app.state.question_speech_provider_factory()
    if provider is None:
        raise HTTPException(status_code=404, detail="Local question speech is disabled")
    try:
        with tempfile.TemporaryDirectory(prefix="ai-interviewer-tts-") as directory:
            output = provider.synthesize(text, output_path=Path(directory) / "question.wav")
            audio = output.read_bytes()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Local question speech is unavailable") from error
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=300"})


@router.get("/{secret}/questions/{question_id}/avatar")
def question_avatar(
    secret: str, question_id: UUID, workflow: CandidateWorkflow = Depends(get_workflow)
) -> RedirectResponse:
    url = workflow.avatar_video_url(secret, question_id)
    if url is None:
        raise HTTPException(status_code=404, detail="Avatar video is not ready")
    return RedirectResponse(url=url, status_code=307)


@router.get("/{secret}/questions/{question_id}/presenter", response_model=PresenterState)
def question_presenter(
    secret: str, question_id: UUID, workflow: CandidateWorkflow = Depends(get_workflow)
) -> PresenterState:
    """Expose only short-lived media URLs authorized by the invitation token."""
    state = workflow.presenter_state(secret, question_id)
    if state is None:
        raise invalid_invitation()
    return state


@router.get("/{secret}/questions/{question_id}/avatar-frame/{frame}")
def question_avatar_frame(
    secret: str,
    question_id: UUID,
    frame: str,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> FileResponse:
    """Return a token-authorised, non-public avatar keyframe."""
    if frame not in {"idle", "speaking"} or workflow.question_speech_text(secret, question_id) is None:
        raise invalid_invitation()
    filename = {
        "idle": "interviewer-cutout.png",
        "speaking": "interviewer-speaking-cutout.png",
    }[frame]
    asset = Path("backend/assets/avatar") / filename
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="Avatar asset is not ready")
    return FileResponse(asset, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


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


@router.post("/{secret}/monitoring-evidence-grants", response_model=MonitoringEvidenceGrant)
def request_monitoring_evidence_grant(
    secret: str,
    request: MonitoringEvidenceGrantRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> MonitoringEvidenceGrant:
    return workflow.create_monitoring_evidence_grant(secret, request) or (
        _ for _ in ()
    ).throw(invalid_invitation())


@router.post("/{secret}/monitoring-events", response_model=MonitoringEventView)
def record_monitoring_event(
    secret: str,
    request: MonitoringEventRequest,
    workflow: CandidateWorkflow = Depends(get_workflow),
) -> MonitoringEventView:
    return workflow.record_monitoring_event(secret, request) or (
        _ for _ in ()
    ).throw(invalid_invitation())

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


@router.post("/{secret}/code-answers", response_model=ResponseSegmentView)
def save_code_answer(secret: str, request: CodeAnswerRequest,
                     workflow: CandidateWorkflow = Depends(get_workflow)) -> ResponseSegmentView:
    if request.end_offset_ms <= request.start_offset_ms:
        raise invalid_invitation()
    return workflow.save_code_answer(secret, request) or (_ for _ in ()).throw(invalid_invitation())


@router.get("/{secret}/follow-ups", response_model=list[FollowUpQuestionView])
def follow_up_questions(secret: str, workflow: CandidateWorkflow = Depends(get_workflow)) -> list[FollowUpQuestionView]:
    questions = workflow.follow_up_questions(secret)
    return questions if questions is not None else (_ for _ in ()).throw(invalid_invitation())
