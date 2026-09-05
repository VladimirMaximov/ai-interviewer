"""Validated, invitation-scoped question blocks and candidate-safe projections."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class QuestionKind(StrEnum):
    SPOKEN = "spoken"
    CODING = "coding"


class QuestionBlockKey(StrEnum):
    HARD_SKILLS = "hard_skills"
    SOFT_SKILLS = "soft_skills"
    WORK_EXPERIENCE = "work_experience"


DEFAULT_QUESTIONS = [
    {"id": "11111111-1111-4111-8111-111111111111", "text": "Расскажите о последнем проекте и вашей роли в нём.", "follow_up_after_answer": False},
    {"id": "22222222-2222-4222-8222-222222222222", "text": "Как вы обычно находите и устраняете сложную техническую проблему?", "follow_up_after_answer": False},
    {"id": "33333333-3333-4333-8333-333333333333", "text": "Какие технологии вы хотели бы применять в следующем проекте?", "follow_up_after_answer": True},
]


class InterviewQuestionInput(BaseModel):
    id: UUID
    text: str = Field(min_length=1, max_length=2_000)
    kind: QuestionKind = QuestionKind.SPOKEN
    follow_up_after_answer: bool = False
    time_limit_seconds: int | None = Field(default=None, ge=30, le=7200)

class InterviewQuestionBlockInput(BaseModel):
    id: UUID
    title: str = Field(min_length=1, max_length=160)
    topic: str = Field(min_length=1, max_length=160)
    key: QuestionBlockKey | None = None
    questions: list[InterviewQuestionInput] = Field(min_length=1, max_length=50)


class InterviewInput(BaseModel):
    blocks: list[InterviewQuestionBlockInput] = Field(min_length=1, max_length=20)
    follow_up_after_all_answers: bool = False
    live_coding_enabled: bool = False

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_flat_questions(cls, value: object) -> object:
        if isinstance(value, dict) and "blocks" not in value and "questions" in value:
            return {
                "blocks": [{
                    "id": "00000000-0000-4000-8000-000000000001",
                    "title": "Интервью",
                    "topic": "general",
                    "questions": value["questions"],
                }],
                "follow_up_after_all_answers": value.get("follow_up_after_all_answers", False),
            }
        return value

    @model_validator(mode="after")
    def unique_question_ids(self) -> "InterviewInput":
        question_ids = [question.id for block in self.blocks for question in block.questions]
        if len(set(question_ids)) != len(question_ids):
            raise ValueError("question ids must be unique across blocks")
        coding_blocks = [block for block in self.blocks if any(question.kind is QuestionKind.CODING for question in block.questions)]
        if coding_blocks and not self.live_coding_enabled:
            raise ValueError("coding questions require live_coding_enabled")
        if any(block.key is not None for block in self.blocks):
            expected = [QuestionBlockKey.HARD_SKILLS, QuestionBlockKey.SOFT_SKILLS, QuestionBlockKey.WORK_EXPERIENCE]
            if [block.key for block in self.blocks] != expected:
                raise ValueError("the three candidate blocks must be hard_skills, soft_skills, work_experience in order")
            if any(block.key is not QuestionBlockKey.HARD_SKILLS for block in coding_blocks):
                raise ValueError("coding questions belong only to hard_skills")
        return self

    @property
    def questions(self) -> list[InterviewQuestionInput]:
        return [question for block in self.blocks for question in block.questions]


def default_interview_input() -> InterviewInput:
    return InterviewInput.model_validate({"questions": DEFAULT_QUESTIONS})


def invitation_input(question_config: object, follow_up_after_all_answers: bool) -> InterviewInput:
    if not question_config:
        return default_interview_input()
    if isinstance(question_config, dict):
        payload = {**question_config, "follow_up_after_all_answers": follow_up_after_all_answers}
    else:
        payload = {"questions": question_config, "follow_up_after_all_answers": follow_up_after_all_answers}
    return InterviewInput.model_validate(payload)
