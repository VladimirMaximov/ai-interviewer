"""Explainable three-way baseline recommendation for the local interview POC.

The recommendation is deliberately deterministic and content-only.  It is not a
hiring decision: a recruiter or hiring manager remains responsible for the next
step.
"""

from __future__ import annotations

import re
from enum import IntEnum, StrEnum
from typing import Any

from .errors import ValidationError


class BaselineRecommendationScore(IntEnum):
    NEEDS_REVIEW = -1
    DO_NOT_ADVANCE = 0
    ADVANCE = 1


class BaselineRecommendationLabel(StrEnum):
    NEEDS_REVIEW = "needs_review"
    DO_NOT_ADVANCE = "do_not_advance"
    ADVANCE = "advance"


LABEL_BY_SCORE = {
    BaselineRecommendationScore.NEEDS_REVIEW: BaselineRecommendationLabel.NEEDS_REVIEW,
    BaselineRecommendationScore.DO_NOT_ADVANCE: BaselineRecommendationLabel.DO_NOT_ADVANCE,
    BaselineRecommendationScore.ADVANCE: BaselineRecommendationLabel.ADVANCE,
}

POLICY_VERSION = "deterministic-baseline-recommendation-v1"
MINIMUM_EVIDENCE_COVERAGE = 0.6
MINIMUM_NORMALIZED_SCORE = 0.5
MINIMUM_CONCRETE_ANSWER_RATIO = 0.5


_DISENGAGEMENT_PATTERNS = (
    re.compile(
        r"^\s*(?:нет[,;:]?\s+)?(?:я\s+)?ничего\s+не\s+хочу[.!?]*\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:я\s+)?не\s+хочу\s+(?:работать|устраиваться|продолжать|"
        r"развиваться|эту\s+работу|эту\s+вакансию|эту\s+должность)"
        r"[.!?]*\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:эта\s+)?(?:вакансия|работа|должность)\s+"
        r"(?:мне\s+)?не\s+интересна[.!?]*\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:я\s+)?не\s+заинтересован(?:а)?(?:\s+в\s+этой\s+"
        r"(?:работе|вакансии|должности))?[.!?]*\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*i\s+(?:do\s+not|don't)\s+want\s+(?:anything|this\s+job)"
        r"[.!?]*\s*$",
        re.IGNORECASE,
    ),
)

_INABILITY_PATTERNS = (
    re.compile(r"\bне\s+знаю\b", re.IGNORECASE),
    re.compile(r"\bнет\s+опыта\b", re.IGNORECASE),
    re.compile(r"\bне\s+делал(?:а)?\b", re.IGNORECASE),
    re.compile(r"\bне\s+могу\s+ответить\b", re.IGNORECASE),
    re.compile(r"\bi\s+(?:do\s+not|don't)\s+know\b", re.IGNORECASE),
    re.compile(r"\bno\s+experience\b", re.IGNORECASE),
)

_CONCRETE_SIGNAL_GROUPS = (
    (
        "в проект",
        "в задаче",
        "в кейсе",
        "ситуац",
        "когда",
        "project",
        "case",
        "situation",
    ),
    (
        "я ",
        "моя роль",
        "отвечал",
        "сделал",
        "реализовал",
        "спроектировал",
        "настроил",
        "предложил",
        "выбрал",
        "i ",
        "my role",
    ),
    (
        "компромисс",
        "альтернатив",
        "риск",
        "сравнил",
        "потому",
        "trade-off",
        "tradeoff",
        "because",
        "risk",
    ),
    (
        "результат",
        "метрик",
        "проверил",
        "после запуска",
        "снизил",
        "увеличил",
        "%",
        "result",
        "metric",
        "measured",
        "reduced",
        "increased",
    ),
)


