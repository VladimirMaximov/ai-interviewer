"""Internal boundary for an eventual clarification agent.

No model is called here. A future agent supplies validated text only after a
completed transcript is available; candidate requests can only read ready items.
"""

from uuid import UUID

from app.models.interview import CandidateResponse, InterviewFollowUpQuestion, InterviewSession
from app.services.candidate_workflow import SqlCandidateWorkflow


def enqueue_clarification(workflow: SqlCandidateWorkflow, response_id: UUID, text: str) -> InterviewFollowUpQuestion:
    """Queue one traceable optional clarification for a completed response."""
    response = workflow.db.get(CandidateResponse, response_id)
    if not response or not response.transcript_text:
        raise ValueError("a completed transcript is required for a follow-up")
    return workflow.queue_follow_up(
        response.session_id,
        text,
        source_response_id=response.id,
        transcript_snapshot=response.transcript_text,
    )


def enqueue_final_clarification(workflow: SqlCandidateWorkflow, session_id: UUID, text: str) -> InterviewFollowUpQuestion:
    """Queue one optional whole-interview clarification if the input permits it."""
    if not workflow.db.get(InterviewSession, session_id):
        raise ValueError("session is missing")
    return workflow.queue_follow_up(session_id, text)
