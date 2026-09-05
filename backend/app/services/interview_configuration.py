"""Authoritative editable vacancy configuration and invitation snapshots."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.hiring_context import (
    HiringContextNotFoundError,
    HiringContextValidationError,
    VacancyStatus,
)
from app.interview_config import (
    InterviewInput,
    default_interview_input,
    normalized_snapshot,
)
from app.models.hiring_context import Vacancy


def read_configuration(db: Session, vacancy_id: UUID) -> InterviewInput:
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HiringContextNotFoundError("vacancy was not found")
    if not vacancy.interview_config:
        return default_interview_input()
    return InterviewInput.model_validate(vacancy.interview_config)


def save_configuration(
    db: Session, vacancy_id: UUID, configuration: InterviewInput
) -> InterviewInput:
    vacancy = db.get(Vacancy, vacancy_id)
    if vacancy is None:
        raise HiringContextNotFoundError("vacancy was not found")
    if vacancy.status is not VacancyStatus.ACTIVE:
        raise HiringContextValidationError("vacancy is not active")
    snapshot = normalized_snapshot(configuration)
    vacancy.interview_config = snapshot
    vacancy.interview_config_revision = (vacancy.interview_config_revision or 0) + 1
    db.commit()
    return InterviewInput.model_validate(snapshot)


def invitation_snapshot(vacancy: Vacancy) -> dict:
    configuration = (
        InterviewInput.model_validate(vacancy.interview_config)
        if vacancy.interview_config
        else default_interview_input()
    )
    return normalized_snapshot(configuration)
