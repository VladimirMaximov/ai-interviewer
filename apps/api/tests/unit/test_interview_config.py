import unittest

from pydantic import ValidationError

from app.interview_config import InterviewInput, QuestionKind


class InterviewInputTests(unittest.TestCase):
    def test_accepts_per_question_and_final_follow_up_flags(self) -> None:
        interview_input = InterviewInput.model_validate({
            "questions": [
                {"id": "11111111-1111-4111-8111-111111111111", "text": "Опыт", "follow_up_after_answer": 0},
                {"id": "22222222-2222-4222-8222-222222222222", "text": "Проект", "follow_up_after_answer": 1},
            ],
            "follow_up_after_all_answers": 1,
        })

        self.assertFalse(interview_input.questions[0].follow_up_after_answer)
        self.assertTrue(interview_input.questions[1].follow_up_after_answer)
        self.assertTrue(interview_input.follow_up_after_all_answers)

    def test_rejects_duplicate_question_ids(self) -> None:
        with self.assertRaises(ValidationError):
            InterviewInput.model_validate({
                "questions": [
                    {"id": "11111111-1111-4111-8111-111111111111", "text": "Первый"},
                    {"id": "11111111-1111-4111-8111-111111111111", "text": "Второй"},
                ],
            })

    def test_accepts_blocks_and_projects_coding_question(self) -> None:
        interview_input = InterviewInput.model_validate({
            "live_coding_enabled": True,
            "blocks": [{
                "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "title": "Практика",
                "topic": "coding",
                "questions": [{
                    "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "text": "Реализуйте очередь",
                    "kind": "coding",
                    "follow_up_after_answer": True,
                }],
            }],
        })
        self.assertEqual(interview_input.questions[0].kind, QuestionKind.CODING)
