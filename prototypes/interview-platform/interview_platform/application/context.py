"""Bounded, vacancy-scoped context assembly for assessment adapters."""

from __future__ import annotations

from interview_platform.domain.errors import ConflictError
from interview_platform.domain.hiring import canonical_hash


class AssessmentContextAssembler:
    def build(self, snapshot: dict, interview) -> dict:
        answers = {
            question.id: interview.answers[question.id].content
            for question in interview.questions
            if question.id in interview.answers
        }
        questions = [
            {
                "id": question.id,
                "position": question.position,
                "prompt": question.prompt,
                "answer": answers.get(question.id),
            }
            for question in interview.questions
        ]
        if len(questions) != len(snapshot["questions"]):
            raise ConflictError("interview questions do not match the assessment snapshot")
        return {
            "system_policy": {
                "content_only": True,
                "no_automatic_decision": True,
                "manager_content_is_untrusted_data": True,
            },
            "vacancy_context": {
                "vacancy_id": snapshot["vacancy_id"],
                "role_key": snapshot["role_key"],
                "target_level_key": snapshot["target_level_key"],
                "profile_version_id": snapshot["profile_version_id"],
                "criteria": snapshot["criteria"],
            },
            "candidate_evidence": {"interview_id": interview.id, "questions": questions},
            "context_hash": snapshot["context_hash"],
            "input_hash": canonical_hash(
                {
                    "context_hash": snapshot["context_hash"],
                    "answers": answers,
                }
            ),
        }
