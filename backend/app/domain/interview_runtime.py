"""Contracts shared by interview configuration and presenter workers."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PresenterStatus(StrEnum):
    QUEUED = "queued"
    AUDIO_PROCESSING = "audio_processing"
    AUDIO_READY = "audio_ready"
    AVATAR_PROCESSING = "avatar_processing"
    READY = "ready"
    FAILED = "failed"


class PresenterFallback(StrEnum):
    NONE = "none"
    STATIC_PORTRAIT = "static_portrait"
    BROWSER_SPEECH = "browser_speech"


class PresenterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    status: PresenterStatus
    audio_url: str | None = None
    avatar_url: str | None = None
    static_portrait_url: str
    fallback: PresenterFallback = PresenterFallback.NONE


class PresenterAssetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    question_id: UUID
    question_text: str = Field(min_length=1, max_length=4_000)
    voice_id: str = Field(min_length=1, max_length=120)
    portrait_version: str = Field(min_length=1, max_length=120)
    renderer_version: str = Field(min_length=1, max_length=120)


class JobKind(StrEnum):
    TRANSCRIPTION = "transcription"
    RUNTIME_ASSESSMENT = "runtime_assessment"
    PRESENTER_AUDIO = "presenter_audio"
    PRESENTER_AVATAR = "presenter_avatar"
    FINAL_ASSESSMENT = "final_assessment"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    RETRYABLE_FAILED = "retryable_failed"
    TERMINAL_FAILED = "terminal_failed"