def build_baseline_recommendation(
    context_bundle: dict[str, Any],
    criterion_assessments: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return an auditable 1/0/-1 recommendation from stored answer evidence."""

    questions = context_bundle["candidate_evidence"]["questions"]
    answered = [item for item in questions if _answer_text(item)]

    disengagement = _first_match(questions, _DISENGAGEMENT_PATTERNS)
    if disengagement is not None:
        question, excerpt = disengagement
        return _result(
            score=BaselineRecommendationScore.DO_NOT_ADVANCE,
            comment=(
                "Baseline не рекомендует переводить кандидата на следующий этап: "
                f"в ответе на вопрос «{_short_question(question)}» кандидат прямо "
                f"сообщил об отсутствии интереса или готовности — «{excerpt}»."
            ),
            reason_codes=["explicit_disengagement"],
            evidence=[
                _evidence(
                    question,
                    excerpt=excerpt,
                    reason_code="explicit_disengagement",
                    note="Прямое высказывание об отсутствии интереса или готовности продолжать.",
                )
            ],
            metrics=calculate_recommendation_metrics(
                criterion_assessments,
                questions,
            ),
        )

    mandatory_failures = [
        item
        for item in criterion_assessments
        if item.get("category") == "must_have"
        and item.get("label") == "not_demonstrated"
    ]
    if mandatory_failures:
        evidence = _assessment_evidence(mandatory_failures[:3], questions)
        titles = ", ".join(
            str(item.get("criterion_title") or item.get("criterion_id"))
            for item in mandatory_failures[:3]
        )
        return _result(
            score=BaselineRecommendationScore.DO_NOT_ADVANCE,
            comment=(
                "Baseline не рекомендует переводить кандидата на следующий этап: "
                f"не подтверждены обязательные критерии вакансии — {titles}."
            ),
            reason_codes=["must_have_not_demonstrated"],
            evidence=evidence,
            metrics=calculate_recommendation_metrics(
                criterion_assessments,
                questions,
            ),
        )

    explicit_inability = [
        match
        for question in questions
        if (match := _match_question(question, _INABILITY_PATTERNS)) is not None
    ]
    if len(explicit_inability) >= 2 and len(explicit_inability) / max(len(answered), 1) >= 0.5:
        evidence = [
            _evidence(
                question,
                excerpt=excerpt,
                reason_code="repeated_explicit_knowledge_gap",
                note="Кандидат прямо сообщает об отсутствии знаний или опыта.",
            )
            for question, excerpt in explicit_inability[:3]
        ]
        return _result(
            score=BaselineRecommendationScore.DO_NOT_ADVANCE,
            comment=(
                "Baseline не рекомендует переводить кандидата на следующий этап: "
                f"в {len(explicit_inability)} из {len(answered)} ответов кандидат прямо "
                "сообщил об отсутствии знаний или опыта."
            ),
            reason_codes=["repeated_explicit_knowledge_gap"],
            evidence=evidence,
            metrics=calculate_recommendation_metrics(
                criterion_assessments,
                questions,
            ),
        )

    metrics = calculate_recommendation_metrics(criterion_assessments, questions)
    if metrics["evidence_coverage"] < MINIMUM_EVIDENCE_COVERAGE:
        gaps = [item for item in questions if not _answer_text(item)]
        evidence = [
            _evidence(
                item,
                excerpt=None,
                reason_code="missing_answer_evidence",
                note="Для вопроса нет текстового ответа, пригодного для проверки.",
            )
            for item in gaps[:3]
        ]
        return _result(
            score=BaselineRecommendationScore.NEEDS_REVIEW,
            comment=(
                "Baseline не уверен в результате: покрытие проверяемыми ответами "
                f"составляет {metrics['evidence_coverage']:.0%}, требуется ручная проверка."
            ),
            reason_codes=["insufficient_evidence_coverage"],
            evidence=evidence,
            metrics=metrics,
        )

    if (
        metrics["normalized_assessment_score"] >= MINIMUM_NORMALIZED_SCORE
        and metrics["concrete_answer_ratio"] >= MINIMUM_CONCRETE_ANSWER_RATIO
    ):
        strongest = sorted(
            (
                item
                for item in criterion_assessments
                if item.get("ordinal_value") is not None
                and item.get("evidence")
            ),
            key=lambda item: (
                -int(item["ordinal_value"]),
                str(item.get("criterion_id", "")),
            ),
        )
        return _result(
            score=BaselineRecommendationScore.ADVANCE,
            comment=(
                "Baseline рекомендует следующий этап: ответы покрывают критерии, "
                "а кандидат приводит конкретные действия, аргументацию или результат. "
                f"Нормализованная оценка {metrics['normalized_assessment_score']:.0%}, "
                f"покрытие evidence {metrics['evidence_coverage']:.0%}."
            ),
            reason_codes=["sufficient_supported_evidence"],
            evidence=_assessment_evidence(strongest[:3], questions),
            metrics=metrics,
        )

    weak = sorted(
        (
            item
            for item in criterion_assessments
            if item.get("ordinal_value") is not None and item.get("evidence")
        ),
        key=lambda item: (
            int(item["ordinal_value"]),
            str(item.get("criterion_id", "")),
        ),
    )
    return _result(
        score=BaselineRecommendationScore.NEEDS_REVIEW,
        comment=(
            "Baseline не уверен в результате: формального evidence достаточно, но "
            "ответы не преодолели порог подтверждённости или конкретности. "
            f"Нормализованная оценка {metrics['normalized_assessment_score']:.0%}, "
            f"доля конкретных ответов {metrics['concrete_answer_ratio']:.0%}."
        ),
        reason_codes=["borderline_answer_quality"],
        evidence=_assessment_evidence(weak[:3], questions),
        metrics=metrics,
    )


def validate_baseline_recommendation(
    recommendation: dict[str, Any], *, answers: dict[str, str]
) -> None:
    """Reject malformed recommendations or evidence not found in stored answers."""

    try:
        score = BaselineRecommendationScore(recommendation["score"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("baseline recommendation score is invalid") from exc
    expected_label = LABEL_BY_SCORE[score].value
    if recommendation.get("label") != expected_label:
        raise ValidationError("baseline recommendation label does not match score")
    if recommendation.get("is_hiring_decision") is not False:
        raise ValidationError("baseline recommendation cannot be a hiring decision")
    if (
        not isinstance(recommendation.get("comment"), str)
        or not recommendation["comment"].strip()
    ):
        raise ValidationError("baseline recommendation requires a comment")
    reason_codes = recommendation.get("reason_codes")
    if not isinstance(reason_codes, list) or not reason_codes:
        raise ValidationError("baseline recommendation requires reason codes")
    evidence = recommendation.get("evidence")
    if not isinstance(evidence, list):
        raise ValidationError("baseline recommendation evidence must be a list")
    if score is not BaselineRecommendationScore.NEEDS_REVIEW and not evidence:
        raise ValidationError("advance and do-not-advance recommendations require evidence")
    for item in evidence:
        question_id = item.get("question_id")
        if question_id not in answers:
            raise ValidationError("baseline evidence question is not in the interview")
        excerpt = item.get("excerpt")
        if excerpt is not None and excerpt not in answers[question_id]:
            raise ValidationError("baseline evidence excerpt must occur in the stored answer")


def calculate_recommendation_metrics(
    criterion_assessments: list[dict[str, Any]], questions: list[dict[str, Any]]
) -> dict[str, float]:
    """Calculate display metrics without asking a model to do arithmetic."""

    applicable_weight = sum(int(item.get("weight", 1)) for item in criterion_assessments)
    assessed = [
        item
        for item in criterion_assessments
        if item.get("ordinal_value") is not None
    ]
    assessed_weight = sum(int(item.get("weight", 1)) for item in assessed)
    weighted_score = sum(
        int(item.get("weight", 1)) * int(item["ordinal_value"])
        for item in assessed
    )
    answered = [item for item in questions if _answer_text(item)]
    concrete = [
        item for item in answered if _has_concrete_evidence(_answer_text(item))
    ]
    return {
        "evidence_coverage": round(
            assessed_weight / applicable_weight if applicable_weight else 0.0,
            4,
        ),
        "normalized_assessment_score": round(
            weighted_score / (3 * assessed_weight) if assessed_weight else 0.0,
            4,
        ),
        "concrete_answer_ratio": round(
            len(concrete) / len(answered) if answered else 0.0,
            4,
        ),
    }


def _result(
    *,
    score: BaselineRecommendationScore,
    comment: str,
    reason_codes: list[str],
    evidence: list[dict[str, Any]],
    metrics: dict[str, float],
) -> dict[str, Any]:
    return {
        "policy_version": POLICY_VERSION,
        "score": int(score),
        "label": LABEL_BY_SCORE[score].value,
        "comment": comment,
        "reason_codes": reason_codes,
        "evidence": evidence,
        "metrics": metrics,
        "is_hiring_decision": False,
        "limitations": [
            "Детерминированный baseline не проверяет фактическую корректность технического ответа.",
            "Рекомендацию должен подтвердить рекрутёр или нанимающий менеджер.",
        ],
    }


def _assessment_evidence(
    assessments: list[dict[str, Any]], questions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in questions}
    result = []
    for assessment in assessments:
        source = assessment["evidence"][0]
        question = by_id.get(source.get("question_id"))
        if question is None:
            continue
        result.append(
            _evidence(
                question,
                excerpt=source.get("excerpt"),
                reason_code="criterion_assessment",
                note=(
                    f"{assessment.get('criterion_title', assessment.get('criterion_id'))}: "
                    f"{assessment.get('label')}."
                ),
            )
        )
    return result


def _evidence(
    question: dict[str, Any],
    *,
    excerpt: str | None,
    reason_code: str,
    note: str,
) -> dict[str, Any]:
    return {
        "question_id": question["id"],
        "question": question["prompt"],
        "excerpt": excerpt,
        "reason_code": reason_code,
        "note": note,
    }


def _first_match(
    questions: list[dict[str, Any]], patterns: tuple[re.Pattern[str], ...]
) -> tuple[dict[str, Any], str] | None:
    for question in questions:
        match = _match_question(question, patterns)
        if match is not None:
            return match
    return None


def _match_question(
    question: dict[str, Any], patterns: tuple[re.Pattern[str], ...]
) -> tuple[dict[str, Any], str] | None:
    answer = _answer_text(question)
    for pattern in patterns:
        if pattern.search(answer):
            return question, _short_excerpt(answer)
    return None


def _answer_text(question: dict[str, Any]) -> str:
    value = question.get("answer")
    return value.strip() if isinstance(value, str) else ""


def _has_concrete_evidence(answer: str) -> bool:
    lowered = answer.casefold()
    signals = sum(any(marker in lowered for marker in group) for group in _CONCRETE_SIGNAL_GROUPS)
    return signals >= 2


def _short_question(question: dict[str, Any]) -> str:
    prompt = str(question.get("prompt", "")).strip()
    return prompt if len(prompt) <= 140 else prompt[:137].rstrip() + "..."


def _short_excerpt(answer: str) -> str:
    # The excerpt is persisted as evidence, so it must remain an exact substring.
    return answer if len(answer) <= 280 else answer[:280].rstrip()
