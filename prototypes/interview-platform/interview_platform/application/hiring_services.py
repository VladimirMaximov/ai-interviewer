"""Composition-friendly bundle for the vacancy-aware use cases."""

from __future__ import annotations

from dataclasses import dataclass

from .assessment_services import AssessmentService
from .feedback_services import FeedbackService
from .ranking_services import DecisionService, RankingService
from .vacancy_services import VacancyService


@dataclass(frozen=True, slots=True)
class HiringServices:
    vacancies: VacancyService
    assessments: AssessmentService
    rankings: RankingService
    decisions: DecisionService
    feedback: FeedbackService
