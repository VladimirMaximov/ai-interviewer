"""Contracts and errors for vacancy/resume matching and agent context."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VacancyStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class ResumeUploaderRole(StrEnum):
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"


class VacancyView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    description: str
    manager_wishes: str | None = None
    manager_brief_fields: list[dict] = Field(default_factory=list)
    status: VacancyStatus
    source_filename: str
    media_type: str
    content_hash: str
    created_at: datetime


class ResumeView(BaseModel):
    """Candidate-safe resume metadata; extracted text is deliberately omitted."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    vacancy_id: UUID
    version: int
    source_filename: str
    media_type: str
    content_hash: str
    uploaded_by_role: ResumeUploaderRole
    created_at: datetime


class InvitationCreated(BaseModel):
    """One-time response containing the candidate secret."""

    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    vacancy_id: UUID
    candidate_token: str
    candidate_url: str
    expires_at: datetime


class ApplicationView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invitation_id: UUID
    vacancy_id: UUID
    candidate_alias: str | None
    invitation_status: str
    session_id: UUID | None
    resume: ResumeView | None


class AgentDocumentContext(BaseModel):
    """A bounded document projection explicitly marked as untrusted input."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    source_kind: Literal["vacancy", "resume"]
    media_type: str
    content_hash: str
    untrusted_text: str
    version: int | None = None
    uploaded_by_role: ResumeUploaderRole | None = None


class ApprovedBriefContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: UUID
    version: int
    content_hash: str
    confirmed_fields: list[dict]


class AgentAnswerContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: UUID
    question_id: UUID
    status: str
    untrusted_text: str | None


class AgentContextPolicy(BaseModel):
    """Safety semantics which downstream orchestration must preserve."""

    model_config = ConfigDict(extra="forbid")

    resume_is_claim_source_only: Literal[True] = True
    interview_scores_require_answer_evidence: Literal[True] = True
    missing_evidence_is_not_zero: Literal[True] = True
    automatic_hiring_decision_forbidden: Literal[True] = True


class InterviewAgentContext(BaseModel):
    """Allowlisted, candidate-isolated input for downstream interview agents."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["interview_agent_context_v1"] = (
        "interview_agent_context_v1"
    )
    purpose: Literal["interview_analysis"] = "interview_analysis"
    invitation_id: UUID
    session_id: UUID | None
    vacancy: AgentDocumentContext
    approved_brief: ApprovedBriefContext | None
    resume: AgentDocumentContext | None
    answers: list[AgentAnswerContext]
    policy: AgentContextPolicy = Field(default_factory=AgentContextPolicy)
    context_hash: str


class HiringContextError(Exception):
    code = "hiring_context_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class HiringContextNotFoundError(HiringContextError):
    code = "hiring_context_not_found"


class HiringContextConflictError(HiringContextError):
    code = "hiring_context_conflict"


class HiringContextValidationError(HiringContextError):
    code = "hiring_context_validation_failed"


class CandidateConsentRequiredError(HiringContextConflictError):
    code = "candidate_consent_required"


class DocumentTooLargeError(HiringContextValidationError):
    code = "document_too_large"


class UnsupportedDocumentError(HiringContextValidationError):
    code = "unsupported_document_type"


class DocumentExtractionError(HiringContextValidationError):
    code = "document_extraction_failed"
