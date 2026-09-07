"""Strict contracts for the session-scoped multi-agent interview harness."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


AGENT_OUTPUT_VERSION = "session_agent_output_v2"
EVIDENCE_CATALOG_VERSION = "evidence_catalog_v1"
SCALE_VERSION = "signed_criterion_v1"
CRITERIA_VERSION = "interview_criteria_v1"
AGGREGATION_VERSION = "candidate_profile_v1"
POLICY_VERSION = "strong_pool_v1"
FEEDBACK_VERSION = "candidate_feedback_v1"
CANDIDATE_SCORE_VERSION = "signed_readiness_to_10_v1"


class AgentPurpose(StrEnum):
    RESUME_RELEVANCE = "resume_relevance"
    QUESTION_PLAN = "question_plan"
    ANSWER_ASSESSMENT = "answer_assessment"
    ALTERNATIVE_VACANCY_MATCH = "alternative_vacancy_match"
    INTEGRITY_CHECK = "integrity_check"
    CANDIDATE_FEEDBACK = "candidate_feedback"


class AgentSessionStatus(StrEnum):
    ACTIVE = "active"
    READY = "ready"
    FAILED = "failed"


class AgentOperationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_FAILED = "provider_failed"


class ArtifactKind(StrEnum):
    RESUME_RELEVANCE = "resume_relevance"
    QUESTION_PLAN = "question_plan"
    ANSWER_ASSESSMENT = "answer_assessment"
    CANDIDATE_PROFILE = "candidate_profile"
    ALTERNATIVE_VACANCY_MATCH = "alternative_vacancy_match"
    INTEGRITY_CHECK = "integrity_check"
    CANDIDATE_FEEDBACK = "candidate_feedback"


class Dimension(StrEnum):
    TECHNICAL = "technical"
    SOFT_SKILLS = "soft_skills"
    CORPORATE_COMPETENCIES = "corporate_competencies"
    VACANCY_FIT = "vacancy_fit"
    LEADERSHIP = "leadership"


class ObservationLabel(StrEnum):
    CONTRADICTED = "contradicted"
    WEAK = "weak"
    NEUTRAL = "neutral"
    SUPPORTED = "supported"
    STRONG = "strong"
    INSUFFICIENT_INFORMATION = "insufficient_information"


LABEL_VALUES: dict[ObservationLabel, float | None] = {
    ObservationLabel.CONTRADICTED: -1.0,
    ObservationLabel.WEAK: -0.5,
    ObservationLabel.NEUTRAL: 0.0,
    ObservationLabel.SUPPORTED: 0.5,
    ObservationLabel.STRONG: 1.0,
    ObservationLabel.INSUFFICIENT_INFORMATION: None,
}


class EvidenceKind(StrEnum):
    SUPPORTING = "supporting"
    COUNTER = "counter"
    MIXED = "mixed"
    INFORMATION_GAP = "information_gap"


class ResumeClaimType(StrEnum):
    EXPERIENCE = "experience"
    SKILL = "skill"
    ACHIEVEMENT = "achievement"
    RESPONSIBILITY = "responsibility"
    LEVEL_SIGNAL = "level_signal"


class ClaimVerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RequirementOrigin(StrEnum):
    VACANCY = "vacancy"
    MANAGER_BRIEF = "manager_brief"


class QuestionKind(StrEnum):
    BASELINE = "baseline"
    PERSONALIZED = "personalized"
    FOLLOW_UP = "follow_up"
    LIVE_CODING = "live_coding"


class FollowUpTrigger(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    MISSING_DETAIL = "missing_detail"


class LiveCodingTrigger(StrEnum):
    CLAIMED_TECHNICAL_SKILL_NOT_DEMONSTRATED = (
        "claimed_technical_skill_not_demonstrated"
    )


class AlternativeCompatibility(StrEnum):
    COMPATIBLE = "compatible"
    MANUAL_COMPARISON_REQUIRED = "manual_comparison_required"


class SeniorityBand(StrEnum):
    UNKNOWN = "unknown"
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"


class IntegrityStatus(StrEnum):
    CONSISTENT = "consistent"
    UNVERIFIED_CLAIM = "unverified_claim"
    CONTRADICTION_DETECTED = "contradiction_detected"
    MANUAL_INTEGRITY_REVIEW = "manual_integrity_review"


class RestrictionType(StrEnum):
    VERIFIED_MISREPRESENTATION = "verified_misrepresentation"
    RESTRICTED = "restricted"
    BLACKLISTED = "blacklisted"
    CLEARED = "cleared"


class FeedbackReleaseStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ExperienceAlignmentStatus(StrEnum):
    CONFIRMED = "confirmed"
    PARTIALLY_CONFIRMED = "partially_confirmed"
    NOT_CONFIRMED = "not_confirmed"
    NOT_ASSESSED = "not_assessed"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeClaim(StrictModel):
    claim_id: str = Field(min_length=1, max_length=120)
    claim_type: ResumeClaimType
    subject: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    verification_status: ClaimVerificationStatus


class ResumePosition(StrictModel):
    position_id: str = Field(min_length=1, max_length=120)
    employer: str | None = Field(default=None, max_length=500)
    role: str | None = Field(default=None, max_length=500)
    period: str | None = Field(default=None, max_length=500)
    project: str | None = Field(default=None, max_length=1_000)
    responsibilities: list[str]
    skills: list[str]
    achievements: list[str]
    evidence_ids: list[str] = Field(min_length=1, max_length=24)


class ExperienceMatch(StrictModel):
    experience_label: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    requirement_id: str = Field(min_length=1, max_length=120)
    requirement_origin: RequirementOrigin
    relevance: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=2_000)
    position_ids: list[str]
    claim_ids: list[str] = Field(default_factory=list)


class ResumeRelevanceOutput(StrictModel):
    schema_version: Literal["session_agent_output_v2"] = AGENT_OUTPUT_VERSION
    purpose: Literal["resume_relevance"] = AgentPurpose.RESUME_RELEVANCE
    positions: list[ResumePosition]
    claims: list[ResumeClaim]
    experience_matches: list[ExperienceMatch]
    gaps: list[str]


class CriterionDefinition(StrictModel):
    criterion_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    dimension: Dimension
    weight: float = Field(default=1.0, gt=0, le=10)
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)


class QuestionSelection(StrictModel):
    question_id: UUID
    prompt: str = Field(min_length=1, max_length=2_000)
    kind: QuestionKind
    criteria: list[CriterionDefinition] = Field(min_length=1)
    source_claim_ids: list[str] = Field(default_factory=list)
    source_manager_field_keys: list[str] = Field(default_factory=list)
    selection_reason: str = Field(min_length=1, max_length=2_000)


class QuestionPlanOutput(StrictModel):
    schema_version: Literal["session_agent_output_v2"] = AGENT_OUTPUT_VERSION
    purpose: Literal["question_plan"] = AgentPurpose.QUESTION_PLAN
    questions: list[QuestionSelection] = Field(min_length=1, max_length=12)


class AnswerEvidence(StrictModel):
    kind: EvidenceKind
    evidence_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_gap_shape(self) -> Self:
        if self.kind is EvidenceKind.INFORMATION_GAP:
            if self.evidence_id is not None:
                raise ValueError("information_gap evidence cannot contain an evidence id")
        elif not self.evidence_id or not self.evidence_id.strip():
            raise ValueError("numeric evidence requires a non-empty evidence id")
        return self


class CriterionObservation(StrictModel):
    criterion_id: str = Field(min_length=1, max_length=120)
    dimension: Dimension
    label: ObservationLabel
    value: float | None
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(min_length=1, max_length=2_000)
    evidence: list[AnswerEvidence] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_label_value_and_evidence(self) -> Self:
        expected = LABEL_VALUES[self.label]
        if expected is None:
            if self.value is not None:
                raise ValueError("insufficient_information requires a null value")
            if any(item.kind is not EvidenceKind.INFORMATION_GAP for item in self.evidence):
                raise ValueError("insufficient_information requires information_gap evidence")
            return self
        if self.value is None or float(self.value) != expected:
            raise ValueError("observation label and value do not match signed_criterion_v1")
        if any(item.kind is EvidenceKind.INFORMATION_GAP for item in self.evidence):
            raise ValueError("numeric observation cannot use information_gap evidence")
        expected_kinds = {
            ObservationLabel.CONTRADICTED: {EvidenceKind.COUNTER},
            ObservationLabel.WEAK: {EvidenceKind.COUNTER, EvidenceKind.MIXED},
            ObservationLabel.NEUTRAL: {EvidenceKind.MIXED},
            ObservationLabel.SUPPORTED: {EvidenceKind.SUPPORTING, EvidenceKind.MIXED},
            ObservationLabel.STRONG: {EvidenceKind.SUPPORTING},
        }[self.label]
        if not any(item.kind in expected_kinds for item in self.evidence):
            raise ValueError("observation evidence kind does not support its label")
        return self


class FollowUpQuestion(StrictModel):
    trigger: FollowUpTrigger
    prompt: str = Field(min_length=1, max_length=1_000)
    reason: str = Field(min_length=1, max_length=1_000)
    criterion_ids: list[str] = Field(min_length=1, max_length=4)
    requirement_ids: list[str] = Field(min_length=1, max_length=4)
    resume_claim_ids: list[str] = Field(default_factory=list, max_length=4)


class LiveCodingChallenge(StrictModel):
    trigger: LiveCodingTrigger
    prompt: str = Field(min_length=1, max_length=2_000)
    reason: str = Field(min_length=1, max_length=1_000)
    criterion_ids: list[str] = Field(min_length=1, max_length=4)
    requirement_ids: list[str] = Field(min_length=1, max_length=4)
    resume_claim_ids: list[str] = Field(min_length=1, max_length=4)


class AnswerAssessmentOutput(StrictModel):
    schema_version: Literal["session_agent_output_v2"] = AGENT_OUTPUT_VERSION
    purpose: Literal["answer_assessment"] = AgentPurpose.ANSWER_ASSESSMENT
    response_id: UUID
    question_id: UUID
    observations: list[CriterionObservation] = Field(min_length=1)
    follow_up: list[FollowUpQuestion] | None = Field(
        default=None,
        min_length=1,
        max_length=2,
    )
    live_coding: LiveCodingChallenge | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_follow_up(cls, value: Any) -> Any:
        """Read v2 artifacts that stored one follow-up object."""

        if not isinstance(value, dict):
            return value
        follow_up = value.get("follow_up")
        if follow_up is None or isinstance(follow_up, list):
            return value
        normalized = dict(value)
        normalized["follow_up"] = [follow_up]
        return normalized

    @model_validator(mode="after")
    def validate_single_conditional_section(self) -> Self:
        if self.follow_up is not None and self.live_coding is not None:
            raise ValueError("only one conditional interview section may be requested")
        return self


class AlternativeVacancyMatchOutput(StrictModel):
    schema_version: Literal["session_agent_output_v2"] = AGENT_OUTPUT_VERSION
    purpose: Literal["alternative_vacancy_match"] = (
        AgentPurpose.ALTERNATIVE_VACANCY_MATCH
    )
    target_vacancy_id: UUID
    candidate_grade: SeniorityBand
    target_grade: SeniorityBand
    compatibility_status: AlternativeCompatibility
    fit_value: float | None = Field(default=None, ge=-1, le=1)
    matched_criteria: list[str]
    matched_terms: list[str]
    gaps: list[str]
    evidence_references: list[str]
    explanation: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_compatibility_value(self) -> Self:
        compatible = self.compatibility_status is AlternativeCompatibility.COMPATIBLE
        if compatible and self.fit_value is None:
            raise ValueError("compatible match requires fit_value")
        if not compatible and self.fit_value is not None:
            raise ValueError("manual comparison cannot expose a fit_value")
        return self


class IntegrityObservation(StrictModel):
    status: IntegrityStatus
    resume_evidence_id: str | None = Field(default=None, max_length=120)
    answer_evidence_id: str | None = Field(default=None, max_length=120)
    response_id: UUID | None = None
    explanation: str = Field(min_length=1, max_length=2_000)
    clarification_question: str | None = Field(default=None, max_length=1_000)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_two_sided_contradiction(self) -> Self:
        if self.status in {
            IntegrityStatus.CONTRADICTION_DETECTED,
            IntegrityStatus.MANUAL_INTEGRITY_REVIEW,
        } and (
            not self.resume_evidence_id
            or not self.answer_evidence_id
            or not self.response_id
        ):
            raise ValueError("contradiction requires resume and answer evidence")
        if self.answer_evidence_id and not self.response_id:
            raise ValueError("answer evidence requires a response id")
        if (
            self.status is IntegrityStatus.UNVERIFIED_CLAIM
            and not self.resume_evidence_id
        ):
            raise ValueError("unverified claim requires resume evidence")
        return self


class IntegrityCheckOutput(StrictModel):
    schema_version: Literal["session_agent_output_v2"] = AGENT_OUTPUT_VERSION
    purpose: Literal["integrity_check"] = AgentPurpose.INTEGRITY_CHECK
    observations: list[IntegrityObservation]
    is_restriction: Literal[False] = False


class CandidateFeedbackPoint(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    detail: str = Field(min_length=1, max_length=2_000)
    evidence_references: list[str] = Field(min_length=1, max_length=5)


class CandidateGrowthArea(CandidateFeedbackPoint):
    action: str = Field(min_length=1, max_length=2_000)


class CandidateExperienceAlignment(CandidateFeedbackPoint):
    status: ExperienceAlignmentStatus


class CandidateAlternativeRecommendation(StrictModel):
    vacancy_id: UUID
    title: str = Field(min_length=1, max_length=500)
    matched_areas: list[str] = Field(min_length=1, max_length=10)
    message: str = Field(min_length=1, max_length=2_000)
    is_automatic_transfer: Literal[False] = False


class CandidateFeedbackOutput(StrictModel):
    schema_version: Literal["candidate_feedback_v1"] = FEEDBACK_VERSION
    purpose: Literal["candidate_feedback"] = AgentPurpose.CANDIDATE_FEEDBACK
    source_profile_artifact_id: UUID
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=4_000)
    strengths: list[CandidateFeedbackPoint] = Field(max_length=6)
    growth_areas: list[CandidateGrowthArea] = Field(min_length=1, max_length=6)
    experience_alignment: list[CandidateExperienceAlignment] = Field(max_length=12)
    alternative_vacancy: CandidateAlternativeRecommendation | None = None
    next_steps: list[str] = Field(min_length=1, max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=6)
    is_hiring_decision: Literal[False] = False


class CriterionSummary(StrictModel):
    criterion_id: str
    dimension: Dimension
    value: float | None = Field(default=None, ge=-1, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    observation_count: int = Field(ge=0)
    evidence_references: list[str]


class DimensionSummary(StrictModel):
    dimension: Dimension
    value: float | None = Field(default=None, ge=-1, le=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    assessed_criteria: int = Field(ge=0)
    applicable_criteria: int = Field(ge=0)
    coverage: float = Field(ge=0, le=1)


class CandidateProfilePayload(StrictModel):
    schema_version: Literal["candidate_profile_v1"] = AGGREGATION_VERSION
    selected_assessment_artifact_ids: list[UUID]
    resume_positions: list[ResumePosition]
    resume_claims: list[ResumeClaim]
    criterion_summaries: list[CriterionSummary]
    dimension_summaries: list[DimensionSummary]
    overall_readiness: float | None = Field(default=None, ge=-1, le=1)
    overall_confidence: float | None = Field(default=None, ge=0, le=1)
    overall_coverage: float = Field(ge=0, le=1)
    strong_pool_eligible: bool
    eligibility_reason_codes: list[str]
    integrity_review_required: bool
    compatibility_key: str = Field(min_length=64, max_length=64)
    is_hiring_decision: Literal[False] = False


class ArtifactView(StrictModel):
    id: UUID
    kind: ArtifactKind
    schema_version: str
    content_hash: str
    payload: dict[str, Any]
    created_at: datetime


class SessionVersions(StrictModel):
    resume_id: UUID | None = None
    resume_version: int | None = None
    resume_hash: str | None = None
    manager_brief_id: UUID | None = None
    manager_brief_version: int | None = None
    manager_brief_hash: str | None = None
    vacancy_hash: str
    criteria_version: str
    scale_version: str
    aggregation_version: str
    policy_version: str


class AgentSessionView(StrictModel):
    id: UUID
    invitation_id: UUID
    vacancy_id: UUID
    interview_session_id: UUID | None = None
    input_hash: str
    status: AgentSessionStatus
    versions: SessionVersions
    artifacts: list[ArtifactView]
    created_at: datetime
    updated_at: datetime


class CandidateQuestionView(StrictModel):
    question_id: UUID
    prompt: str
    kind: QuestionKind


class CandidateQuestionPlanView(StrictModel):
    agent_session_id: UUID
    questions: list[CandidateQuestionView]


class LiveCodingSubmissionView(StrictModel):
    response_id: UUID
    question_id: UUID
    status: Literal["completed"] = "completed"


class RankingEntryView(StrictModel):
    rank: int = Field(ge=1)
    agent_session_id: UUID
    candidate_alias: str | None = None
    overall_value: float = Field(ge=-1, le=1)
    coverage: float = Field(ge=0, le=1)


class RankingView(StrictModel):
    vacancy_id: UUID
    compatibility_key: str | None = None
    entries: list[RankingEntryView]
    created_at: datetime | None = None


class FinalizationView(StrictModel):
    profile: ArtifactView
    integrity: ArtifactView
    alternative_matches: list[ArtifactView]
    ranking: RankingView


class CandidateFeedbackScoreView(StrictModel):
    value: float | None = Field(default=None, ge=0, le=10)
    maximum: Literal[10] = 10
    scale_version: Literal["signed_readiness_to_10_v1"] = CANDIDATE_SCORE_VERSION
    evidence_coverage: float = Field(ge=0, le=1)
    explanation: str


class CandidateFeedbackEvidenceView(StrictModel):
    excerpt: str | None = None


class CandidateFeedbackPointView(StrictModel):
    title: str
    detail: str
    evidence: list[CandidateFeedbackEvidenceView]


class CandidateGrowthAreaView(CandidateFeedbackPointView):
    action: str


class CandidateExperienceAlignmentView(CandidateFeedbackPointView):
    status: ExperienceAlignmentStatus


class CandidateFeedbackContentView(StrictModel):
    score: CandidateFeedbackScoreView
    headline: str
    summary: str
    strengths: list[CandidateFeedbackPointView]
    growth_areas: list[CandidateGrowthAreaView]
    experience_alignment: list[CandidateExperienceAlignmentView]
    alternative_vacancy: CandidateAlternativeRecommendation | None = None
    next_steps: list[str]
    limitations: list[str]
    published_at: datetime


class CandidateFeedbackDeliveryView(StrictModel):
    status: Literal["pending_review", "published"]
    feedback: CandidateFeedbackContentView | None = None

    @model_validator(mode="after")
    def validate_delivery_state(self) -> Self:
        if self.status == "published" and self.feedback is None:
            raise ValueError("published feedback delivery requires content")
        if self.status == "pending_review" and self.feedback is not None:
            raise ValueError("pending feedback delivery cannot expose content")
        return self


class CandidateFeedbackReleaseView(StrictModel):
    id: UUID
    invitation_id: UUID
    agent_session_id: UUID
    status: FeedbackReleaseStatus
    artifact: ArtifactView
    created_by: str
    created_at: datetime
    published_by: str | None = None
    published_at: datetime | None = None


class CreateRestrictionRequest(StrictModel):
    decision_type: RestrictionType
    reason: str = Field(min_length=1, max_length=2_000)
    evidence_references: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    supersedes_id: UUID | None = None

    @model_validator(mode="after")
    def require_evidence_for_restriction(self) -> Self:
        if self.decision_type is not RestrictionType.CLEARED and not self.evidence_references:
            raise ValueError("restriction decision requires evidence references")
        if self.decision_type is RestrictionType.CLEARED and self.supersedes_id is None:
            raise ValueError("cleared decision must supersede a prior decision")
        return self


class RestrictionDecisionView(StrictModel):
    id: UUID
    invitation_id: UUID
    decision_type: RestrictionType
    reason: str
    evidence_references: list[str]
    created_by: str
    created_at: datetime
    expires_at: datetime | None = None
    supersedes_id: UUID | None = None


class RestrictionListView(StrictModel):
    decisions: list[RestrictionDecisionView]


class StructuredInterviewAgent(Protocol):
    purpose: AgentPurpose
    model_id: str
    model_version: str
    prompt_id: str

    def run(self, context: dict[str, Any]) -> BaseModel | dict[str, Any]: ...


class MultiAgentError(Exception):
    code = "multi_agent_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MultiAgentNotFoundError(MultiAgentError):
    code = "multi_agent_not_found"


class MultiAgentConflictError(MultiAgentError):
    code = "multi_agent_conflict"


class MultiAgentValidationError(MultiAgentError):
    code = "multi_agent_validation_failed"


class MultiAgentProviderError(MultiAgentError):
    code = "multi_agent_provider_failed"


class MultiAgentOutputError(MultiAgentValidationError):
    code = "multi_agent_output_invalid"
