"""Internal boundary for an eventual clarification agent.

No model is called here. A future agent supplies validated text only after a
completed transcript is available; candidate requests can only read ready items.
"""

from uuid import UUID

from app.models.interview import CandidateResponse, InterviewFollowUpQuestion
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
