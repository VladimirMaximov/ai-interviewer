"""Durable orchestration, validation, scoring, ranking, and human review."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, ValidationError as PydanticValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.manager_brief import ConfirmationStatus, ManagerBriefStatus
from app.domain.multi_agent import (
    AGGREGATION_VERSION,
    AGENT_OUTPUT_VERSION,
    CRITERIA_VERSION,
    POLICY_VERSION,
    SCALE_VERSION,
    AgentOperationStatus,
    AgentPurpose,
    AgentRunStatus,
    AgentSessionStatus,
    AgentSessionView,
    AlternativeCompatibility,
    AlternativeVacancyMatchOutput,
    AnswerAssessmentOutput,
    ArtifactKind,
    ArtifactView,
    CandidateFeedbackContentView,
    CandidateFeedbackDeliveryView,
    CandidateFeedbackEvidenceView,
    CandidateFeedbackOutput,
    CandidateFeedbackPointView,
    CandidateFeedbackReleaseView,
    CandidateFeedbackScoreView,
    CandidateExperienceAlignmentView,
    CandidateGrowthAreaView,
    CandidateProfilePayload,
    CandidateQuestionPlanView,
    CandidateQuestionView,
    CreateRestrictionRequest,
    CriterionDefinition,
    CriterionObservation,
    CriterionSummary,
    Dimension,
    DimensionSummary,
    EVIDENCE_CATALOG_VERSION,
    FEEDBACK_VERSION,
    FeedbackReleaseStatus,
    FinalizationView,
    FollowUpTrigger,
    IntegrityCheckOutput,
    IntegrityStatus,
    LiveCodingSubmissionView,
    MultiAgentConflictError,
    MultiAgentNotFoundError,
    MultiAgentOutputError,
    MultiAgentProviderError,
    MultiAgentValidationError,
    ObservationLabel,
    QuestionKind,
    QuestionPlanOutput,
    QuestionSelection,
    RankingEntryView,
    RankingView,
    RestrictionDecisionView,
    RestrictionListView,
    RestrictionType,
    RequirementOrigin,
    ResumeClaimType,
    ResumeRelevanceOutput,
    SeniorityBand,
    SessionVersions,
    StructuredInterviewAgent,
)
from app.models.hiring_context import CandidateResume, Vacancy
from app.domain.hiring_context import VacancyStatus
from app.models.interview import (
    CandidateResponse,
    CodeAnswer,
    InterviewInvitation,
    InterviewSession,
    TranscriptionStatus,
)
from app.interview_config import QuestionKind as ConfigQuestionKind, invitation_input
from app.models.manager_brief import ManagerBriefDraft
from app.models.multi_agent import (
    AgentArtifact,
    AgentOperation,
    AgentRun,
    AgentSession,
    CandidateFeedbackRelease,
    RankingEntry,
    RankingSnapshot,
    RestrictionDecision,
)
from app.security.invitations import digest_invitation_secret


OUTPUT_TYPES: dict[AgentPurpose, type[BaseModel]] = {
    AgentPurpose.RESUME_RELEVANCE: ResumeRelevanceOutput,
    AgentPurpose.QUESTION_PLAN: QuestionPlanOutput,
    AgentPurpose.ANSWER_ASSESSMENT: AnswerAssessmentOutput,
    AgentPurpose.ALTERNATIVE_VACANCY_MATCH: AlternativeVacancyMatchOutput,
    AgentPurpose.INTEGRITY_CHECK: IntegrityCheckOutput,
    AgentPurpose.CANDIDATE_FEEDBACK: CandidateFeedbackOutput,
}

PROHIBITED_TRAIT_PATTERN = re.compile(
    r"\b(age|возраст\w*|gender|sex|пол|nationality|национальн\w*|accent|"
    r"акцент\w*\s+(?:реч\w*|произнош\w*)|"
    r"emotion\w*|эмоци\w*|voice confidence|уверенность голоса|family status|семейн\w*|"
    r"religion|религи\w*|disability|инвалид\w*|health|здоров\w*)\b",
    re.IGNORECASE,
)
PROHIBITED_INTEGRITY_DECISION_PATTERN = re.compile(
    r"\b(blacklist\w*|бл[эе]клист\w*|fraud\w*|мошеннич\w*|lie|lying|лж[её]т|ложь)\b",
    re.IGNORECASE,
)
PROHIBITED_CANDIDATE_FEEDBACK_PATTERN = re.compile(
    r"\b(blacklist\w*|бл[эе]клист\w*|candidate_pool|strong_pool|integrity|"
    r"антифрод\w*|fraud\w*|мошеннич\w*|rank(?:ing)?|рейтинг\w*)\b",
    re.IGNORECASE,
)
GRADE_ORDER = {
    SeniorityBand.INTERN: 0,
    SeniorityBand.JUNIOR: 1,
    SeniorityBand.MIDDLE: 2,
    SeniorityBand.SENIOR: 3,
    SeniorityBand.LEAD: 4,
}
FOLLOW_UP_MAX_QUESTIONS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _required_text(value: str, name: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise MultiAgentValidationError(f"{name} is required")
    if len(normalized) > maximum:
        raise MultiAgentValidationError(f"{name} exceeds {maximum} characters")
    return normalized


class MultiAgentHarness:
    """Coordinate isolated LLM stages and deterministic downstream decisions."""

    def __init__(
        self,
        session: Session,
        agents: dict[AgentPurpose, StructuredInterviewAgent],
        *,
        max_attempts: int = 3,
        strong_pool_min_readiness: float = 0.25,
        strong_pool_min_coverage: float = 0.5,
        alternative_min_fit: float = 0.25,
        alternative_max_grade_distance: int = 1,
        personalization_cap: int = 3,
        follow_up_confidence_threshold: float = 0.65,
        follow_up_max_per_session: int = FOLLOW_UP_MAX_QUESTIONS,
    ) -> None:
        if not 0 <= follow_up_confidence_threshold <= 1:
            raise ValueError("follow-up confidence threshold must be in [0, 1]")
        if not 1 <= follow_up_max_per_session <= FOLLOW_UP_MAX_QUESTIONS:
            raise ValueError("follow-up session cap must be in [1, 2]")
        missing = set(AgentPurpose) - set(agents)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"all LLM agent stages are required; missing: {names}")
        self.db = session
        self.agents = agents
        self.max_attempts = max_attempts
        self.policy = {
            "policy_version": POLICY_VERSION,
            "strong_pool_min_readiness": strong_pool_min_readiness,
            "strong_pool_min_coverage": strong_pool_min_coverage,
            "alternative_min_fit": alternative_min_fit,
            "alternative_max_grade_distance": alternative_max_grade_distance,
            "personalization_cap": personalization_cap,
            "follow_up_confidence_threshold": follow_up_confidence_threshold,
            "follow_up_max_per_session": follow_up_max_per_session,
            "live_coding_max_per_session": 1,
            "automatic_hiring_decision_forbidden": True,
            "automatic_restriction_forbidden": True,
        }

    def close(self) -> None:
        self.db.close()

    def create_session(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        idempotency_key: str,
    ) -> AgentSessionView:
        actor = _required_text(actor_id, "actor id", 120)
        key = _required_text(idempotency_key, "idempotency key", 128)
        if len(key) < 8:
            raise MultiAgentValidationError(
                "idempotency key must contain at least 8 characters"
            )
        vacancy, invitation = self._scoped_application(vacancy_id, invitation_id)
        existing = self.db.scalar(
            select(AgentSession).where(AgentSession.invitation_id == invitation.id)
        )

        resume = self.db.scalar(
            select(CandidateResume)
            .where(
                CandidateResume.invitation_id == invitation.id,
                CandidateResume.vacancy_id == vacancy.id,
            )
            .order_by(CandidateResume.version.desc(), CandidateResume.id.desc())
        )
        brief = self.db.scalar(
            select(ManagerBriefDraft)
            .where(
                ManagerBriefDraft.vacancy_id == vacancy.id,
                ManagerBriefDraft.status == ManagerBriefStatus.APPROVED,
            )
            .order_by(ManagerBriefDraft.version.desc(), ManagerBriefDraft.id.desc())
        )
        interview = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation.id
            )
        )
        pinned = {
            "invitation_id": str(invitation.id),
            "vacancy_id": str(vacancy.id),
            "vacancy_hash": vacancy.content_hash,
            "resume_id": str(resume.id) if resume else None,
            "resume_version": resume.version if resume else None,
            "resume_hash": resume.content_hash if resume else None,
            "manager_brief_id": str(brief.id) if brief else None,
            "manager_brief_version": brief.version if brief else None,
            "manager_brief_hash": brief.content_hash if brief else None,
            "criteria_version": CRITERIA_VERSION,
            "scale_version": SCALE_VERSION,
            "aggregation_version": AGGREGATION_VERSION,
            "policy": self.policy,
        }
        input_hash = _canonical_hash(pinned)
        if existing is not None:
            if existing.input_hash != input_hash:
                raise MultiAgentConflictError(
                    "agent session already pins a different input version"
                )
            return self._session_view(existing)

        request_collision = self.db.scalar(
            select(AgentSession).where(
                AgentSession.vacancy_id == vacancy.id,
                AgentSession.created_by == actor,
                AgentSession.idempotency_key == key,
            )
        )
        if request_collision is not None:
            raise MultiAgentConflictError(
                "idempotency key was already used for another application"
            )

        now = _now()
        model = AgentSession(
            invitation_id=invitation.id,
            vacancy_id=vacancy.id,
            interview_session_id=interview.id if interview else None,
            resume_id=resume.id if resume else None,
            resume_version=resume.version if resume else None,
            resume_hash=resume.content_hash if resume else None,
            manager_brief_id=brief.id if brief else None,
            manager_brief_version=brief.version if brief else None,
            manager_brief_hash=brief.content_hash if brief else None,
            vacancy_hash=vacancy.content_hash,
            criteria_version=CRITERIA_VERSION,
            scale_version=SCALE_VERSION,
            aggregation_version=AGGREGATION_VERSION,
            policy_version=POLICY_VERSION,
            policy_payload=self.policy,
            input_hash=input_hash,
            status=AgentSessionStatus.ACTIVE,
            created_by=actor,
            idempotency_key=key,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(AgentSession).where(
                    AgentSession.invitation_id == invitation.id
                )
            )
            if concurrent is not None and concurrent.input_hash == input_hash:
                return self._session_view(concurrent)
            raise MultiAgentConflictError(
                "agent session conflicted with a concurrent request"
            ) from error
        self.db.refresh(model)
        return self._session_view(model)

    def get_session(
        self, *, vacancy_id: UUID, invitation_id: UUID
    ) -> AgentSessionView:
        model = self._session_model(vacancy_id, invitation_id)
        return self._session_view(model)

    def candidate_question_plan(
        self, *, secret: str
    ) -> CandidateQuestionPlanView | None:
        if not secret:
            return None
        invitation = self.db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.token_digest == digest_invitation_secret(secret)
            )
        )
        if (
            invitation is None
            or invitation.status.value != "active"
            or _aware(invitation.expires_at) <= _now()
        ):
            return None
        agent_session = self.db.scalar(
            select(AgentSession).where(
                AgentSession.invitation_id == invitation.id
            )
        )
        if agent_session is None:
            return None
        artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=False
        )
        if artifact is None:
            return None
        plan = QuestionPlanOutput.model_validate(artifact.payload)
        questions = self._session_questions(agent_session, plan)
        return CandidateQuestionPlanView(
            agent_session_id=agent_session.id,
            questions=[
                CandidateQuestionView(
                    question_id=item.question_id,
                    prompt=item.prompt,
                    kind=item.kind,
                )
                for item in questions
            ],
        )

    def submit_live_coding(
        self,
        *,
        secret: str,
        question_id: UUID,
        code: str,
    ) -> LiveCodingSubmissionView | None:
        if not secret:
            return None
        invitation = self.db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.token_digest == digest_invitation_secret(secret)
            )
        )
        if (
            invitation is None
            or invitation.status.value != "active"
            or _aware(invitation.expires_at) <= _now()
        ):
            return None
        agent_session = self.db.scalar(
            select(AgentSession).where(AgentSession.invitation_id == invitation.id)
        )
        interview = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation.id
            )
        )
        if (
            agent_session is None
            or interview is None
            or interview.consented_at is None
        ):
            return None
        plan_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=False
        )
        if plan_artifact is None:
            return None
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        question = next(
            (
                item
                for item in self._session_questions(agent_session, plan)
                if item.question_id == question_id
            ),
            None,
        )
        if question is None or question.kind is not QuestionKind.LIVE_CODING:
            raise MultiAgentValidationError(
                "code can only be submitted for the active live-coding question"
            )
        if len(code.strip()) < 4:
            raise MultiAgentValidationError(
                "live-coding solution must contain at least 4 characters"
            )
        if len(code) > 30_000:
            raise MultiAgentValidationError(
                "live-coding solution exceeds 30000 characters"
            )
        normalized_code = code
        existing = self.db.scalar(
            select(CandidateResponse)
            .where(
                CandidateResponse.session_id == interview.id,
                CandidateResponse.question_id == question_id,
            )
            .order_by(CandidateResponse.created_at, CandidateResponse.id)
        )
        if existing is not None:
            if (
                existing.content_type == "text/plain"
                and existing.transcript_text == normalized_code
                and existing.transcription_status is TranscriptionStatus.COMPLETED
            ):
                return LiveCodingSubmissionView(
                    response_id=existing.id,
                    question_id=existing.question_id,
                )
            raise MultiAgentConflictError(
                "a live-coding solution was already submitted for this interview"
            )
        response_id = uuid4()
        response = CandidateResponse(
            id=response_id,
            session_id=interview.id,
            question_id=question_id,
            storage_key=f"live-coding/{interview.id}/{response_id}.txt",
            content_type="text/plain",
            checksum=hashlib.sha256(normalized_code.encode("utf-8")).hexdigest(),
            transcription_status=TranscriptionStatus.COMPLETED,
            transcript_text=normalized_code,
            created_at=_now(),
        )
        self.db.add(response)
        self.db.commit()
        return LiveCodingSubmissionView(
            response_id=response.id,
            question_id=response.question_id,
        )

    def candidate_feedback(
        self, *, secret: str
    ) -> CandidateFeedbackDeliveryView | None:
        """Return only the latest human-published candidate-safe feedback."""

        if not secret:
            return None
        invitation = self.db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.token_digest == digest_invitation_secret(secret)
            )
        )
        if invitation is None or invitation.status.value not in {"active", "submitted"}:
            return None
        release = self.db.scalar(
            select(CandidateFeedbackRelease)
            .where(
                CandidateFeedbackRelease.invitation_id == invitation.id,
                CandidateFeedbackRelease.status == FeedbackReleaseStatus.PUBLISHED,
            )
            .order_by(
                CandidateFeedbackRelease.published_at.desc(),
                CandidateFeedbackRelease.id.desc(),
            )
        )
        if release is None:
            return CandidateFeedbackDeliveryView(
                status="pending_review", feedback=None
            )
        return CandidateFeedbackDeliveryView(
            status="published",
            feedback=self._candidate_feedback_content(release),
        )

    def generate_candidate_feedback(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        actor_id: str,
        idempotency_key: str,
    ) -> CandidateFeedbackReleaseView:
        """Generate an evidence-linked draft from candidate-safe agent inputs."""

        actor = _required_text(actor_id, "actor id", 120)
        key = _required_text(idempotency_key, "idempotency key", 128)
        agent_session = self._session_model(vacancy_id, invitation_id)
        if agent_session.status is not AgentSessionStatus.READY:
            raise MultiAgentConflictError(
                "candidate profile must be finalized before feedback generation"
            )
        vacancy = self.db.get(Vacancy, vacancy_id)
        resume_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.RESUME_RELEVANCE, required=True
        )
        plan_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=True
        )
        profile_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.CANDIDATE_PROFILE, required=True
        )
        assessments = self._assessment_artifacts(agent_session.id)
        if not assessments:
            raise MultiAgentConflictError(
                "answer assessments are required before feedback generation"
            )
        profile = CandidateProfilePayload.model_validate(profile_artifact.payload)
        evidence_catalog = self._feedback_evidence_catalog(
            resume_artifact, plan_artifact, assessments
        )
        alternatives = self._feedback_alternatives(agent_session, profile)
        profile_payload = profile.model_dump(mode="json")
        candidate_safe_profile = {
            "schema_version": profile_payload["schema_version"],
            "criterion_summaries": [
                {
                    **item,
                    "evidence_references": [
                        self._feedback_reference(reference)
                        for reference in item["evidence_references"]
                    ],
                }
                for item in profile_payload["criterion_summaries"]
            ],
            "dimension_summaries": profile_payload["dimension_summaries"],
            "overall_coverage": profile_payload["overall_coverage"],
        }
        context = {
            "schema_version": "candidate_feedback_input_v1",
            "session_id": str(agent_session.id),
            "source_profile_artifact_id": str(profile_artifact.id),
            "primary_vacancy": {
                "id": str(vacancy.id),
                "title": vacancy.title,
                "untrusted_text": vacancy.extracted_text,
                "approved_manager_brief": self._approved_brief_payload(agent_session),
            },
            "upstream_agent_results": {
                "resume_relevance": {
                    "artifact_id": str(resume_artifact.id),
                    "output": resume_artifact.payload,
                },
                "question_plan": {
                    "artifact_id": str(plan_artifact.id),
                    "output": plan_artifact.payload,
                },
                "answer_assessments": [
                    {
                        "artifact_id": str(item.id),
                        "output": item.payload,
                    }
                    for item in assessments
                ],
                "candidate_profile": {
                    "artifact_id": str(profile_artifact.id),
                    "output": candidate_safe_profile,
                },
                "candidate_score": self._candidate_score(profile),
                "alternative_vacancy_matches": alternatives,
            },
            "candidate_answers": self._integrity_answer_context(
                agent_session, assessments
            ),
            "evidence_catalog": evidence_catalog,
            "allowed_alternative_vacancies": alternatives,
            "publication_policy": {
                "human_review_required": True,
                "automatic_transfer_forbidden": True,
                "missing_evidence_is_not_absence_of_skill": True,
            },
            "policy": self._agent_policy(),
        }
        artifact = self._execute_agent(
            agent_session,
            AgentPurpose.CANDIDATE_FEEDBACK,
            key,
            context,
            lambda output: self._validate_candidate_feedback_output(
                output,
                profile_artifact,
                evidence_catalog,
                alternatives,
            ),
        )
        release = self.db.scalar(
            select(CandidateFeedbackRelease).where(
                CandidateFeedbackRelease.feedback_artifact_id == artifact.id
            )
        )
        if release is None:
            release = CandidateFeedbackRelease(
                invitation_id=invitation_id,
                agent_session_id=agent_session.id,
                feedback_artifact_id=artifact.id,
                status=FeedbackReleaseStatus.DRAFT,
                created_by=actor,
                created_at=_now(),
                published_by=None,
                published_at=None,
            )
            self.db.add(release)
            try:
                self.db.commit()
            except IntegrityError as error:
                self.db.rollback()
                release = self.db.scalar(
                    select(CandidateFeedbackRelease).where(
                        CandidateFeedbackRelease.feedback_artifact_id == artifact.id
                    )
                )
                if release is None:
                    raise MultiAgentConflictError(
                        "candidate feedback draft conflicted with another request"
                    ) from error
            self.db.refresh(release)
        return self._feedback_release_view(release)

    def publish_candidate_feedback(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        release_id: UUID,
        actor_id: str,
    ) -> CandidateFeedbackReleaseView:
        """Publish one reviewed immutable draft to the candidate token."""

        actor = _required_text(actor_id, "actor id", 120)
        if actor == "system":
            raise MultiAgentValidationError(
                "candidate feedback requires publication by an authorized human"
            )
        agent_session = self._session_model(vacancy_id, invitation_id)
        release = self.db.get(CandidateFeedbackRelease, release_id)
        if (
            release is None
            or release.invitation_id != invitation_id
            or release.agent_session_id != agent_session.id
        ):
            raise MultiAgentNotFoundError("candidate feedback draft was not found")
        if release.status is FeedbackReleaseStatus.PUBLISHED:
            return self._feedback_release_view(release)
        artifact = self.db.get(AgentArtifact, release.feedback_artifact_id)
        if artifact is None:
            raise MultiAgentConflictError("candidate feedback artifact is missing")
        output = CandidateFeedbackOutput.model_validate(artifact.payload)
        if output.alternative_vacancy is not None:
            target = self.db.get(Vacancy, output.alternative_vacancy.vacancy_id)
            if target is None or target.status is not VacancyStatus.ACTIVE:
                raise MultiAgentConflictError(
                    "recommended alternative vacancy is no longer active"
                )
            if self._active_restriction(invitation_id):
                raise MultiAgentConflictError(
                    "review the feedback again before publishing an alternative"
                )
        release.status = FeedbackReleaseStatus.PUBLISHED
        release.published_by = actor
        release.published_at = _now()
        self.db.commit()
        self.db.refresh(release)
        return self._feedback_release_view(release)

    def run_resume_analysis(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView:
        agent_session = self._session_model(vacancy_id, invitation_id)
        vacancy = self.db.get(Vacancy, vacancy_id)
        resume = (
            self.db.get(CandidateResume, agent_session.resume_id)
            if agent_session.resume_id
            else None
        )
        context = {
            "schema_version": "resume_relevance_input_v1",
            "evidence_catalog_version": EVIDENCE_CATALOG_VERSION,
            "session_id": str(agent_session.id),
            "vacancy": {
                "id": str(vacancy.id),
                "title": vacancy.title,
                "untrusted_text": vacancy.extracted_text,
                "content_hash": agent_session.vacancy_hash,
            },
            "approved_manager_brief": self._approved_brief_payload(agent_session),
            "resume": (
                {
                    "id": str(resume.id),
                    "version": resume.version,
                    "content_hash": resume.content_hash,
                    "untrusted_text": resume.extracted_text,
                }
                if resume
                else None
            ),
            "resume_evidence_catalog": (
                self._evidence_catalog(resume.extracted_text, "resume")
                if resume
                else []
            ),
            "policy": self._agent_policy(),
        }
        context["requirement_catalog"] = self._requirement_catalog(
            vacancy.extracted_text,
            context["approved_manager_brief"],
        )
        return self._execute_agent(
            agent_session,
            AgentPurpose.RESUME_RELEVANCE,
            idempotency_key,
            context,
            lambda output: self._validate_resume_output(
                output,
                resume,
                context["resume_evidence_catalog"],
                context["requirement_catalog"],
            ),
        )

    def run_question_plan(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView:
        agent_session = self._session_model(vacancy_id, invitation_id)
        vacancy = self.db.get(Vacancy, vacancy_id)
        resume_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.RESUME_RELEVANCE, required=True
        )
        baseline = self._baseline_questions(agent_session, vacancy)
        context = {
            "schema_version": "question_plan_input_v1",
            "session_id": str(agent_session.id),
            "vacancy": {
                "id": str(vacancy.id),
                "title": vacancy.title,
                "untrusted_text": vacancy.extracted_text,
            },
            "approved_manager_brief": self._approved_brief_payload(agent_session),
            "resume_relevance": resume_artifact.payload,
            "baseline_questions": [item.model_dump(mode="json") for item in baseline],
            "personalization_cap": int(agent_session.policy_payload["personalization_cap"]),
            "policy": self._agent_policy(),
        }
        return self._execute_agent(
            agent_session,
            AgentPurpose.QUESTION_PLAN,
            idempotency_key,
            context,
            lambda output: self._validate_question_plan(
                output,
                baseline,
                ResumeRelevanceOutput.model_validate(resume_artifact.payload),
                context["approved_manager_brief"],
                int(agent_session.policy_payload["personalization_cap"]),
            ),
        )

    def assess_answer(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        response_id: UUID,
        idempotency_key: str,
    ) -> ArtifactView:
        agent_session = self._session_model(vacancy_id, invitation_id)
        plan_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=True
        )
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        vacancy = self.db.get(Vacancy, vacancy_id)
        resume_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.RESUME_RELEVANCE, required=True
        )
        response = self.db.get(CandidateResponse, response_id)
        if response is None:
            raise MultiAgentNotFoundError("candidate response was not found")
        interview = self.db.get(InterviewSession, response.session_id)
        if interview is None or interview.invitation_id != invitation_id:
            raise MultiAgentNotFoundError("candidate response was not found in application")
        if (
            response.transcription_status is not TranscriptionStatus.COMPLETED
            or not response.transcript_text
            or not response.transcript_text.strip()
        ):
            raise MultiAgentConflictError(
                "a completed stored transcript is required before assessment"
            )
        question = next(
            (
                item
                for item in self._session_questions(agent_session, plan)
                if item.question_id == response.question_id
            ),
            None,
        )
        if question is None:
            raise MultiAgentConflictError(
                "candidate response does not belong to the pinned question plan"
            )
        approved_brief = self._approved_brief_payload(agent_session)
        requirement_catalog = self._requirement_catalog(
            vacancy.extracted_text,
            approved_brief,
        )
        follow_up_count = self._follow_up_count(agent_session.id)
        follow_up_limit = min(
            FOLLOW_UP_MAX_QUESTIONS,
            int(
                agent_session.policy_payload.get(
                    "follow_up_max_per_session",
                    FOLLOW_UP_MAX_QUESTIONS,
                )
            ),
        )
        follow_up_remaining = max(0, follow_up_limit - follow_up_count)
        follow_up_allowed = (
            question.kind
            not in {QuestionKind.FOLLOW_UP, QuestionKind.LIVE_CODING}
            and follow_up_remaining > 0
            and self._follow_up_enabled(interview, response.question_id)
        )
        confidence_threshold = float(
            agent_session.policy_payload.get(
                "follow_up_confidence_threshold", 0.65
            )
        )
        resume_relevance = ResumeRelevanceOutput.model_validate(
            resume_artifact.payload
        )
        eligible_live_coding_claim_ids = sorted(
            claim.claim_id
            for claim in resume_relevance.claims
            if claim.claim_type is ResumeClaimType.SKILL
        )
        live_coding_count = self._live_coding_count(agent_session.id)
        live_coding_allowed = (
            question.kind
            not in {QuestionKind.FOLLOW_UP, QuestionKind.LIVE_CODING}
            and live_coding_count == 0
            and bool(eligible_live_coding_claim_ids)
            and any(
                criterion.dimension is Dimension.TECHNICAL
                for criterion in question.criteria
            )
        )
        invitation = self.db.get(InterviewInvitation, invitation_id)
        configured = invitation_input(
            invitation.question_config, invitation.follow_up_after_all_answers
        )
        live_coding_allowed = live_coding_allowed and not any(
            item.kind is ConfigQuestionKind.CODING for item in configured.questions
        )
        configured_question = next(
            (item for item in configured.questions if item.id == response.question_id),
            None,
        )
        code_answer = self.db.scalar(select(CodeAnswer).where(
            CodeAnswer.response_id == response.id
        ))
        is_configured_coding = bool(
            configured_question
            and configured_question.kind is ConfigQuestionKind.CODING
            and code_answer
        )
        answer_text = (
            f"КОД:\n{code_answer.source_code}\n\n"
            f"УСТНОЕ ОБЪЯСНЕНИЕ:\n{response.transcript_text}"
            if is_configured_coding
            else response.transcript_text
        )
        question_payload = question.model_dump(mode="json")
        if code_answer:
            question_payload["kind"] = QuestionKind.LIVE_CODING.value
            question_payload["language"] = code_answer.language
            question_payload["spoken_context"] = response.transcript_text
        context = {
            "schema_version": "answer_assessment_input_v1",
            "evidence_catalog_version": EVIDENCE_CATALOG_VERSION,
            "session_id": str(agent_session.id),
            "response_id": str(response.id),
            "question_id": str(question.question_id),
            "question": question_payload,
            "answer_text": answer_text,
            "source_code": code_answer.source_code if code_answer else None,
            "spoken_text": response.transcript_text,
            "answer_evidence_catalog": self._evidence_catalog(
                answer_text,
                f"answer:{response.id}",
            ),
            "vacancy": {
                "id": str(vacancy.id),
                "title": vacancy.title,
                "untrusted_text": vacancy.extracted_text,
            },
            "requirement_catalog": requirement_catalog,
            "resume_relevance": resume_artifact.payload,
            "follow_up_policy": {
                "allowed": follow_up_allowed,
                "confidence_threshold": confidence_threshold,
                "remaining_in_session": follow_up_remaining,
                "min_questions_when_triggered": 1,
                "max_questions_this_answer": min(
                    FOLLOW_UP_MAX_QUESTIONS,
                    follow_up_remaining,
                ),
                "allowed_triggers": [
                    FollowUpTrigger.LOW_CONFIDENCE.value,
                    FollowUpTrigger.MISSING_DETAIL.value,
                ],
            },
            "live_coding_policy": {
                "allowed": live_coding_allowed,
                "remaining_in_session": 1 if live_coding_allowed else 0,
                "trigger": "claimed_technical_skill_not_demonstrated",
                "eligible_resume_claim_ids": eligible_live_coding_claim_ids,
            },
            "policy": self._agent_policy(),
        }
        return self._execute_agent(
            agent_session,
            AgentPurpose.ANSWER_ASSESSMENT,
            idempotency_key,
            context,
            lambda output: self._validate_answer_output(
                output,
                response,
                question,
                context["answer_evidence_catalog"],
                requirement_catalog,
                resume_relevance,
                follow_up_allowed,
                follow_up_remaining,
                confidence_threshold,
                live_coding_allowed,
            ),
        )

    def finalize(
        self,
        *,
        vacancy_id: UUID,
        invitation_id: UUID,
        idempotency_key: str,
    ) -> FinalizationView:
        key = _required_text(idempotency_key, "idempotency key", 128)
        agent_session = self._session_model(vacancy_id, invitation_id)
        resume_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.RESUME_RELEVANCE, required=True
        )
        plan_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=True
        )
        assessments = self._assessment_artifacts(agent_session.id)
        if not assessments:
            raise MultiAgentConflictError(
                "at least one answer assessment is required before finalization"
            )
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        if self._pending_conditional_questions(agent_session, plan):
            raise MultiAgentConflictError(
                "required follow-up and live-coding questions must be answered "
                "and assessed "
                "before finalization"
            )
        answer_context = self._integrity_answer_context(agent_session, assessments)
        integrity_context = {
            "schema_version": "integrity_check_input_v1",
            "evidence_catalog_version": EVIDENCE_CATALOG_VERSION,
            "session_id": str(agent_session.id),
            "resume_relevance": resume_artifact.payload,
            "resume_text": (
                self.db.get(CandidateResume, agent_session.resume_id).extracted_text
                if agent_session.resume_id
                else None
            ),
            "resume_evidence_catalog": self._resume_evidence_catalog(
                agent_session
            ),
            "answers": answer_context,
            "answer_evidence_catalogs": {
                item["response_id"]: self._evidence_catalog(
                    item["answer_text"],
                    f"answer:{item['response_id']}",
                )
                for item in answer_context
            },
            "policy": self._agent_policy(),
        }
        integrity = self._execute_agent(
            agent_session,
            AgentPurpose.INTEGRITY_CHECK,
            self._stage_key(key, "integrity"),
            integrity_context,
            lambda output: self._validate_integrity_output(
                output,
                integrity_context["resume_evidence_catalog"],
                integrity_context["answer_evidence_catalogs"],
            ),
        )
        profile_payload = self._build_profile(
            agent_session,
            ResumeRelevanceOutput.model_validate(resume_artifact.payload),
            QuestionPlanOutput.model_validate(plan_artifact.payload),
            assessments,
            IntegrityCheckOutput.model_validate(integrity.payload),
        )
        profile = self._materialize_deterministic_artifact(
            agent_session,
            ArtifactKind.CANDIDATE_PROFILE,
            AGGREGATION_VERSION,
            profile_payload,
        )

        alternative_matches: list[ArtifactView] = []
        if profile_payload.strong_pool_eligible:
            candidate_evidence = self._candidate_evidence(assessments, plan_artifact)
            candidate_manifest = {
                "criteria_version": agent_session.criteria_version,
                "scale_version": agent_session.scale_version,
                "aggregation_version": agent_session.aggregation_version,
            }
            target_manifest = {
                "criteria_version": CRITERIA_VERSION,
                "scale_version": SCALE_VERSION,
                "aggregation_version": AGGREGATION_VERSION,
            }
            active_vacancies = self.db.scalars(
                select(Vacancy)
                .where(Vacancy.status == VacancyStatus.ACTIVE, Vacancy.id != vacancy_id)
                .order_by(Vacancy.id)
            ).all()
            for target in active_vacancies:
                context = {
                    "schema_version": "alternative_vacancy_input_v1",
                    "session_id": str(agent_session.id),
                    "candidate_profile": profile_payload.model_dump(mode="json"),
                    "candidate_evidence": candidate_evidence,
                    "allowed_matched_criteria": sorted(
                        {item["criterion_id"] for item in candidate_evidence}
                    ),
                    "allowed_evidence_references": sorted(
                        {
                            item["evidence_reference"]
                            for item in candidate_evidence
                        }
                    ),
                    "candidate_compatibility_manifest": candidate_manifest,
                    "target_vacancy": {
                        "id": str(target.id),
                        "title": target.title,
                        "untrusted_text": target.extracted_text,
                        "content_hash": target.content_hash,
                        "approved_manager_brief": (
                            self._approved_brief_for_vacancy(target.id)
                        ),
                    },
                    "target_compatibility_manifest": target_manifest,
                    "grade_policy": {
                        "bands": [item.value for item in SeniorityBand],
                        "maximum_distance": int(
                            agent_session.policy_payload[
                                "alternative_max_grade_distance"
                            ]
                        ),
                    },
                    "policy": self._agent_policy(),
                }
                artifact = self._execute_agent(
                    agent_session,
                    AgentPurpose.ALTERNATIVE_VACANCY_MATCH,
                    self._stage_key(key, f"alternative:{target.id}"),
                    context,
                    lambda output, target=target: self._validate_alternative_output(
                        output,
                        target,
                        candidate_evidence,
                        candidate_manifest,
                        target_manifest,
                        int(
                            agent_session.policy_payload[
                                "alternative_max_grade_distance"
                            ]
                        ),
                    ),
                )
                parsed = AlternativeVacancyMatchOutput.model_validate(artifact.payload)
                if (
                    parsed.compatibility_status
                    is AlternativeCompatibility.COMPATIBLE
                    and parsed.fit_value is not None
                    and parsed.fit_value
                    >= float(agent_session.policy_payload["alternative_min_fit"])
                ):
                    alternative_matches.append(artifact)
            alternative_matches.sort(
                key=lambda item: (
                    -float(item.payload["fit_value"]),
                    item.payload["target_vacancy_id"],
                )
            )

        agent_session.status = AgentSessionStatus.READY
        agent_session.updated_at = _now()
        self.db.commit()
        ranking = self.build_ranking(vacancy_id=vacancy_id)
        return FinalizationView(
            profile=profile,
            integrity=integrity,
            alternative_matches=alternative_matches,
            ranking=ranking,
        )

    def build_ranking(self, *, vacancy_id: UUID) -> RankingView:
        vacancy = self.db.get(Vacancy, vacancy_id)
        if vacancy is None:
            raise MultiAgentNotFoundError("vacancy was not found")
        sessions = self.db.scalars(
            select(AgentSession)
            .where(
                AgentSession.vacancy_id == vacancy_id,
                AgentSession.status == AgentSessionStatus.READY,
            )
            .order_by(AgentSession.id)
        ).all()
        if not sessions:
            return RankingView(vacancy_id=vacancy_id, entries=[])
        session_ids = [item.id for item in sessions]
        artifacts = self.db.scalars(
            select(AgentArtifact)
            .where(
                AgentArtifact.agent_session_id.in_(session_ids),
                AgentArtifact.kind == ArtifactKind.CANDIDATE_PROFILE.value,
            )
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
        ).all()
        latest_profile_by_session: dict[UUID, AgentArtifact] = {}
        for artifact in artifacts:
            latest_profile_by_session[artifact.agent_session_id] = artifact
        invitation_ids = [item.invitation_id for item in sessions]
        restriction_rows = self.db.scalars(
            select(RestrictionDecision)
            .where(RestrictionDecision.invitation_id.in_(invitation_ids))
            .order_by(RestrictionDecision.created_at, RestrictionDecision.id)
        ).all()
        latest_restriction_by_invitation: dict[UUID, RestrictionDecision] = {}
        for decision in restriction_rows:
            latest_restriction_by_invitation[decision.invitation_id] = decision
        candidates: list[tuple[AgentSession, AgentArtifact, CandidateProfilePayload]] = []
        for item in sessions:
            artifact = latest_profile_by_session.get(item.id)
            restriction = latest_restriction_by_invitation.get(item.invitation_id)
            if artifact is None or self._restriction_is_active(restriction):
                continue
            payload = CandidateProfilePayload.model_validate(artifact.payload)
            if payload.overall_readiness is not None:
                candidates.append((item, artifact, payload))
        compatibility_key = self._compatibility_key(
            vacancy_id=vacancy.id,
            vacancy_hash=vacancy.content_hash,
            policy_payload=self.policy,
        )
        compatible = [
            item for item in candidates if item[2].compatibility_key == compatibility_key
        ]
        if not compatible:
            return RankingView(
                vacancy_id=vacancy_id,
                compatibility_key=compatibility_key,
                entries=[],
            )
        compatible.sort(
            key=lambda item: (
                -float(item[2].overall_readiness),
                -item[2].overall_coverage,
                str(item[0].id),
            )
        )
        input_hash = _canonical_hash(
            [
                {
                    "profile_id": str(artifact.id),
                    "profile_hash": artifact.content_hash,
                    "session_id": str(agent_session.id),
                }
                for agent_session, artifact, _ in compatible
            ]
        )
        snapshot = self.db.scalar(
            select(RankingSnapshot).where(
                RankingSnapshot.vacancy_id == vacancy_id,
                RankingSnapshot.input_hash == input_hash,
            )
        )
        if snapshot is None:
            snapshot = RankingSnapshot(
                vacancy_id=vacancy_id,
                compatibility_key=compatibility_key,
                input_hash=input_hash,
                created_at=_now(),
            )
            self.db.add(snapshot)
            self.db.flush()
            for rank, (agent_session, artifact, payload) in enumerate(
                compatible, start=1
            ):
                self.db.add(
                    RankingEntry(
                        snapshot_id=snapshot.id,
                        agent_session_id=agent_session.id,
                        profile_artifact_id=artifact.id,
                        rank=rank,
                        overall_value=float(payload.overall_readiness),
                        coverage=payload.overall_coverage,
                        tie_break_key=str(agent_session.id),
                    )
                )
            self.db.commit()
            self.db.refresh(snapshot)
        return self._ranking_view(snapshot)

    def create_restriction(
        self,
        *,
        invitation_id: UUID,
        actor_id: str,
        request: CreateRestrictionRequest,
    ) -> RestrictionDecisionView:
        actor = _required_text(actor_id, "actor id", 120)
        invitation = self.db.get(InterviewInvitation, invitation_id)
        if invitation is None:
            raise MultiAgentNotFoundError("application was not found")
        if request.expires_at is not None and _aware(request.expires_at) <= _now():
            raise MultiAgentValidationError("restriction expiry must be in the future")
        prior = None
        if request.supersedes_id is not None:
            prior = self.db.get(RestrictionDecision, request.supersedes_id)
            if prior is None or prior.invitation_id != invitation_id:
                raise MultiAgentNotFoundError("superseded restriction was not found")
            already_replaced = self.db.scalar(
                select(RestrictionDecision.id).where(
                    RestrictionDecision.supersedes_id == prior.id
                )
            )
            if already_replaced is not None:
                raise MultiAgentConflictError(
                    "restriction decision was already superseded"
                )
        elif request.decision_type is RestrictionType.CLEARED:
            raise MultiAgentValidationError(
                "cleared decision must supersede a prior restriction"
            )
        self._validate_restriction_evidence(invitation_id, request)
        decision = RestrictionDecision(
            invitation_id=invitation_id,
            decision_type=request.decision_type,
            reason=request.reason.strip(),
            evidence_references=request.evidence_references,
            created_by=actor,
            created_at=_now(),
            expires_at=request.expires_at,
            supersedes_id=prior.id if prior else None,
        )
        self.db.add(decision)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise MultiAgentConflictError(
                "restriction decision conflicted with another review"
            ) from error
        self.db.refresh(decision)
        return self._restriction_view(decision)

    def list_restrictions(self, *, invitation_id: UUID) -> RestrictionListView:
        if self.db.get(InterviewInvitation, invitation_id) is None:
            raise MultiAgentNotFoundError("application was not found")
        decisions = self.db.scalars(
            select(RestrictionDecision)
            .where(RestrictionDecision.invitation_id == invitation_id)
            .order_by(RestrictionDecision.created_at, RestrictionDecision.id)
        ).all()
        return RestrictionListView(
            decisions=[self._restriction_view(item) for item in decisions]
        )

    def _execute_agent(
        self,
        agent_session: AgentSession,
        purpose: AgentPurpose,
        idempotency_key: str,
        context: dict[str, Any],
        validate_output: Callable[[BaseModel], None],
    ) -> ArtifactView:
        key = _required_text(idempotency_key, "idempotency key", 220)
        if len(key) < 8:
            raise MultiAgentValidationError(
                "idempotency key must contain at least 8 characters"
            )
        input_hash = _canonical_hash(context)
        operation = self.db.scalar(
            select(AgentOperation).where(
                AgentOperation.agent_session_id == agent_session.id,
                AgentOperation.purpose == purpose.value,
                AgentOperation.idempotency_key == key,
            )
        )
        if operation is not None:
            if operation.input_hash != input_hash:
                raise MultiAgentConflictError(
                    "idempotency key was already used with different agent input"
                )
            if operation.status is AgentOperationStatus.SUCCEEDED:
                artifact = self.db.get(AgentArtifact, operation.output_artifact_id)
                if artifact is None:
                    raise MultiAgentConflictError(
                        "successful operation has no persisted artifact"
                    )
                return self._artifact_view(artifact)
        else:
            now = _now()
            operation = AgentOperation(
                agent_session_id=agent_session.id,
                purpose=purpose.value,
                idempotency_key=key,
                input_hash=input_hash,
                status=AgentOperationStatus.RUNNING,
                created_at=now,
                updated_at=now,
            )
            self.db.add(operation)
            self.db.flush()

        attempt = int(
            self.db.scalar(
                select(func.max(AgentRun.attempt)).where(
                    AgentRun.operation_id == operation.id
                )
            )
            or 0
        ) + 1
        if attempt > self.max_attempts:
            self.db.rollback()
            current_session = self.db.get(AgentSession, agent_session.id)
            current_session.status = AgentSessionStatus.FAILED
            current_session.updated_at = _now()
            self.db.commit()
            raise MultiAgentConflictError("agent operation exhausted its retry limit")
        agent = self.agents[purpose]
        run = AgentRun(
            operation_id=operation.id,
            attempt=attempt,
            status=AgentRunStatus.RUNNING,
            contract_version=(
                FEEDBACK_VERSION
                if purpose is AgentPurpose.CANDIDATE_FEEDBACK
                else AGENT_OUTPUT_VERSION
            ),
            model_id=agent.model_id,
            model_version=agent.model_version,
            prompt_id=agent.prompt_id,
            input_hash=input_hash,
            started_at=_now(),
        )
        operation.status = AgentOperationStatus.RUNNING
        operation.updated_at = _now()
        self.db.add(run)
        self.db.commit()

        raw_payload: dict[str, Any] | None = None
        try:
            raw_output = agent.run(context)
            if isinstance(raw_output, BaseModel):
                raw_payload = raw_output.model_dump(mode="json")
            elif isinstance(raw_output, dict):
                raw_payload = raw_output
            output_type = OUTPUT_TYPES[purpose]
            output = output_type.model_validate(raw_output)
            validate_output(output)
        except (PydanticValidationError, MultiAgentOutputError, ValueError) as error:
            self._fail_run(
                operation,
                run,
                AgentRunStatus.INVALID_OUTPUT,
                "invalid_output",
                output_payload=raw_payload,
            )
            if isinstance(error, MultiAgentOutputError):
                raise
            raise MultiAgentOutputError(
                f"{purpose.value} output failed local validation"
            ) from error
        except MultiAgentProviderError:
            self._fail_run(operation, run, AgentRunStatus.PROVIDER_FAILED, "provider_error")
            raise
        except Exception as error:
            self._fail_run(operation, run, AgentRunStatus.PROVIDER_FAILED, "provider_error")
            raise MultiAgentProviderError(
                f"{purpose.value} provider request failed"
            ) from error

        payload = output.model_dump(mode="json")
        output_hash = _canonical_hash(payload)
        artifact = self.db.scalar(
            select(AgentArtifact).where(
                AgentArtifact.agent_session_id == agent_session.id,
                AgentArtifact.kind == purpose.value,
                AgentArtifact.content_hash == output_hash,
            )
        )
        if artifact is None:
            artifact = AgentArtifact(
                agent_session_id=agent_session.id,
                operation_id=operation.id,
                kind=purpose.value,
                schema_version=(
                    FEEDBACK_VERSION
                    if purpose is AgentPurpose.CANDIDATE_FEEDBACK
                    else AGENT_OUTPUT_VERSION
                ),
                payload=payload,
                content_hash=output_hash,
                created_at=_now(),
            )
            self.db.add(artifact)
            self.db.flush()
        run.status = AgentRunStatus.SUCCEEDED
        run.output_hash = output_hash
        run.output_payload = payload
        run.completed_at = _now()
        operation.status = AgentOperationStatus.SUCCEEDED
        operation.output_artifact_id = artifact.id
        operation.updated_at = _now()
        self.db.commit()
        self.db.refresh(artifact)
        return self._artifact_view(artifact)

    def _validate_resume_output(
        self,
        output: BaseModel,
        resume: CandidateResume | None,
        resume_evidence_catalog: list[dict[str, str]],
        requirement_catalog: list[dict[str, str]],
    ) -> None:
        parsed = ResumeRelevanceOutput.model_validate(output)
        self._reject_sensitive_output(parsed)
        if resume is None:
            if parsed.positions or parsed.claims or parsed.experience_matches:
                raise MultiAgentOutputError(
                    "resume agent cannot create positions or claims without a resume"
                )
            return
        position_ids = [item.position_id for item in parsed.positions]
        if len(position_ids) != len(set(position_ids)):
            raise MultiAgentOutputError("resume agent returned duplicate position ids")
        known_evidence_ids = {
            item["evidence_id"] for item in resume_evidence_catalog
        }
        for position in parsed.positions:
            if len(position.evidence_ids) != len(set(position.evidence_ids)):
                raise MultiAgentOutputError(
                    "resume position contains duplicate evidence ids"
                )
            if not set(position.evidence_ids).issubset(known_evidence_ids):
                raise MultiAgentOutputError(
                    "resume position references an unknown evidence id"
                )
        claim_ids = [item.claim_id for item in parsed.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise MultiAgentOutputError("resume agent returned duplicate claim ids")
        for claim in parsed.claims:
            if len(claim.evidence_ids) != len(set(claim.evidence_ids)):
                raise MultiAgentOutputError(
                    "resume claim contains duplicate evidence ids"
                )
            if not set(claim.evidence_ids).issubset(known_evidence_ids):
                raise MultiAgentOutputError(
                    "resume claim references an unknown evidence id"
                )
        known_claims = set(claim_ids)
        relevances = [item.relevance for item in parsed.experience_matches]
        if relevances != sorted(relevances, reverse=True):
            raise MultiAgentOutputError(
                "experience matches must be ordered by descending relevance"
            )
        requirements = {
            item["requirement_id"]: item for item in requirement_catalog
        }
        for match in parsed.experience_matches:
            if len(match.evidence_ids) != len(set(match.evidence_ids)):
                raise MultiAgentOutputError(
                    "experience match contains duplicate evidence ids"
                )
            if not set(match.evidence_ids).issubset(known_evidence_ids):
                raise MultiAgentOutputError(
                    "experience match references an unknown resume evidence id"
                )
            if not set(match.claim_ids).issubset(known_claims):
                raise MultiAgentOutputError(
                    "experience match references an unknown resume claim"
                )
            if not match.position_ids or not set(match.position_ids).issubset(
                position_ids
            ):
                raise MultiAgentOutputError(
                    "experience match requires known resume positions"
                )
            requirement = requirements.get(match.requirement_id)
            if requirement is None:
                raise MultiAgentOutputError(
                    "experience match references an unknown requirement id"
                )
            if requirement["origin"] != match.requirement_origin.value:
                raise MultiAgentOutputError(
                    "experience match changed the requirement origin"
                )

    @staticmethod
    def _validate_question_plan(
        output: BaseModel,
        baseline: list[QuestionSelection],
        resume: ResumeRelevanceOutput,
        approved_brief: dict[str, Any] | None,
        personalization_cap: int,
    ) -> None:
        parsed = QuestionPlanOutput.model_validate(output)
        MultiAgentHarness._reject_sensitive_output(parsed)
        if len(parsed.questions) < len(baseline):
            raise MultiAgentOutputError("question plan omitted baseline questions")
        for expected, actual in zip(baseline, parsed.questions, strict=False):
            if actual != expected:
                raise MultiAgentOutputError(
                    "question planner changed a pinned baseline question"
                )
        additional = parsed.questions[len(baseline) :]
        if len(additional) > personalization_cap:
            raise MultiAgentOutputError("question planner exceeded personalization cap")
        question_ids = [item.question_id for item in parsed.questions]
        if len(question_ids) != len(set(question_ids)):
            raise MultiAgentOutputError("question planner returned duplicate question ids")
        known_claims = {item.claim_id for item in resume.claims}
        known_manager_fields = {
            item["field_key"]
            for item in (approved_brief or {}).get("confirmed_fields", [])
        }
        known_criteria = {
            item.criterion_id: item for question in baseline for item in question.criteria
        }
        for question in additional:
            if question.kind is not QuestionKind.PERSONALIZED:
                raise MultiAgentOutputError("additional question must be personalized")
            if not question.source_claim_ids and not question.source_manager_field_keys:
                raise MultiAgentOutputError(
                    "personalized question requires a resume claim or confirmed manager field"
                )
            if not set(question.source_claim_ids).issubset(known_claims):
                raise MultiAgentOutputError(
                    "personalized question references an unknown resume claim"
                )
            if not set(question.source_manager_field_keys).issubset(
                known_manager_fields
            ):
                raise MultiAgentOutputError(
                    "personalized question references an unconfirmed manager field"
                )
            for criterion in question.criteria:
                if known_criteria.get(criterion.criterion_id) != criterion:
                    raise MultiAgentOutputError(
                        "personalized question introduced or changed a criterion"
                    )

    @staticmethod
    def _verbatim_excerpt_options(text: str) -> list[str]:
        """Create bounded, exact source spans that an LLM can copy safely."""

        clauses = re.split(r"\n+|(?<=[.!?])\s+|(?<=,)\s+", text.strip())
        options: list[str] = []
        for clause in clauses:
            excerpt = clause.strip()
            if len(excerpt) < 4:
                continue
            exact_chunks = (
                [excerpt]
                if len(excerpt) <= 500
                else [excerpt[offset : offset + 500] for offset in range(0, len(excerpt), 500)]
            )
            for chunk in exact_chunks:
                if len(chunk) >= 4 and chunk not in options:
                    options.append(chunk)
                if len(options) >= 80:
                    return options
        return options

    @staticmethod
    def _evidence_catalog(
        text: str,
        namespace: str,
        *,
        limit: int = 80,
    ) -> list[dict[str, str]]:
        """Assign stable IDs to exact source fragments without asking an LLM to copy text."""

        return [
            {
                "evidence_id": f"{namespace}:{index:03d}",
                "text": excerpt,
            }
            for index, excerpt in enumerate(
                MultiAgentHarness._verbatim_excerpt_options(text)[:limit],
                start=1,
            )
        ]

    @staticmethod
    def _requirement_catalog(
        vacancy_text: str,
        approved_brief: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        catalog = [
            {
                "requirement_id": f"vacancy:{index:03d}",
                "origin": RequirementOrigin.VACANCY.value,
                "text": excerpt,
            }
            for index, excerpt in enumerate(
                MultiAgentHarness._verbatim_excerpt_options(vacancy_text),
                start=1,
            )
        ]
        for field in (approved_brief or {}).get("confirmed_fields", []):
            values = field["value"] if isinstance(field["value"], list) else [field["value"]]
            field_digest = hashlib.sha256(
                str(field["field_key"]).encode("utf-8")
            ).hexdigest()[:12]
            for index, value in enumerate(values, start=1):
                catalog.append(
                    {
                        "requirement_id": f"manager:{field_digest}:{index:03d}",
                        "origin": RequirementOrigin.MANAGER_BRIEF.value,
                        "text": str(value),
                    }
                )
        return catalog

    def _resume_evidence_catalog(
        self, agent_session: AgentSession
    ) -> list[dict[str, str]]:
        if agent_session.resume_id is None:
            return []
        resume = self.db.get(CandidateResume, agent_session.resume_id)
        if resume is None:
            raise MultiAgentConflictError("pinned resume is missing")
        return self._evidence_catalog(resume.extracted_text, "resume")

    @staticmethod
    def _validate_answer_output(
        output: BaseModel,
        response: CandidateResponse,
        question: QuestionSelection,
        answer_evidence_catalog: list[dict[str, str]],
        requirement_catalog: list[dict[str, str]],
        resume: ResumeRelevanceOutput,
        follow_up_allowed: bool,
        follow_up_remaining: int,
        confidence_threshold: float,
        live_coding_allowed: bool,
    ) -> None:
        parsed = AnswerAssessmentOutput.model_validate(output)
        MultiAgentHarness._reject_sensitive_output(parsed)
        if parsed.response_id != response.id or parsed.question_id != response.question_id:
            raise MultiAgentOutputError(
                "answer assessment changed response or question identity"
            )
        expected = {item.criterion_id: item for item in question.criteria}
        returned = [item.criterion_id for item in parsed.observations]
        if len(returned) != len(set(returned)) or set(returned) != set(expected):
            raise MultiAgentOutputError(
                "answer assessment must return every applicable criterion exactly once"
            )
        known_evidence_ids = {
            item["evidence_id"] for item in answer_evidence_catalog
        }
        for observation in parsed.observations:
            if observation.dimension is not expected[observation.criterion_id].dimension:
                raise MultiAgentOutputError(
                    "answer assessment changed the criterion dimension"
                )
            selected_ids = [
                evidence.evidence_id
                for evidence in observation.evidence
                if evidence.evidence_id is not None
            ]
            if len(selected_ids) != len(set(selected_ids)):
                raise MultiAgentOutputError(
                    "answer assessment contains duplicate evidence ids"
                )
            if not set(selected_ids).issubset(known_evidence_ids):
                raise MultiAgentOutputError(
                    "answer assessment references an unknown evidence id"
                )
        follow_ups = parsed.follow_up
        if follow_ups is None:
            MultiAgentHarness._validate_live_coding(
                parsed,
                question,
                requirement_catalog,
                resume,
                live_coding_allowed,
            )
            return
        if not follow_up_allowed:
            raise MultiAgentOutputError(
                "answer assessment cannot create a follow-up for this question"
            )
        if len(follow_ups) > min(FOLLOW_UP_MAX_QUESTIONS, follow_up_remaining):
            raise MultiAgentOutputError(
                "answer assessment exceeds the remaining follow-up limit"
            )
        low_confidence_criteria = {
            observation.criterion_id
            for observation in parsed.observations
            if observation.confidence < confidence_threshold
        }
        missing_detail_criteria = {
            observation.criterion_id
            for observation in parsed.observations
            if observation.label
            in {
                ObservationLabel.WEAK,
                ObservationLabel.NEUTRAL,
                ObservationLabel.INSUFFICIENT_INFORMATION,
            }
        }
        expected_criteria = {item.criterion_id for item in question.criteria}
        known_requirements = {
            item["requirement_id"] for item in requirement_catalog
        }
        known_claims = {item.claim_id for item in resume.claims}
        prompts: set[str] = set()
        for follow_up in follow_ups:
            if (
                follow_up.trigger is FollowUpTrigger.LOW_CONFIDENCE
                and not set(follow_up.criterion_ids).issubset(
                    low_confidence_criteria
                )
            ):
                raise MultiAgentOutputError(
                    "follow-up low-confidence trigger is not supported by "
                    "observations"
                )
            if (
                follow_up.trigger is FollowUpTrigger.MISSING_DETAIL
                and not set(follow_up.criterion_ids).issubset(
                    missing_detail_criteria
                )
            ):
                raise MultiAgentOutputError(
                    "follow-up missing-detail trigger is not supported by "
                    "observations"
                )
            if len(follow_up.criterion_ids) != len(
                set(follow_up.criterion_ids)
            ):
                raise MultiAgentOutputError(
                    "follow-up contains duplicate criterion ids"
                )
            if not set(follow_up.criterion_ids).issubset(expected_criteria):
                raise MultiAgentOutputError(
                    "follow-up references a criterion outside the source "
                    "question"
                )
            if len(follow_up.requirement_ids) != len(
                set(follow_up.requirement_ids)
            ):
                raise MultiAgentOutputError(
                    "follow-up contains duplicate requirement ids"
                )
            if not set(follow_up.requirement_ids).issubset(known_requirements):
                raise MultiAgentOutputError(
                    "follow-up references an unknown vacancy requirement"
                )
            if len(follow_up.resume_claim_ids) != len(
                set(follow_up.resume_claim_ids)
            ):
                raise MultiAgentOutputError(
                    "follow-up contains duplicate resume claim ids"
                )
            if not set(follow_up.resume_claim_ids).issubset(known_claims):
                raise MultiAgentOutputError(
                    "follow-up references an unknown resume claim"
                )
            normalized_prompt = follow_up.prompt.strip()
            if normalized_prompt == question.prompt.strip():
                raise MultiAgentOutputError(
                    "follow-up must not repeat the source question"
                )
            if normalized_prompt in prompts:
                raise MultiAgentOutputError(
                    "follow-up questions must not repeat each other"
                )
            prompts.add(normalized_prompt)
            has_prior_sentence = re.search(
                r"[.!?]\s+",
                normalized_prompt[:-1],
            )
            if (
                normalized_prompt.count("?") != 1
                or not normalized_prompt.endswith("?")
                or has_prior_sentence
            ):
                raise MultiAgentOutputError(
                    "each follow-up item must be one question sentence"
                )

    @staticmethod
    def _validate_live_coding(
        parsed: AnswerAssessmentOutput,
        question: QuestionSelection,
        requirement_catalog: list[dict[str, str]],
        resume: ResumeRelevanceOutput,
        live_coding_allowed: bool,
    ) -> None:
        challenge = parsed.live_coding
        if challenge is None:
            return
        if not live_coding_allowed:
            raise MultiAgentOutputError(
                "answer assessment cannot create live coding for this question"
            )
        eligible_criteria = {
            observation.criterion_id
            for observation in parsed.observations
            if observation.dimension is Dimension.TECHNICAL
            and observation.label
            in {
                ObservationLabel.WEAK,
                ObservationLabel.INSUFFICIENT_INFORMATION,
            }
        }
        if not set(challenge.criterion_ids).issubset(eligible_criteria):
            raise MultiAgentOutputError(
                "live coding requires an unanswered or weak technical criterion"
            )
        expected_technical_criteria = {
            criterion.criterion_id
            for criterion in question.criteria
            if criterion.dimension is Dimension.TECHNICAL
        }
        if len(challenge.criterion_ids) != len(set(challenge.criterion_ids)):
            raise MultiAgentOutputError(
                "live coding contains duplicate criterion ids"
            )
        if not set(challenge.criterion_ids).issubset(expected_technical_criteria):
            raise MultiAgentOutputError(
                "live coding references a non-technical source criterion"
            )
        known_requirements = {
            item["requirement_id"] for item in requirement_catalog
        }
        if len(challenge.requirement_ids) != len(set(challenge.requirement_ids)):
            raise MultiAgentOutputError(
                "live coding contains duplicate requirement ids"
            )
        if not set(challenge.requirement_ids).issubset(known_requirements):
            raise MultiAgentOutputError(
                "live coding references an unknown vacancy requirement"
            )
        skill_claim_ids = {
            claim.claim_id
            for claim in resume.claims
            if claim.claim_type is ResumeClaimType.SKILL
        }
        if len(challenge.resume_claim_ids) != len(
            set(challenge.resume_claim_ids)
        ):
            raise MultiAgentOutputError(
                "live coding contains duplicate resume claim ids"
            )
        if not set(challenge.resume_claim_ids).issubset(skill_claim_ids):
            raise MultiAgentOutputError(
                "live coding requires an existing resume skill claim"
            )
        linked_claim_requirements = {
            (claim_id, match.requirement_id)
            for match in resume.experience_matches
            for claim_id in match.claim_ids
        }
        if any(
            not any(
                (claim_id, requirement_id) in linked_claim_requirements
                for requirement_id in challenge.requirement_ids
            )
            for claim_id in challenge.resume_claim_ids
        ):
            raise MultiAgentOutputError(
                "live coding skill claim is not linked to its vacancy requirement"
            )
        if challenge.prompt.strip() == question.prompt.strip():
            raise MultiAgentOutputError(
                "live coding must contain a practical task, not repeat the question"
            )

    @staticmethod
    def _validate_integrity_output(
        output: BaseModel,
        resume_evidence_catalog: list[dict[str, str]],
        answer_evidence_catalogs: dict[str, list[dict[str, str]]],
    ) -> None:
        parsed = IntegrityCheckOutput.model_validate(output)
        MultiAgentHarness._reject_sensitive_output(parsed)
        if PROHIBITED_INTEGRITY_DECISION_PATTERN.search(
            parsed.model_dump_json()
        ):
            raise MultiAgentOutputError(
                "integrity agent used prohibited decision language"
            )
        known_resume_ids = {
            item["evidence_id"] for item in resume_evidence_catalog
        }
        known_answer_ids = {
            response_id: {item["evidence_id"] for item in catalog}
            for response_id, catalog in answer_evidence_catalogs.items()
        }
        for observation in parsed.observations:
            if (
                observation.resume_evidence_id is not None
                and observation.resume_evidence_id not in known_resume_ids
            ):
                raise MultiAgentOutputError(
                    "integrity check references an unknown resume evidence id"
                )
            if observation.answer_evidence_id is not None:
                response_ids = known_answer_ids.get(str(observation.response_id))
                if (
                    response_ids is None
                    or observation.answer_evidence_id not in response_ids
                ):
                    raise MultiAgentOutputError(
                        "integrity check references an unknown answer evidence id"
                    )

    @staticmethod
    def _validate_alternative_output(
        output: BaseModel,
        target: Vacancy,
        candidate_evidence: list[dict[str, Any]],
        candidate_manifest: dict[str, str],
        target_manifest: dict[str, str],
        maximum_grade_distance: int,
    ) -> None:
        parsed = AlternativeVacancyMatchOutput.model_validate(output)
        MultiAgentHarness._reject_sensitive_output(parsed)
        if parsed.target_vacancy_id != target.id:
            raise MultiAgentOutputError("alternative agent changed target vacancy")
        known = {item["evidence_reference"] for item in candidate_evidence}
        known_criteria = {item["criterion_id"] for item in candidate_evidence}
        if not set(parsed.evidence_references).issubset(known):
            raise MultiAgentOutputError(
                "alternative match references unknown candidate evidence"
            )
        if not set(parsed.matched_criteria).issubset(known_criteria):
            raise MultiAgentOutputError(
                "alternative match references unknown assessed criteria"
            )
        grades_are_known = (
            parsed.candidate_grade is not SeniorityBand.UNKNOWN
            and parsed.target_grade is not SeniorityBand.UNKNOWN
        )
        if parsed.compatibility_status is AlternativeCompatibility.COMPATIBLE:
            if candidate_manifest != target_manifest:
                raise MultiAgentOutputError(
                    "compatible alternative requires matching competency versions"
                )
            if not parsed.matched_criteria or not parsed.evidence_references:
                raise MultiAgentOutputError(
                    "compatible alternative requires matched criteria and evidence"
                )
            if not grades_are_known:
                raise MultiAgentOutputError(
                    "compatible alternative requires known candidate and target grades"
                )
            distance = abs(
                GRADE_ORDER[parsed.candidate_grade] - GRADE_ORDER[parsed.target_grade]
            )
            if distance > maximum_grade_distance:
                raise MultiAgentOutputError(
                    "alternative match exceeds the pinned grade-distance policy"
                )

    @staticmethod
    def _validate_candidate_feedback_output(
        output: BaseModel,
        profile_artifact: AgentArtifact,
        evidence_catalog: list[dict[str, Any]],
        alternatives: list[dict[str, Any]],
    ) -> None:
        parsed = CandidateFeedbackOutput.model_validate(output)
        MultiAgentHarness._reject_sensitive_output(parsed)
        if PROHIBITED_CANDIDATE_FEEDBACK_PATTERN.search(parsed.model_dump_json()):
            raise MultiAgentOutputError(
                "candidate feedback contains staff-only concepts"
            )
        if parsed.source_profile_artifact_id != profile_artifact.id:
            raise MultiAgentOutputError(
                "candidate feedback changed the source profile identity"
            )
        known_references = {
            item["evidence_reference"] for item in evidence_catalog
        }
        evidence_by_reference = {
            item["evidence_reference"]: item for item in evidence_catalog
        }
        supportive_references = {
            item["evidence_reference"]
            for item in evidence_catalog
            if item.get("source") == "answer_assessment"
            and item.get("label") in {"supported", "strong"}
        }
        points = [
            *parsed.strengths,
            *parsed.growth_areas,
            *parsed.experience_alignment,
        ]
        for point in points:
            if len(point.evidence_references) != len(
                set(point.evidence_references)
            ):
                raise MultiAgentOutputError(
                    "candidate feedback contains duplicate evidence references"
                )
            if not set(point.evidence_references).issubset(known_references):
                raise MultiAgentOutputError(
                    "candidate feedback references unknown evidence"
                )
        for point in parsed.strengths:
            if not set(point.evidence_references) & supportive_references:
                raise MultiAgentOutputError(
                    "candidate strength requires supported answer evidence"
                )
        for point in parsed.growth_areas:
            evidence = [
                evidence_by_reference[reference]
                for reference in point.evidence_references
            ]
            has_answer_evidence = any(
                item.get("source") == "answer_assessment" for item in evidence
            )
            if not has_answer_evidence:
                if not evidence or not all(
                    item.get("source") == "resume_gap" for item in evidence
                ):
                    raise MultiAgentOutputError(
                        "candidate growth area requires answer or resume-gap evidence"
                    )
                growth_text = f"{point.title} {point.detail} {point.action}"
                if not re.search(r"\bрезюм\w*\b", growth_text, re.IGNORECASE):
                    raise MultiAgentOutputError(
                        "resume-only growth area must describe missing resume evidence"
                    )
        alignment_labels = {
            "confirmed": {"supported", "strong"},
            "partially_confirmed": {"neutral", "supported"},
            "not_confirmed": {
                "contradicted",
                "weak",
                "insufficient_information",
            },
            "not_assessed": {"insufficient_information"},
        }
        for point in parsed.experience_alignment:
            evidence = [
                evidence_by_reference[reference]
                for reference in point.evidence_references
            ]
            allowed_labels = alignment_labels[point.status.value]
            has_allowed_answer = any(
                item.get("source") == "answer_assessment"
                and item.get("label") in allowed_labels
                for item in evidence
            )
            has_resume_gap = (
                point.status.value == "not_assessed"
                and any(item.get("source") == "resume_gap" for item in evidence)
            )
            if not has_allowed_answer and not has_resume_gap:
                raise MultiAgentOutputError(
                    "candidate experience status conflicts with its evidence label"
                )
        allowed_by_id = {
            UUID(item["vacancy_id"]): item for item in alternatives
        }
        recommendation = parsed.alternative_vacancy
        if alternatives and recommendation is None:
            raise MultiAgentOutputError(
                "eligible alternative vacancy must be included in candidate feedback"
            )
        if recommendation is not None:
            allowed = allowed_by_id.get(recommendation.vacancy_id)
            if allowed is None:
                raise MultiAgentOutputError(
                    "candidate feedback invented an alternative vacancy"
                )
            if recommendation.title != allowed["title"]:
                raise MultiAgentOutputError(
                    "candidate feedback changed the alternative vacancy title"
                )
            if not set(recommendation.matched_areas).issubset(
                set(allowed["matched_areas"])
            ):
                raise MultiAgentOutputError(
                    "candidate feedback invented an alternative matched area"
                )

    def _build_profile(
        self,
        agent_session: AgentSession,
        resume: ResumeRelevanceOutput,
        plan: QuestionPlanOutput,
        assessments: list[AgentArtifact],
        integrity: IntegrityCheckOutput,
    ) -> CandidateProfilePayload:
        criteria: dict[str, CriterionDefinition] = {}
        for question in plan.questions:
            for criterion in question.criteria:
                existing = criteria.get(criterion.criterion_id)
                if existing is not None and existing != criterion:
                    raise MultiAgentConflictError(
                        "question plan contains inconsistent criterion definitions"
                    )
                criteria[criterion.criterion_id] = criterion
        observations: dict[str, list[tuple[CriterionObservation, UUID]]] = defaultdict(list)
        for artifact in assessments:
            parsed = AnswerAssessmentOutput.model_validate(artifact.payload)
            for item in parsed.observations:
                observations[item.criterion_id].append((item, artifact.id))

        criterion_summaries: list[CriterionSummary] = []
        for criterion_id in sorted(criteria):
            definition = criteria[criterion_id]
            items = observations.get(criterion_id, [])
            values = [item.value for item, _ in items if item.value is not None]
            confidences = [
                item.confidence for item, _ in items if item.value is not None
            ]
            value = sum(values) / len(values) if values else None
            references = sorted(
                {
                    f"{artifact_id}:{criterion_id}:{index}"
                    for item, artifact_id in items
                    for index, evidence in enumerate(item.evidence)
                    if evidence.evidence_id is not None
                }
            )
            criterion_summaries.append(
                CriterionSummary(
                    criterion_id=criterion_id,
                    dimension=definition.dimension,
                    value=value,
                    confidence=(
                        sum(confidences) / len(confidences) if confidences else None
                    ),
                    observation_count=len(items),
                    evidence_references=references,
                )
            )

        by_dimension: dict[Dimension, list[CriterionSummary]] = defaultdict(list)
        for item in criterion_summaries:
            by_dimension[item.dimension].append(item)
        dimension_summaries: list[DimensionSummary] = []
        for dimension in Dimension:
            items = by_dimension.get(dimension, [])
            if not items:
                continue
            assessed = [item.value for item in items if item.value is not None]
            confidences = [
                item.confidence for item in items if item.confidence is not None
            ]
            dimension_summaries.append(
                DimensionSummary(
                    dimension=dimension,
                    value=sum(assessed) / len(assessed) if assessed else None,
                    confidence=(
                        sum(confidences) / len(confidences) if confidences else None
                    ),
                    assessed_criteria=len(assessed),
                    applicable_criteria=len(items),
                    coverage=len(assessed) / len(items),
                )
            )
        assessed_criteria = [
            item for item in criterion_summaries if item.value is not None
        ]
        overall_coverage = (
            len(assessed_criteria) / len(criterion_summaries)
            if criterion_summaries
            else 0.0
        )
        dimension_values = [
            item.value for item in dimension_summaries if item.value is not None
        ]
        overall_readiness = (
            sum(dimension_values) / len(dimension_values)
            if dimension_values
            else None
        )
        dimension_confidences = [
            item.confidence
            for item in dimension_summaries
            if item.confidence is not None
        ]
        overall_confidence = (
            sum(dimension_confidences) / len(dimension_confidences)
            if dimension_confidences
            else None
        )
        review_required = any(
            item.status
            in {
                IntegrityStatus.CONTRADICTION_DETECTED,
                IntegrityStatus.MANUAL_INTEGRITY_REVIEW,
            }
            for item in integrity.observations
        )
        reasons: list[str] = []
        if overall_readiness is None:
            reasons.append("no_assessed_evidence")
        elif overall_readiness < float(
            agent_session.policy_payload["strong_pool_min_readiness"]
        ):
            reasons.append("readiness_below_threshold")
        if overall_coverage < float(
            agent_session.policy_payload["strong_pool_min_coverage"]
        ):
            reasons.append("coverage_below_threshold")
        if review_required:
            reasons.append("integrity_review_required")
        if self._active_restriction(agent_session.invitation_id):
            reasons.append("active_human_restriction")
        compatibility_key = self._compatibility_key(
            vacancy_id=agent_session.vacancy_id,
            vacancy_hash=agent_session.vacancy_hash,
            policy_payload=agent_session.policy_payload,
            criteria_version=agent_session.criteria_version,
            scale_version=agent_session.scale_version,
            aggregation_version=agent_session.aggregation_version,
            policy_version=agent_session.policy_version,
        )
        return CandidateProfilePayload(
            selected_assessment_artifact_ids=[item.id for item in assessments],
            resume_positions=resume.positions,
            resume_claims=resume.claims,
            criterion_summaries=criterion_summaries,
            dimension_summaries=dimension_summaries,
            overall_readiness=overall_readiness,
            overall_confidence=overall_confidence,
            overall_coverage=overall_coverage,
            strong_pool_eligible=not reasons,
            eligibility_reason_codes=reasons,
            integrity_review_required=review_required,
            compatibility_key=compatibility_key,
        )

    def _materialize_deterministic_artifact(
        self,
        agent_session: AgentSession,
        kind: ArtifactKind,
        schema_version: str,
        payload_model: BaseModel,
    ) -> ArtifactView:
        payload = payload_model.model_dump(mode="json")
        content_hash = _canonical_hash(payload)
        existing = self.db.scalar(
            select(AgentArtifact).where(
                AgentArtifact.agent_session_id == agent_session.id,
                AgentArtifact.kind == kind.value,
                AgentArtifact.content_hash == content_hash,
            )
        )
        if existing is not None:
            return self._artifact_view(existing)
        artifact = AgentArtifact(
            agent_session_id=agent_session.id,
            operation_id=None,
            kind=kind.value,
            schema_version=schema_version,
            payload=payload,
            content_hash=content_hash,
            created_at=_now(),
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return self._artifact_view(artifact)

    def _ranking_view(self, snapshot: RankingSnapshot) -> RankingView:
        rows = self.db.execute(
            select(RankingEntry, AgentSession, InterviewInvitation)
            .join(
                AgentSession,
                RankingEntry.agent_session_id == AgentSession.id,
            )
            .join(
                InterviewInvitation,
                AgentSession.invitation_id == InterviewInvitation.id,
            )
            .where(RankingEntry.snapshot_id == snapshot.id)
            .order_by(RankingEntry.rank)
        ).all()
        result = []
        for entry, _agent_session, invitation in rows:
            result.append(
                RankingEntryView(
                    rank=entry.rank,
                    agent_session_id=entry.agent_session_id,
                    candidate_alias=invitation.candidate_alias,
                    overall_value=entry.overall_value,
                    coverage=entry.coverage,
                )
            )
        return RankingView(
            vacancy_id=snapshot.vacancy_id,
            compatibility_key=snapshot.compatibility_key,
            entries=result,
            created_at=snapshot.created_at,
        )

    def _validate_restriction_evidence(
        self, invitation_id: UUID, request: CreateRestrictionRequest
    ) -> None:
        if request.decision_type is RestrictionType.CLEARED:
            return
        agent_session = self.db.scalar(
            select(AgentSession).where(AgentSession.invitation_id == invitation_id)
        )
        known: set[str] = set()
        if agent_session is not None:
            known.update(
                str(item)
                for item in self.db.scalars(
                    select(AgentArtifact.id).where(
                        AgentArtifact.agent_session_id == agent_session.id
                    )
                ).all()
            )
        interview = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation_id
            )
        )
        if interview is not None:
            known.update(
                str(item)
                for item in self.db.scalars(
                    select(CandidateResponse.id).where(
                        CandidateResponse.session_id == interview.id
                    )
                ).all()
            )
        if not set(request.evidence_references).issubset(known):
            raise MultiAgentValidationError(
                "restriction references evidence outside this application"
            )

    def _active_restriction(self, invitation_id: UUID) -> bool:
        latest = self.db.scalar(
            select(RestrictionDecision)
            .where(RestrictionDecision.invitation_id == invitation_id)
            .order_by(
                RestrictionDecision.created_at.desc(),
                RestrictionDecision.id.desc(),
            )
        )
        return self._restriction_is_active(latest)

    @staticmethod
    def _restriction_is_active(
        decision: RestrictionDecision | None,
    ) -> bool:
        if decision is None or decision.decision_type is RestrictionType.CLEARED:
            return False
        if decision.expires_at is not None and _aware(decision.expires_at) <= _now():
            return False
        return True

    def _candidate_evidence(
        self, assessments: list[AgentArtifact], plan_artifact: AgentArtifact
    ) -> list[dict[str, Any]]:
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        criteria = {
            item.criterion_id: item
            for question in plan.questions
            for item in question.criteria
        }
        result: list[dict[str, Any]] = []
        for artifact in assessments:
            assessment = AnswerAssessmentOutput.model_validate(artifact.payload)
            response = self.db.get(CandidateResponse, assessment.response_id)
            if response is None or response.transcript_text is None:
                raise MultiAgentConflictError(
                    "assessment source response is missing"
                )
            code_answer = self.db.scalar(select(CodeAnswer).where(
                CodeAnswer.response_id == response.id
            ))
            evidence_text = (
                f"КОД:\n{code_answer.source_code}\n\n"
                f"УСТНОЕ ОБЪЯСНЕНИЕ:\n{response.transcript_text}"
                if code_answer else response.transcript_text
            )
            excerpts = {
                item["evidence_id"]: item["text"]
                for item in self._evidence_catalog(
                    evidence_text,
                    f"answer:{response.id}",
                )
            }
            for observation in assessment.observations:
                if observation.value is None:
                    continue
                for index, evidence in enumerate(observation.evidence):
                    if evidence.evidence_id is None:
                        continue
                    result.append(
                        {
                            "evidence_reference": (
                                f"{artifact.id}:{observation.criterion_id}:{index}"
                            ),
                            "criterion_id": observation.criterion_id,
                            "criterion_title": criteria[observation.criterion_id].title,
                            "dimension": observation.dimension.value,
                            "value": observation.value,
                            "answer_evidence_id": evidence.evidence_id,
                            "answer_excerpt": excerpts[evidence.evidence_id],
                        }
                    )
        return result

    def _feedback_evidence_catalog(
        self,
        resume_artifact: AgentArtifact,
        plan_artifact: AgentArtifact,
        assessments: list[AgentArtifact],
    ) -> list[dict[str, Any]]:
        """Build the only evidence identifiers a feedback draft may cite."""

        resume = ResumeRelevanceOutput.model_validate(resume_artifact.payload)
        agent_session = self.db.get(AgentSession, resume_artifact.agent_session_id)
        if agent_session is None:
            raise MultiAgentConflictError("resume artifact session is missing")
        resume_excerpts = {
            item["evidence_id"]: item["text"]
            for item in self._resume_evidence_catalog(agent_session)
        }
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        questions = {str(item.question_id): item for item in plan.questions}
        criteria = {
            item.criterion_id: item
            for question in plan.questions
            for item in question.criteria
        }
        catalog: list[dict[str, Any]] = []
        for claim in resume.claims:
            for evidence_id in claim.evidence_ids:
                source_reference = (
                    f"{resume_artifact.id}:resume_claim:{claim.claim_id}:"
                    f"{evidence_id}"
                )
                catalog.append(
                    {
                        "evidence_reference": self._feedback_reference(
                            source_reference
                        ),
                        "source": "resume_claim",
                        "subject": claim.subject,
                        "verification_status": claim.verification_status.value,
                        "source_evidence_id": evidence_id,
                        "excerpt": resume_excerpts[evidence_id],
                    }
                )
        for index, gap in enumerate(resume.gaps):
            source_reference = f"{resume_artifact.id}:resume_gap:{index}"
            catalog.append(
                {
                    "evidence_reference": self._feedback_reference(
                        source_reference
                    ),
                    "source": "resume_gap",
                    "subject": gap,
                    "verification_status": "insufficient_information",
                    "excerpt": None,
                }
            )
        for artifact in assessments:
            assessment = AnswerAssessmentOutput.model_validate(artifact.payload)
            response = self.db.get(CandidateResponse, assessment.response_id)
            if response is None or response.transcript_text is None:
                raise MultiAgentConflictError(
                    "assessment source response is missing"
                )
            code_answer = self.db.scalar(select(CodeAnswer).where(
                CodeAnswer.response_id == response.id
            ))
            evidence_text = (
                f"КОД:\n{code_answer.source_code}\n\n"
                f"УСТНОЕ ОБЪЯСНЕНИЕ:\n{response.transcript_text}"
                if code_answer else response.transcript_text
            )
            answer_excerpts = {
                item["evidence_id"]: item["text"]
                for item in self._evidence_catalog(
                    evidence_text,
                    f"answer:{response.id}",
                )
            }
            question = questions.get(str(assessment.question_id))
            for observation in assessment.observations:
                definition = criteria[observation.criterion_id]
                for index, evidence in enumerate(observation.evidence):
                    source_reference = (
                        f"{artifact.id}:{observation.criterion_id}:{index}"
                    )
                    catalog.append(
                        {
                            "evidence_reference": self._feedback_reference(
                                source_reference
                            ),
                            "source": "answer_assessment",
                            "response_id": str(assessment.response_id),
                            "question_id": str(assessment.question_id),
                            "question": question.prompt if question else None,
                            "criterion_id": observation.criterion_id,
                            "criterion_title": definition.title,
                            "dimension": observation.dimension.value,
                            "label": observation.label.value,
                            "explanation": observation.explanation,
                            "source_evidence_id": evidence.evidence_id,
                            "excerpt": (
                                answer_excerpts[evidence.evidence_id]
                                if evidence.evidence_id is not None
                                else None
                            ),
                        }
                    )
        return catalog

    @staticmethod
    def _feedback_reference(source_reference: str) -> str:
        """Expose a short stable alias instead of an internal artifact locator."""

        digest = hashlib.sha256(source_reference.encode("utf-8")).hexdigest()
        return f"E-{digest[:12].upper()}"

    def _feedback_alternatives(
        self,
        agent_session: AgentSession,
        profile: CandidateProfilePayload,
    ) -> list[dict[str, Any]]:
        """Return only currently eligible active alternatives, without pool metadata."""

        if (
            not profile.strong_pool_eligible
            or self._active_restriction(agent_session.invitation_id)
        ):
            return []
        artifacts = self.db.scalars(
            select(AgentArtifact)
            .where(
                AgentArtifact.agent_session_id == agent_session.id,
                AgentArtifact.kind == ArtifactKind.ALTERNATIVE_VACANCY_MATCH.value,
            )
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
        ).all()
        plan_artifact = self._latest_artifact(
            agent_session.id, ArtifactKind.QUESTION_PLAN, required=True
        )
        plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
        criterion_titles = {
            criterion.criterion_id: criterion.title
            for question in plan.questions
            for criterion in question.criteria
        }
        latest_by_target: dict[UUID, tuple[AgentArtifact, AlternativeVacancyMatchOutput]] = {}
        for artifact in artifacts:
            parsed = AlternativeVacancyMatchOutput.model_validate(artifact.payload)
            latest_by_target[parsed.target_vacancy_id] = (artifact, parsed)
        alternatives: list[dict[str, Any]] = []
        for target_id, (artifact, parsed) in latest_by_target.items():
            target = self.db.get(Vacancy, target_id)
            if (
                target is None
                or target.status is not VacancyStatus.ACTIVE
                or parsed.compatibility_status
                is not AlternativeCompatibility.COMPATIBLE
                or parsed.fit_value is None
                or parsed.fit_value
                < float(agent_session.policy_payload["alternative_min_fit"])
            ):
                continue
            alternatives.append(
                {
                    "vacancy_id": str(target.id),
                    "title": target.title,
                    "matched_criteria": parsed.matched_criteria,
                    "matched_terms": parsed.matched_terms,
                    "matched_areas": sorted(
                        set(parsed.matched_terms)
                        | {
                            criterion_titles[criterion_id]
                            for criterion_id in parsed.matched_criteria
                            if criterion_id in criterion_titles
                        }
                    ),
                    "gaps": parsed.gaps,
                    "explanation": parsed.explanation,
                    "_fit_value": parsed.fit_value,
                }
            )
        alternatives.sort(
            key=lambda item: (-float(item["_fit_value"]), item["vacancy_id"])
        )
        for item in alternatives:
            item.pop("_fit_value")
        return alternatives

    @staticmethod
    def _candidate_score(profile: CandidateProfilePayload) -> dict[str, Any]:
        value = (
            None
            if profile.overall_readiness is None
            else round((profile.overall_readiness + 1) * 5, 2)
        )
        return {
            "value": value,
            "maximum": 10,
            "scale_version": "signed_readiness_to_10_v1",
            "evidence_coverage": profile.overall_coverage,
            "explanation": (
                "Сводный результат только этого интервью; отсутствие подтверждений "
                "учитывается в полноте оценки и не считается отсутствием навыка."
            ),
        }

    def _feedback_evidence_excerpts(
        self, agent_session_id: UUID
    ) -> dict[str, str | None]:
        """Resolve immutable feedback references from their original artifacts."""

        artifacts = self.db.scalars(
            select(AgentArtifact)
            .where(
                AgentArtifact.agent_session_id == agent_session_id,
                AgentArtifact.kind.in_(
                    [
                        ArtifactKind.RESUME_RELEVANCE.value,
                        ArtifactKind.ANSWER_ASSESSMENT.value,
                    ]
                ),
            )
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
        ).all()
        excerpts: dict[str, str | None] = {}
        for artifact in artifacts:
            if artifact.kind == ArtifactKind.RESUME_RELEVANCE.value:
                resume = ResumeRelevanceOutput.model_validate(artifact.payload)
                agent_session = self.db.get(AgentSession, artifact.agent_session_id)
                if agent_session is None:
                    raise MultiAgentConflictError(
                        "resume artifact session is missing"
                    )
                resume_excerpts = {
                    item["evidence_id"]: item["text"]
                    for item in self._resume_evidence_catalog(agent_session)
                }
                for claim in resume.claims:
                    for evidence_id in claim.evidence_ids:
                        source_reference = (
                            f"{artifact.id}:resume_claim:{claim.claim_id}:"
                            f"{evidence_id}"
                        )
                        reference = self._feedback_reference(source_reference)
                        excerpts[reference] = resume_excerpts[evidence_id]
                for index, _gap in enumerate(resume.gaps):
                    source_reference = f"{artifact.id}:resume_gap:{index}"
                    reference = self._feedback_reference(source_reference)
                    excerpts[reference] = None
                continue
            assessment = AnswerAssessmentOutput.model_validate(artifact.payload)
            response = self.db.get(CandidateResponse, assessment.response_id)
            if response is None or response.transcript_text is None:
                raise MultiAgentConflictError(
                    "assessment source response is missing"
                )
            answer_excerpts = {
                item["evidence_id"]: item["text"]
                for item in self._evidence_catalog(
                    response.transcript_text,
                    f"answer:{response.id}",
                )
            }
            for observation in assessment.observations:
                for index, evidence in enumerate(observation.evidence):
                    source_reference = (
                        f"{artifact.id}:{observation.criterion_id}:{index}"
                    )
                    reference = self._feedback_reference(source_reference)
                    excerpts[reference] = (
                        answer_excerpts[evidence.evidence_id]
                        if evidence.evidence_id is not None
                        else None
                    )
        return excerpts

    def _candidate_feedback_content(
        self, release: CandidateFeedbackRelease
    ) -> CandidateFeedbackContentView:
        artifact = self.db.get(AgentArtifact, release.feedback_artifact_id)
        if artifact is None:
            raise MultiAgentConflictError("published feedback artifact is missing")
        output = CandidateFeedbackOutput.model_validate(artifact.payload)
        profile_artifact = self.db.get(
            AgentArtifact, output.source_profile_artifact_id
        )
        if profile_artifact is None:
            raise MultiAgentConflictError("feedback source profile is missing")
        profile = CandidateProfilePayload.model_validate(profile_artifact.payload)
        evidence_by_reference = self._feedback_evidence_excerpts(
            release.agent_session_id
        )

        def evidence(references: list[str]) -> list[CandidateFeedbackEvidenceView]:
            return [
                CandidateFeedbackEvidenceView(
                    excerpt=evidence_by_reference[reference]
                )
                for reference in references
                if reference in evidence_by_reference
                and evidence_by_reference[reference] is not None
            ]

        published_at = release.published_at
        if published_at is None:
            raise MultiAgentConflictError("published feedback has no timestamp")
        return CandidateFeedbackContentView(
            score=CandidateFeedbackScoreView(**self._candidate_score(profile)),
            headline=output.headline,
            summary=output.summary,
            strengths=[
                CandidateFeedbackPointView(
                    title=item.title,
                    detail=item.detail,
                    evidence=evidence(item.evidence_references),
                )
                for item in output.strengths
            ],
            growth_areas=[
                CandidateGrowthAreaView(
                    title=item.title,
                    detail=item.detail,
                    action=item.action,
                    evidence=evidence(item.evidence_references),
                )
                for item in output.growth_areas
            ],
            experience_alignment=[
                CandidateExperienceAlignmentView(
                    title=item.title,
                    detail=item.detail,
                    status=item.status,
                    evidence=evidence(item.evidence_references),
                )
                for item in output.experience_alignment
            ],
            alternative_vacancy=output.alternative_vacancy,
            next_steps=output.next_steps,
            limitations=output.limitations,
            published_at=published_at,
        )

    def _integrity_answer_context(
        self, agent_session: AgentSession, assessments: list[AgentArtifact]
    ) -> list[dict[str, Any]]:
        response_ids = {
            AnswerAssessmentOutput.model_validate(item.payload).response_id
            for item in assessments
        }
        responses = self.db.scalars(
            select(CandidateResponse)
            .where(CandidateResponse.id.in_(response_ids))
            .order_by(CandidateResponse.created_at, CandidateResponse.id)
        ).all()
        return [
            {
                "response_id": str(item.id),
                "question_id": str(item.question_id),
                "answer_text": item.transcript_text,
            }
            for item in responses
        ]

    def _baseline_questions(
        self, agent_session: AgentSession, vacancy: Vacancy
    ) -> list[QuestionSelection]:
        criteria = [
            (
                "technical_depth",
                "Техническая глубина и применение знаний",
                Dimension.TECHNICAL,
            ),
            (
                "collaboration",
                "Работа в команде и коммуникация",
                Dimension.SOFT_SKILLS,
            ),
            (
                "ownership",
                "Ответственность за результат",
                Dimension.CORPORATE_COMPETENCIES,
            ),
            (
                "primary_vacancy_fit",
                f"Соответствие задачам вакансии {vacancy.title}",
                Dimension.VACANCY_FIT,
            ),
        ]
        criterion_models = [
            CriterionDefinition(
                criterion_id=criterion_id,
                title=title,
                dimension=dimension,
                weight=1.0,
            )
            for criterion_id, title, dimension in criteria
        ]
        invitation = self.db.get(InterviewInvitation, agent_session.invitation_id)
        if invitation.question_config:
            configured = invitation_input(
                invitation.question_config, invitation.follow_up_after_all_answers
            )
            questions_to_ask = [
                (question.id, question.text, question.kind)
                for block in configured.blocks
                for question in block.questions
            ]
        else:
            legacy_prompts = [
                ("technical_depth", "Расскажите о сложной технической задаче, которую вы решили лично: подход, компромиссы и результат."),
                ("collaboration", "Опишите рабочее разногласие в команде и как вы помогли прийти к решению."),
                ("ownership", "Приведите пример, когда вы взяли ответственность за результат за пределами своей непосредственной задачи."),
                ("primary_vacancy_fit", f"Какие задачи вакансии «{vacancy.title}» наиболее близки вашему опыту и почему?"),
            ]
            questions_to_ask = [
                (
                    uuid5(NAMESPACE_URL, f"{agent_session.vacancy_id}:{agent_session.criteria_version}:{criterion_id}"),
                    prompt,
                    ConfigQuestionKind.SPOKEN,
                )
                for criterion_id, prompt in legacy_prompts
            ]
        questions: list[QuestionSelection] = []
        for question_id, prompt, configured_kind in questions_to_ask:
            questions.append(
                QuestionSelection(
                    question_id=question_id,
                    prompt=prompt,
                    kind=(
                        QuestionKind.LIVE_CODING
                        if configured_kind is ConfigQuestionKind.CODING
                        else QuestionKind.BASELINE
                    ),
                    criteria=criterion_models,
                    source_claim_ids=[],
                    source_manager_field_keys=[],
                    selection_reason=(
                        "Обязательный сопоставимый вопрос утверждённой версии; каждый "
                        "блок оценивается независимо и без evidence получает null."
                    ),
                )
            )
        return questions

    def _follow_up_enabled(
        self, interview: InterviewSession, question_id: UUID
    ) -> bool:
        invitation = self.db.get(InterviewInvitation, interview.invitation_id)
        if not invitation.question_config:
            return True
        configured = invitation_input(
            invitation.question_config, invitation.follow_up_after_all_answers
        )
        return configured.follow_up_after_all_answers or any(
            item.id == question_id and item.follow_up_after_answer
            for item in configured.questions
        )

    def _approved_brief_payload(
        self, agent_session: AgentSession
    ) -> dict[str, Any] | None:
        if agent_session.manager_brief_id is None:
            return None
        brief = self.db.get(ManagerBriefDraft, agent_session.manager_brief_id)
        if brief is None or brief.status is not ManagerBriefStatus.APPROVED:
            raise MultiAgentConflictError("pinned manager brief is no longer approved")
        fields = [
            {
                "field_key": item["field_key"],
                "value": item["value"],
                "source_fragment_ids": item.get("source_fragment_ids", []),
            }
            for item in brief.fields_payload
            if item.get("confirmation_status") == ConfirmationStatus.CONFIRMED.value
        ]
        return {
            "id": str(brief.id),
            "version": brief.version,
            "content_hash": brief.content_hash,
            "confirmed_fields": fields,
        }

    def _approved_brief_for_vacancy(self, vacancy_id: UUID) -> dict[str, Any] | None:
        brief = self.db.scalar(
            select(ManagerBriefDraft)
            .where(
                ManagerBriefDraft.vacancy_id == vacancy_id,
                ManagerBriefDraft.status == ManagerBriefStatus.APPROVED,
            )
            .order_by(ManagerBriefDraft.version.desc(), ManagerBriefDraft.id.desc())
        )
        if brief is None:
            return None
        fields = [
            {
                "field_key": item["field_key"],
                "value": item["value"],
                "source_fragment_ids": item.get("source_fragment_ids", []),
            }
            for item in brief.fields_payload
            if item.get("confirmation_status") == ConfirmationStatus.CONFIRMED.value
        ]
        return {
            "id": str(brief.id),
            "version": brief.version,
            "content_hash": brief.content_hash,
            "confirmed_fields": fields,
        }

    @staticmethod
    def _compatibility_key(
        *,
        vacancy_id: UUID,
        vacancy_hash: str,
        policy_payload: dict[str, Any],
        criteria_version: str = CRITERIA_VERSION,
        scale_version: str = SCALE_VERSION,
        aggregation_version: str = AGGREGATION_VERSION,
        policy_version: str = POLICY_VERSION,
    ) -> str:
        return _canonical_hash(
            {
                "vacancy_id": str(vacancy_id),
                "vacancy_hash": vacancy_hash,
                "criteria_version": criteria_version,
                "scale_version": scale_version,
                "aggregation_version": aggregation_version,
                "policy_version": policy_version,
                "policy_payload": policy_payload,
            }
        )

    @staticmethod
    def _agent_policy() -> dict[str, bool]:
        return {
            "resume_is_claim_source_only": True,
            "interview_scores_require_answer_evidence": True,
            "missing_evidence_is_not_zero": True,
            "automatic_hiring_decision_forbidden": True,
            "automatic_restriction_forbidden": True,
            "sensitive_trait_scoring_forbidden": True,
        }

    def _scoped_application(
        self, vacancy_id: UUID, invitation_id: UUID
    ) -> tuple[Vacancy, InterviewInvitation]:
        vacancy = self.db.get(Vacancy, vacancy_id)
        invitation = self.db.get(InterviewInvitation, invitation_id)
        if (
            vacancy is None
            or invitation is None
            or invitation.vacancy_id != vacancy_id
        ):
            raise MultiAgentNotFoundError("vacancy application was not found")
        return vacancy, invitation

    def _session_model(
        self, vacancy_id: UUID, invitation_id: UUID
    ) -> AgentSession:
        model = self.db.scalar(
            select(AgentSession).where(
                AgentSession.vacancy_id == vacancy_id,
                AgentSession.invitation_id == invitation_id,
            )
        )
        if model is None:
            raise MultiAgentNotFoundError("agent session was not found")
        return model

    def _latest_artifact(
        self,
        agent_session_id: UUID,
        kind: ArtifactKind,
        *,
        required: bool,
    ) -> AgentArtifact | None:
        artifact = self.db.scalar(
            select(AgentArtifact)
            .where(
                AgentArtifact.agent_session_id == agent_session_id,
                AgentArtifact.kind == kind.value,
            )
            .order_by(AgentArtifact.created_at.desc(), AgentArtifact.id.desc())
        )
        if artifact is None and required:
            raise MultiAgentConflictError(f"required {kind.value} artifact is missing")
        return artifact

    def _assessment_artifacts(self, agent_session_id: UUID) -> list[AgentArtifact]:
        artifacts = self.db.scalars(
            select(AgentArtifact)
            .where(
                AgentArtifact.agent_session_id == agent_session_id,
                AgentArtifact.kind == ArtifactKind.ANSWER_ASSESSMENT.value,
            )
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
        ).all()
        latest_by_response: dict[str, AgentArtifact] = {}
        for artifact in artifacts:
            response_id = str(artifact.payload["response_id"])
            latest_by_response[response_id] = artifact
        return sorted(latest_by_response.values(), key=lambda item: str(item.id))

    def _follow_up_count(self, agent_session_id: UUID) -> int:
        return sum(
            len(
                AnswerAssessmentOutput.model_validate(artifact.payload).follow_up
                or []
            )
            for artifact in self._assessment_artifacts(agent_session_id)
        )

    def _live_coding_count(self, agent_session_id: UUID) -> int:
        return sum(
            1
            for artifact in self._assessment_artifacts(agent_session_id)
            if AnswerAssessmentOutput.model_validate(artifact.payload).live_coding
            is not None
        )

    def _session_questions(
        self,
        agent_session: AgentSession,
        plan: QuestionPlanOutput,
    ) -> list[QuestionSelection]:
        """Combine the pinned plan with validated conditional questions."""

        criteria = {
            criterion.criterion_id: criterion
            for question in plan.questions
            for criterion in question.criteria
        }
        questions = list(plan.questions)
        follow_up_artifacts = sorted(
            self._assessment_artifacts(agent_session.id),
            key=lambda item: (item.created_at, str(item.id)),
        )
        limit = min(
            FOLLOW_UP_MAX_QUESTIONS,
            int(
                agent_session.policy_payload.get(
                    "follow_up_max_per_session",
                    FOLLOW_UP_MAX_QUESTIONS,
                )
            ),
        )
        appended = 0
        live_coding_appended = False
        for artifact in follow_up_artifacts:
            assessment = AnswerAssessmentOutput.model_validate(artifact.payload)
            if appended < limit:
                for index, follow_up in enumerate(assessment.follow_up or []):
                    selected_criteria = [
                        criteria[criterion_id]
                        for criterion_id in follow_up.criterion_ids
                        if criterion_id in criteria
                    ]
                    if not selected_criteria:
                        continue
                    questions.append(
                        QuestionSelection(
                            question_id=uuid5(
                                NAMESPACE_URL,
                                (
                                    f"{agent_session.id}:follow-up:"
                                    f"{artifact.id}:{index}"
                                ),
                            ),
                            prompt=follow_up.prompt,
                            kind=QuestionKind.FOLLOW_UP,
                            criteria=selected_criteria,
                            source_claim_ids=follow_up.resume_claim_ids,
                            source_manager_field_keys=[],
                            selection_reason=follow_up.reason,
                        )
                    )
                    appended += 1
                    if appended >= limit:
                        break
            live_coding = assessment.live_coding
            if live_coding is None or live_coding_appended:
                continue
            selected_criteria = [
                criteria[criterion_id]
                for criterion_id in live_coding.criterion_ids
                if criterion_id in criteria
            ]
            if not selected_criteria:
                continue
            questions.append(
                QuestionSelection(
                    question_id=uuid5(
                        NAMESPACE_URL,
                        f"{agent_session.id}:live-coding:{artifact.id}",
                    ),
                    prompt=live_coding.prompt,
                    kind=QuestionKind.LIVE_CODING,
                    criteria=selected_criteria,
                    source_claim_ids=live_coding.resume_claim_ids,
                    source_manager_field_keys=[],
                    selection_reason=live_coding.reason,
                )
            )
            live_coding_appended = True
        return questions

    def _pending_conditional_questions(
        self,
        agent_session: AgentSession,
        plan: QuestionPlanOutput,
    ) -> list[QuestionSelection]:
        assessments = self._assessment_artifacts(agent_session.id)
        assessed_question_ids = {
            AnswerAssessmentOutput.model_validate(artifact.payload).question_id
            for artifact in assessments
        }
        return [
            question
            for question in self._session_questions(agent_session, plan)
            if question.kind in {QuestionKind.FOLLOW_UP, QuestionKind.LIVE_CODING}
            and question.question_id not in assessed_question_ids
        ]

    def _session_view(self, model: AgentSession) -> AgentSessionView:
        artifacts = self.db.scalars(
            select(AgentArtifact)
            .where(AgentArtifact.agent_session_id == model.id)
            .order_by(AgentArtifact.created_at, AgentArtifact.id)
        ).all()
        return AgentSessionView(
            id=model.id,
            invitation_id=model.invitation_id,
            vacancy_id=model.vacancy_id,
            interview_session_id=model.interview_session_id,
            input_hash=model.input_hash,
            status=model.status,
            versions=SessionVersions(
                resume_id=model.resume_id,
                resume_version=model.resume_version,
                resume_hash=model.resume_hash,
                manager_brief_id=model.manager_brief_id,
                manager_brief_version=model.manager_brief_version,
                manager_brief_hash=model.manager_brief_hash,
                vacancy_hash=model.vacancy_hash,
                criteria_version=model.criteria_version,
                scale_version=model.scale_version,
                aggregation_version=model.aggregation_version,
                policy_version=model.policy_version,
            ),
            artifacts=[self._artifact_view(item) for item in artifacts],
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _artifact_view(model: AgentArtifact) -> ArtifactView:
        return ArtifactView(
            id=model.id,
            kind=ArtifactKind(model.kind),
            schema_version=model.schema_version,
            content_hash=model.content_hash,
            payload=model.payload,
            created_at=model.created_at,
        )

    @staticmethod
    def _restriction_view(model: RestrictionDecision) -> RestrictionDecisionView:
        return RestrictionDecisionView(
            id=model.id,
            invitation_id=model.invitation_id,
            decision_type=model.decision_type,
            reason=model.reason,
            evidence_references=model.evidence_references,
            created_by=model.created_by,
            created_at=model.created_at,
            expires_at=model.expires_at,
            supersedes_id=model.supersedes_id,
        )

    def _feedback_release_view(
        self, model: CandidateFeedbackRelease
    ) -> CandidateFeedbackReleaseView:
        artifact = self.db.get(AgentArtifact, model.feedback_artifact_id)
        if artifact is None:
            raise MultiAgentConflictError("candidate feedback artifact is missing")
        return CandidateFeedbackReleaseView(
            id=model.id,
            invitation_id=model.invitation_id,
            agent_session_id=model.agent_session_id,
            status=model.status,
            artifact=self._artifact_view(artifact),
            created_by=model.created_by,
            created_at=model.created_at,
            published_by=model.published_by,
            published_at=model.published_at,
        )

    def _fail_run(
        self,
        operation: AgentOperation,
        run: AgentRun,
        status: AgentRunStatus,
        failure_code: str,
        *,
        output_payload: dict[str, Any] | None = None,
    ) -> None:
        current_run = self.db.get(AgentRun, run.id)
        current_operation = self.db.get(AgentOperation, operation.id)
        current_run.status = status
        current_run.failure_code = failure_code
        current_run.output_payload = output_payload
        if output_payload is not None:
            current_run.output_hash = _canonical_hash(output_payload)
        current_run.completed_at = _now()
        current_operation.status = AgentOperationStatus.FAILED
        current_operation.updated_at = _now()
        self.db.commit()

    @staticmethod
    def _stage_key(base_key: str, stage: str) -> str:
        return _canonical_hash({"base_key": base_key, "stage": stage})

    @staticmethod
    def _reject_sensitive_output(output: BaseModel) -> None:
        if PROHIBITED_TRAIT_PATTERN.search(output.model_dump_json()):
            raise MultiAgentOutputError(
                "agent output contains a prohibited sensitive-trait signal"
            )
