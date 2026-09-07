"""Validated manager-brief contracts shared by the agent, service, and API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FieldKey(StrEnum):
    ROLE = "role"
    SENIORITY = "seniority"
    BUSINESS_CONTEXT = "business_context"
    RESPONSIBILITIES = "responsibilities"
    MUST_HAVE_COMPETENCIES = "must_have_competencies"
    NICE_TO_HAVE_COMPETENCIES = "nice_to_have_competencies"
    EXPECTED_ANSWER_SIGNALS = "expected_answer_signals"
    CONSTRAINTS = "constraints"
    TOPICS_TO_COVER = "topics_to_cover"


SINGLE_VALUE_FIELDS = {
    FieldKey.ROLE,
    FieldKey.SENIORITY,
    FieldKey.BUSINESS_CONTEXT,
}

FIELD_LABELS = {
    FieldKey.ROLE: "Роль",
    FieldKey.SENIORITY: "Уровень",
    FieldKey.BUSINESS_CONTEXT: "Контекст команды и продукта",
    FieldKey.RESPONSIBILITIES: "Рабочие задачи",
    FieldKey.MUST_HAVE_COMPETENCIES: "Обязательные компетенции",
    FieldKey.NICE_TO_HAVE_COMPETENCIES: "Желательные компетенции",
    FieldKey.EXPECTED_ANSWER_SIGNALS: "Что ожидаем услышать в ответах",
    FieldKey.CONSTRAINTS: "Ограничения и условия",
    FieldKey.TOPICS_TO_COVER: "Темы для проверки",
}


class FieldOrigin(StrEnum):
    MANAGER_SOURCE = "manager_source"
    # Read compatibility for drafts created before agent suggestions were disabled.
    AGENT_SUGGESTION = "agent_suggestion"
    MANAGER_EDITED = "manager_edited"


class AgentFieldOrigin(StrEnum):
    MANAGER_SOURCE = "manager_source"


class ConfirmationStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class ManagerBriefStatus(StrEnum):
    DRAFT = "draft"
    VALIDATION_FAILED = "validation_failed"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class AgentOperationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_FAILED = "provider_failed"


FieldValue = str | list[str]


class AgentFieldProposal(BaseModel):
    """One structured value emitted by the manager-brief agent."""

    model_config = ConfigDict(extra="forbid")

    field_key: FieldKey
    value: FieldValue
    origin: AgentFieldOrigin
    source_fragment_ids: list[str]
    source_quotes: list[str]
    confidence: Annotated[float, Field(ge=0, le=1)]


class UnresolvedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: FieldKey
    question: str = Field(min_length=1, max_length=500)


class ManagerBriefAgentResult(BaseModel):
    """Strict structured output requested from the language model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["manager_brief_v1"]
    purpose: Literal["manager_brief_draft"]
    fields: list[AgentFieldProposal]
    unresolved_fields: list[UnresolvedField]


class ManagerBriefField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    field_key: FieldKey
    label: str
    value: FieldValue
    origin: FieldOrigin
    source_fragment_ids: list[str]
    source_quotes: list[str]
    confidence: Annotated[float, Field(ge=0, le=1)] | None
    confirmation_status: ConfirmationStatus
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None

    @model_validator(mode="after")
    def confirmation_has_actor_and_time(self) -> Self:
        confirmed = self.confirmation_status is ConfirmationStatus.CONFIRMED
        if confirmed and (not self.confirmed_by or self.confirmed_at is None):
            raise ValueError("confirmed field requires confirmed_by and confirmed_at")
        if not confirmed and (
            self.confirmed_by is not None or self.confirmed_at is not None
        ):
            raise ValueError("unconfirmed field cannot carry confirmation metadata")
        return self


class ManagerBriefFieldUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: FieldKey
    value: FieldValue
    confirmation_status: ConfirmationStatus

    @field_validator("confirmation_status")
    @classmethod
    def manager_must_resolve_proposal(
        cls, value: ConfirmationStatus
    ) -> ConfirmationStatus:
        if value is ConfirmationStatus.PROPOSED:
            raise ValueError("manager update must confirm or reject the field")
        return value


class ManagerBriefDraftView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    vacancy_id: UUID
    version: int
    revision: int
    status: ManagerBriefStatus
    source_text: str
    fields: list[ManagerBriefField]
    unresolved_fields: list[UnresolvedField]
    validation_issues: list[dict]
    content_hash: str
    agent_run_id: UUID
    created_by: str
    created_at: datetime
    updated_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None


class ApprovedManagerBriefField(BaseModel):
    """Minimum confirmed field data needed by downstream agents."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    field_key: FieldKey
    value: FieldValue
    origin: FieldOrigin
    source_fragment_ids: list[str]


class ApprovedManagerBriefContext(BaseModel):
    """Allowlisted context handed to downstream interview-analysis agents."""

    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    vacancy_id: UUID
    version: int
    content_hash: str
    fields: list[ApprovedManagerBriefField]


class ManagerBriefError(Exception):
    code = "manager_brief_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ManagerBriefNotFoundError(ManagerBriefError):
    code = "manager_brief_not_found"


class ManagerBriefConflictError(ManagerBriefError):
    code = "manager_brief_conflict"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ManagerBriefValidationError(ManagerBriefError):
    code = "manager_brief_validation_failed"

    def __init__(self, message: str, *, issues: list[dict] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or []


class AgentProviderError(ManagerBriefError):
    code = "manager_brief_agent_unavailable"


class AgentOutputError(ManagerBriefError):
    code = "manager_brief_agent_invalid_output"
