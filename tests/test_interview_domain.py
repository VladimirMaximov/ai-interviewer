from __future__ import annotations

import unittest
from datetime import UTC, datetime

from interview_platform.domain.errors import ConflictError, ValidationError
from interview_platform.domain.models import (
    Evidence,
    EvidenceKind,
    Feedback,
    Interview,
    InterviewStatus,
    ManagerDecision,
    PublicationStatus,
    Question,
)


NOW = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


def make_interview() -> Interview:
    question = Question("q1", "i1", "Explain a trade-off", 1, True)
    return Interview(
        id="i1",
        candidate_alias="synthetic-candidate",
        position_title="Python Developer",
        invitation_token_digest="d" * 64,
        questions=(question,),
        status=InterviewStatus.INVITED,
        evidence_type="synthetic",
        consent_given_at=None,
        started_at=None,
        submitted_at=None,
        reviewed_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


class InterviewDomainTests(unittest.TestCase):
    def test_start_requires_consent_and_is_idempotent_while_in_progress(self) -> None:
        interview = make_interview()
        with self.assertRaises(ValidationError):
            interview.start(consent=False, now=NOW)

        interview.start(consent=True, now=NOW)
        interview.start(consent=True, now=NOW)

        self.assertEqual(InterviewStatus.IN_PROGRESS, interview.status)
        self.assertEqual(NOW, interview.consent_given_at)

    def test_complete_lists_missing_required_questions(self) -> None:
        interview = make_interview()
        interview.start(consent=True, now=NOW)

        with self.assertRaises(ConflictError) as context:
            interview.complete(now=NOW)

        self.assertEqual(["q1"], context.exception.details["missing_question_ids"])

    def test_answers_are_locked_after_submission(self) -> None:
        interview = make_interview()
        interview.start(consent=True, now=NOW)
        interview.save_answer(
            question_id="q1",
            capture_kind="text_stub",
            content="I chose consistency because the workload was write-heavy.",
            media_reference=None,
            now=NOW,
        )
        interview.complete(now=NOW)

        with self.assertRaises(ConflictError):
            interview.save_answer(
                question_id="q1",
                capture_kind="text_stub",
                content="changed",
                media_reference=None,
                now=NOW,
            )

    def test_feedback_excerpt_must_be_present_in_answer(self) -> None:
        interview = make_interview()
        interview.start(consent=True, now=NOW)
        interview.save_answer(
            question_id="q1",
            capture_kind="text_stub",
            content="I compared latency and consistency before choosing.",
            media_reference=None,
            now=NOW,
        )
        interview.complete(now=NOW)
        feedback = Feedback(
            id="f1",
            interview_id="i1",
            candidate_summary="Clear architecture reasoning.",
            strengths=("Explains trade-offs",),
            risks=(),
            next_steps="Discuss the production case.",
            internal_notes="Human-authored.",
            ai_recommendation=None,
            recruiter_decision=None,
            manager_decision=ManagerDecision.ADVANCE,
            publication_status=PublicationStatus.PUBLISHED,
            evidence=(
                Evidence(
                    id="e1",
                    feedback_id="f1",
                    kind=EvidenceKind.ANSWER_EXCERPT,
                    question_id="q1",
                    excerpt="not in the answer",
                    note="Supposed evidence",
                ),
            ),
            version=1,
            published_at=NOW,
            updated_at=NOW,
        )

        with self.assertRaises(ValidationError):
            interview.set_feedback(feedback, now=NOW)

    def test_poc_rejects_non_synthetic_data_and_ai_decisions(self) -> None:
        interview = make_interview()
        interview.evidence_type = "customer"
        with self.assertRaises(ValidationError):
            interview.__post_init__()

        with self.assertRaises(ValidationError):
            Feedback(
                id="f1",
                interview_id="i1",
                candidate_summary="Summary",
                strengths=(),
                risks=(),
                next_steps="Next",
                internal_notes="",
                ai_recommendation="reject",
                recruiter_decision=None,
                manager_decision=ManagerDecision.HOLD,
                publication_status=PublicationStatus.DRAFT,
                evidence=(
                    Evidence(
                        id="e1",
                        feedback_id="f1",
                        kind=EvidenceKind.INSUFFICIENT_INFORMATION,
                        question_id="q1",
                        excerpt=None,
                        note="No answer",
                    ),
                ),
                version=1,
                published_at=None,
                updated_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
