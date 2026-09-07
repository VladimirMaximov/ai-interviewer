"""Automatic post-transcription assessment and report finalization."""

import logging
from uuid import UUID

from sqlalchemy import select

from app.database import multi_agent_harness_factory
from app.domain.multi_agent import MultiAgentConflictError
from app.models.interview import (
    CandidateResponse,
    InterviewInvitation,
    InterviewSession,
    RuntimeEvaluationJob,
    RuntimeEvaluationStatus,
    TranscriptionStatus,
)


logger = logging.getLogger(__name__)


def finalize_completed_interview(response_id: UUID) -> None:
    """Finalize once every submitted answer has STT and an assessment artifact."""

    harness = multi_agent_harness_factory()
    try:
        response = harness.db.get(CandidateResponse, response_id)
        interview = (
            harness.db.get(InterviewSession, response.session_id) if response else None
        )
        if interview is None or interview.submitted_at is None:
            return
        responses = list(
            harness.db.scalars(
                select(CandidateResponse).where(
                    CandidateResponse.session_id == interview.id
                )
            )
        )
        if not responses or any(
            item.transcription_status is not TranscriptionStatus.COMPLETED
            for item in responses
        ):
            return
        jobs = list(
            harness.db.scalars(
                select(RuntimeEvaluationJob).where(
                    RuntimeEvaluationJob.response_id.in_(
                        [item.id for item in responses]
                    )
                )
            )
        )
        if len(jobs) != len(responses) or any(
            item.status is not RuntimeEvaluationStatus.COMPLETED for item in jobs
        ):
            return
        invitation = harness.db.get(InterviewInvitation, interview.invitation_id)
        if invitation is None:
            return
        harness.finalize(
            vacancy_id=invitation.vacancy_id,
            invitation_id=invitation.id,
            idempotency_key=f"runtime-final-{invitation.id}",
        )
        harness.generate_candidate_feedback(
            vacancy_id=invitation.vacancy_id,
            invitation_id=invitation.id,
            actor_id="interview-runtime",
            idempotency_key=f"runtime-summary-{invitation.id}",
        )
    except MultiAgentConflictError:
        logger.info("Interview assessment is waiting for conditional answers")
    except Exception:
        logger.exception("Automatic interview finalization failed")
    finally:
        harness.close()
