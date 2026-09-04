"""Run the complete multi-agent harness against VseGPT on synthetic data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
import app.models.multi_agent  # noqa: F401
from app.adapters.openai_interview_agents import build_openai_interview_agents
from app.config import settings
from app.domain.hiring_context import VacancyStatus
from app.domain.multi_agent import (
    AgentPurpose,
    MultiAgentOutputError,
    MultiAgentProviderError,
    QuestionKind,
    QuestionPlanOutput,
)
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    Base,
    CandidateResponse,
    InterviewInvitation,
    InterviewSession,
    InvitationStatus,
    TranscriptionStatus,
)
from app.models.multi_agent import AgentArtifact, AgentOperation, AgentRun
from app.security.invitations import digest_invitation_secret
from app.services.multi_agent_harness import MultiAgentHarness


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPOSITORY_ROOT / Path(
    "deliverables/ai-technical-interview/vsegpt-python-middle-evidence-id-run.md"
)
RAW_OUTPUT_PATH = OUTPUT_PATH.with_suffix(".json")
CHECKPOINT_PATH = OUTPUT_PATH.with_name(
    "vsegpt-python-middle-evidence-id-raw-v2.sqlite3"
)
ACTOR_ID = "synthetic-evaluation-runner"
PIPELINE_REVISION = "evidence-ids-raw-v2"
CHECKPOINT_MAX_ATTEMPTS = 9

VACANCY_TEXT = """Middle + Python Developer
Уровень должности: Middle
Тип занятости: Полная занятость
Зарплата: Не указана
Опыт работы: от 3 лет коммерческой разработки
Регионы показа вакансии: Санкт-Петербург/ Челябинск

Обязанности:
● Разработка и поддержка высоконагруженных микросервисов;
● Интеграция с Kafka для обработки потоков данных;
● Проектирование Event Sourcing и CQRS паттернов;
● Разработка API для межсервисного взаимодействия;
● Настройка мониторинга и алертинга сервисов;
● Участие в Code review.

Требования:
● Опыт работы с Python от 5 лет;
● Django/FastAPI - опыт разработки REST API;
● Микросервисная архитектура - опыт проектирования и поддержки;
● Apache Kafka - продакшн опыт работы с producers/consumers;
● PostgreSQL - проектирование схем, оптимизация запросов;
● ETL процессы - Extract, Transform, Load данных;
● Docker/Kubernetes - контейнеризация и оркестрация;
● Базы данных: PostgreSQL, ClickHouse;
● Event-driven архитектура - паттерны работы с событиями;
● API Gateway - опыт интеграции через шлюзы;
● Мониторинг: Prometheus, Grafana или аналоги;
● Git, CI/CD - DevOps практики.

Будет плюсом:
● Знание gRPC для межсервисного взаимодействия;
● Опыт с ELK Stack (Elasticsearch, Logstash, Kibana);
● Redis Cluster для высокодоступного кэширования;
● Знание Domain-Driven Design (DDD);
● Опыт performance tuning Python приложений.

Условия:
● Удаленная работа, гибкое начало и конец рабочего дня при синхронизации с командой.
● Индивидуальный план развития с возможностью освоения новых технологий.
● Насыщенная корпоративная жизнь.
● Оплата профильных конференций и профессиональной литературы.
● Доступ к курсам GIGASCHOOL.
"""

RESUME_TEXT = """СИНТЕТИЧЕСКОЕ РЕЗЮМЕ — данные не принадлежат реальному человеку.

Позиция 1: BetaSoft, Python-разработчик, июнь 2018 — август 2021.
Проект: REST-платформа обработки заказов.
Обязанности: разработка Django REST API, проектирование схем PostgreSQL, оптимизация SQL,
контейнеризация в Docker, участие в code review и настройке GitLab CI/CD.
Достижение: сократил p95 ответа API с 900 до 320 мс после профилирования Python-кода и SQL.

Позиция 2: StreamWorks, Middle Python Developer, сентябрь 2021 — настоящее время.
Проект: высоконагруженная событийная платформа, 12 микросервисов и до 18 000 событий в секунду.
Обязанности: разработка FastAPI-микросервисов; Kafka producers и consumers; внедрение transactional
outbox, идемпотентности, Event Sourcing и CQRS в сервисе статусов; ETL из PostgreSQL в ClickHouse;
деплой в Kubernetes; мониторинг Prometheus и Grafana; алерты и разбор инцидентов; code review.
Достижение: снизил долю повторно обработанных событий с 1,8% до 0,03%, добавив idempotency key,
retry с backoff и dead-letter topic. Настроил gRPC между двумя внутренними сервисами и Redis Cluster
для кэша справочников. Регулярно писал ADR и согласовывал изменения контрактов с соседними командами.
"""

ALTERNATIVE_VACANCY_TEXT = """Middle Data Platform Python Developer.
Требования: Middle, Python, FastAPI, Kafka, ETL, PostgreSQL, ClickHouse, Docker, Kubernetes,
Prometheus, Grafana. Задачи: потоковая обработка данных, сервисы загрузки данных и REST API.
"""

ANSWERS = {
    "technical_depth": (
        "Я лично проектировал обработчик статусов на FastAPI для потока до 18 000 событий в секунду. "
        "Сначала замерил p95 и lag consumer group, затем сравнил прямую запись и transactional outbox. "
        "Выбрал outbox с PostgreSQL и Kafka: producer использовал idempotency key, consumer фиксировал "
        "обработанные ключи, retry выполнялся с exponential backoff, ошибки уходили в dead-letter topic. "
        "Схему события версионировали, миграцию провели без остановки. После нагрузочного теста доля "
        "повторной обработки снизилась с 1,8% до 0,03%, p95 составил 210 мс. Решение оформил в ADR, "
        "обсудил на code review и добавил дашборд Grafana с алертами на lag и DLQ."
    ),
    "collaboration": (
        "На проекте команда спорила, вводить ли Event Sourcing во всех сервисах. Я предложил не спорить "
        "на уровне предпочтений: собрал требования, подготовил ADR и два прототипа. Вместе с аналитиком, "
        "SRE и разработчиками сравнили сложность восстановления, latency и стоимость поддержки. Решили "
        "применить Event Sourcing и CQRS только в сервисе истории статусов, а в остальных оставить "
        "transactional outbox. Я учёл замечания коллег, обновил контракты и провёл совместное code review. "
        "Команда приняла решение, а релиз прошёл без конфликтов между потребителями Kafka."
    ),
    "ownership": (
        "После ночного инцидента с ростом Kafka lag я взял координацию, хотя дежурил другой сервис. "
        "Проверил метрики Prometheus, нашёл медленный запрос PostgreSQL в consumer, добавил индекс и "
        "временно уменьшил batch. Сообщал команде статус каждые 20 минут и после восстановления создал "
        "postmortem без поиска виноватых. Затем добавил нагрузочный тест в CI, алерт на прогнозируемый lag "
        "и runbook. Время обнаружения похожей проблемы на следующей проверке сократилось с 25 до 4 минут."
    ),
    "primary_vacancy_fit": (
        "Ближе всего мне разработка высоконагруженных FastAPI-микросервисов, Kafka producers/consumers, "
        "PostgreSQL и ClickHouse ETL. С Python коммерчески работаю с июня 2018 года. В Kubernetes "
        "настраивал deployment, readiness probes и limits, в Prometheus и Grafana — метрики, дашборды и "
        "алерты. Использовал API Gateway для маршрутизации REST API и gRPC для двух внутренних сервисов. "
        "Event Sourcing и CQRS применял адресно, потому что для обычного CRUD их сложность не окупается. "
        "Я готов отвечать за разработку, эксплуатацию и code review таких сервисов."
    ),
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _exception_chain(error: BaseException) -> list[str]:
    result: list[str] = []
    current: BaseException | None = error
    while current is not None:
        message = str(current)
        if settings.openai_api_key:
            message = message.replace(settings.openai_api_key, "[api-key-redacted]")
        message = re.sub(r"sk-[A-Za-z0-9_-]+", "[api-key-redacted]", message)
        message = re.sub(
            r"\(\d{6,}\)", "(account-id-redacted)", message
        )
        result.append(f"{type(current).__name__}: {message}")
        current = current.__cause__ or current.__context__
    return result


def _retry_stage(
    label: str,
    callback: Callable[[], Any],
    events: list[dict[str, Any]],
) -> Any:
    for attempt in range(1, settings.multi_agent_max_attempts + 1):
        started = time.monotonic()
        try:
            result = callback()
        except (MultiAgentOutputError, MultiAgentProviderError) as error:
            errors = _exception_chain(error)
            events.append(
                {
                    "stage": label,
                    "attempt": attempt,
                    "status": "failed",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "errors": errors,
                }
            )
            non_retryable = any(
                marker in item.casefold()
                for item in errors
                for marker in (
                    "subscription end",
                    "not available on your subscription plan",
                    "out of budget",
                    "api key not found",
                )
            )
            if non_retryable or attempt == settings.multi_agent_max_attempts:
                raise
        else:
            events.append(
                {
                    "stage": label,
                    "attempt": attempt,
                    "status": "succeeded",
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                }
            )
            return result
    raise RuntimeError("unreachable retry state")


def _seed(db: Session) -> tuple[Vacancy, Vacancy, InterviewInvitation, InterviewSession]:
    existing_primary = db.scalar(
        select(Vacancy).where(
            Vacancy.created_by == ACTOR_ID,
            Vacancy.idempotency_key == "synthetic-primary-vacancy-v1",
        )
    )
    if existing_primary is not None:
        existing_alternative = db.scalar(
            select(Vacancy).where(
                Vacancy.created_by == ACTOR_ID,
                Vacancy.idempotency_key == "synthetic-alternative-vacancy-v1",
            )
        )
        invitation = db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.vacancy_id == existing_primary.id,
                InterviewInvitation.created_by == ACTOR_ID,
            )
        )
        interview = (
            db.scalar(
                select(InterviewSession).where(
                    InterviewSession.invitation_id == invitation.id
                )
            )
            if invitation is not None
            else None
        )
        if existing_alternative is None or invitation is None or interview is None:
            raise RuntimeError("synthetic checkpoint is incomplete")
        return existing_primary, existing_alternative, invitation, interview

    now = datetime.now(timezone.utc)
    primary = Vacancy(
        title="Middle + Python Developer",
        source_filename="synthetic-python-middle-vacancy.txt",
        media_type="text/plain",
        byte_size=len(VACANCY_TEXT.encode("utf-8")),
        extracted_text=VACANCY_TEXT,
        content_hash=_hash(VACANCY_TEXT),
        status=VacancyStatus.ACTIVE,
        created_by=ACTOR_ID,
        idempotency_key="synthetic-primary-vacancy-v1",
        created_at=now,
    )
    alternative = Vacancy(
        title="Middle Data Platform Python Developer",
        source_filename="synthetic-alternative-vacancy.txt",
        media_type="text/plain",
        byte_size=len(ALTERNATIVE_VACANCY_TEXT.encode("utf-8")),
        extracted_text=ALTERNATIVE_VACANCY_TEXT,
        content_hash=_hash(ALTERNATIVE_VACANCY_TEXT),
        status=VacancyStatus.ACTIVE,
        created_by=ACTOR_ID,
        idempotency_key="synthetic-alternative-vacancy-v1",
        created_at=now,
    )
    db.add_all([primary, alternative])
    db.flush()
    invitation = InterviewInvitation(
        token_digest=digest_invitation_secret("synthetic-local-token"),
        vacancy_id=primary.id,
        candidate_alias="Синтетический кандидат PY-001",
        created_by=ACTOR_ID,
        expires_at=now + timedelta(days=1),
        status=InvitationStatus.ACTIVE,
    )
    db.add(invitation)
    db.flush()
    interview = InterviewSession(invitation_id=invitation.id, consented_at=now)
    resume = CandidateResume(
        invitation_id=invitation.id,
        vacancy_id=primary.id,
        version=1,
        source_filename="synthetic-resume.txt",
        media_type="text/plain",
        byte_size=len(RESUME_TEXT.encode("utf-8")),
        extracted_text=RESUME_TEXT,
        content_hash=_hash(RESUME_TEXT),
        idempotency_key="synthetic-resume-v1",
        uploaded_by_role="candidate",
        uploaded_by_actor_id=None,
        created_at=now,
    )
    db.add_all([interview, resume])
    db.commit()
    return primary, alternative, invitation, interview


def _answer_for(question: Any) -> str:
    prompt = question.prompt.casefold()
    if "разногласи" in prompt:
        return ANSWERS["collaboration"]
    if "ответственност" in prompt:
        return ANSWERS["ownership"]
    if "задач" in prompt and "ваканс" in prompt:
        return ANSWERS["primary_vacancy_fit"]
    return ANSWERS["technical_depth"]


def _stored_response(
    db: Session,
    interview_id: UUID,
    question_id: UUID,
    transcript: str,
) -> CandidateResponse:
    existing = db.scalar(
        select(CandidateResponse).where(
            CandidateResponse.session_id == interview_id,
            CandidateResponse.question_id == question_id,
        )
    )
    if existing is not None:
        if existing.transcript_text != transcript:
            raise RuntimeError("synthetic checkpoint answer does not match fixture")
        return existing
    response = CandidateResponse(
        session_id=interview_id,
        question_id=question_id,
        storage_key=f"synthetic/responses/{uuid4()}.webm",
        content_type="audio/webm",
        checksum=_hash(transcript),
        transcription_status=TranscriptionStatus.COMPLETED,
        transcript_text=transcript,
        created_at=datetime.now(timezone.utc),
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def _agent_runs(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        select(AgentRun, AgentOperation)
        .join(AgentOperation, AgentOperation.id == AgentRun.operation_id)
        .order_by(AgentRun.started_at, AgentRun.id)
    ).all()
    return [
        {
            "purpose": operation.purpose,
            "attempt": run.attempt,
            "status": run.status.value,
            "model_adapter": run.model_id,
            "model": run.model_version,
            "prompt_id": run.prompt_id,
            "failure_code": run.failure_code,
            "output_payload": run.output_payload,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        for run, operation in rows
    ]


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _resolved_evidence_view(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve selected IDs for display without changing any agent payload."""

    catalogs = report.get("evidence_catalogs", {})
    resume = {
        item["evidence_id"]: item["text"]
        for item in catalogs.get("resume", [])
    }
    requirements = {
        item["requirement_id"]: item
        for item in catalogs.get("requirements", [])
    }
    answers = {
        response_id: {
            item["evidence_id"]: item["text"] for item in entries
        }
        for response_id, entries in catalogs.get("answers", {}).items()
    }
    feedback_evidence = {
        item["evidence_reference"]: item
        for item in catalogs.get("candidate_feedback", [])
    }
    answer_references: dict[str, dict[str, Any]] = {}
    for artifact in report.get("artifacts", []):
        if artifact["kind"] != "answer_assessment":
            continue
        payload = artifact["payload"]
        response_id = payload["response_id"]
        for observation in payload["observations"]:
            for index, evidence in enumerate(observation["evidence"]):
                evidence_id = evidence["evidence_id"]
                answer_references[
                    f"{artifact['id']}:{observation['criterion_id']}:{index}"
                ] = {
                    "evidence_id": evidence_id,
                    "text": (
                        answers[response_id][evidence_id]
                        if evidence_id is not None
                        else None
                    ),
                }
    resolved: list[dict[str, Any]] = []
    for artifact in report.get("artifacts", []):
        payload = artifact["payload"]
        if artifact["kind"] == "resume_relevance":
            for item_type in ("positions", "claims", "experience_matches"):
                for index, item in enumerate(payload[item_type]):
                    entry = {
                        "artifact_id": artifact["id"],
                        "agent_purpose": artifact["kind"],
                        "item_type": item_type,
                        "item_index": index,
                        "selected_evidence": [
                            {
                                "evidence_id": evidence_id,
                                "text": resume[evidence_id],
                            }
                            for evidence_id in item["evidence_ids"]
                        ],
                    }
                    if item_type == "experience_matches":
                        entry["selected_requirement"] = requirements[
                            item["requirement_id"]
                        ]
                    resolved.append(entry)
        elif artifact["kind"] == "answer_assessment":
            response_id = payload["response_id"]
            for observation in payload["observations"]:
                resolved.append(
                    {
                        "artifact_id": artifact["id"],
                        "agent_purpose": artifact["kind"],
                        "criterion_id": observation["criterion_id"],
                        "selected_evidence": [
                            {
                                "kind": evidence["kind"],
                                "evidence_id": evidence["evidence_id"],
                                "text": (
                                    answers[response_id][evidence["evidence_id"]]
                                    if evidence["evidence_id"] is not None
                                    else None
                                ),
                            }
                            for evidence in observation["evidence"]
                        ],
                    }
                )
        elif artifact["kind"] == "integrity_check":
            for observation in payload["observations"]:
                response_id = observation["response_id"]
                resume_id = observation["resume_evidence_id"]
                answer_id = observation["answer_evidence_id"]
                resolved.append(
                    {
                        "artifact_id": artifact["id"],
                        "agent_purpose": artifact["kind"],
                        "resume_evidence": (
                            {"evidence_id": resume_id, "text": resume[resume_id]}
                            if resume_id is not None
                            else None
                        ),
                        "answer_evidence": (
                            {
                                "evidence_id": answer_id,
                                "text": answers[response_id][answer_id],
                            }
                            if answer_id is not None and response_id is not None
                            else None
                        ),
                    }
                )
        elif artifact["kind"] == "alternative_vacancy_match":
            resolved.append(
                {
                    "artifact_id": artifact["id"],
                    "agent_purpose": artifact["kind"],
                    "selected_evidence": [
                        {
                            "evidence_reference": reference,
                            **answer_references[reference],
                        }
                        for reference in payload["evidence_references"]
                    ],
                }
            )
        elif artifact["kind"] == "candidate_feedback":
            for item_type in (
                "strengths",
                "growth_areas",
                "experience_alignment",
            ):
                for index, item in enumerate(payload[item_type]):
                    resolved.append(
                        {
                            "artifact_id": artifact["id"],
                            "agent_purpose": artifact["kind"],
                            "item_type": item_type,
                            "item_index": index,
                            "selected_evidence": [
                                feedback_evidence[reference]
                                for reference in item["evidence_references"]
                            ],
                        }
                    )
    return resolved


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Мок-прогон мультиагентной системы: Middle + Python Developer",
        "",
        f"- Статус: `{report['status']}`",
        f"- Тип данных: `{report['data_classification']}`",
        f"- Провайдер: `{report['provider']['base_url']}`",
        f"- API-режим: `{report['provider']['api_mode']}`",
        f"- Модель: `{report['provider']['model']}`",
        f"- Начало: `{report['started_at']}`",
        f"- Завершение: `{report['completed_at']}`",
        "",
        "## Итог",
        "",
        report.get("summary", "Прогон не завершён."),
        "",
        "### Статистика фактических LLM-вызовов",
        "",
        "```json",
        _json_block(report.get("run_statistics", {})),
        "```",
        "",
        "## Выполнение этапов",
        "",
        "```json",
        _json_block(report.get("events", [])),
        "```",
        "",
        "## Аудит LLM-запусков",
        "",
        "Ответы ниже сохранены без сортировки, исправления цитат, замены "
        "идентификаторов, удаления наблюдений или корректировки оценок. Поле "
        "`status` показывает результат отдельной read-only валидации.",
        "",
        "```json",
        _json_block(report.get("agent_runs", [])),
        "```",
        "",
        "## Входные мок-данные",
        "",
        "### Вакансия",
        "",
        report["inputs"]["vacancy"],
        "",
        "### Синтетическое резюме",
        "",
        report["inputs"]["resume"],
        "",
        "### Сохранённые ответы",
        "",
        "```json",
        _json_block(report["inputs"].get("answers", [])),
        "```",
        "",
        "## Детерминированные каталоги доказательств",
        "",
        "Это отдельное представление исходных текстов. Оно не является частью "
        "сырого ответа LLM и используется только для разрешения выбранных ID.",
        "",
        "```json",
        _json_block(report.get("evidence_catalogs", {})),
        "```",
        "",
        "## Выбранные ID, разрешённые в исходный текст",
        "",
        "```json",
        _json_block(report.get("resolved_evidence", [])),
        "```",
        "",
        "## Артефакты агентов и детерминированный профиль",
        "",
        "```json",
        _json_block(report.get("artifacts", [])),
        "```",
        "",
        "## Черновик обратной связи кандидату",
        "",
        "```json",
        _json_block(report.get("candidate_feedback")),
        "```",
        "",
        "## Ошибки",
        "",
        "```json",
        _json_block(report.get("errors", [])),
        "```",
        "",
        "Отчёт не является решением о найме. Публикация обратной связи и любые "
        "ограничения требуют отдельного решения человека.",
        "",
    ]
    return "\n".join(lines)


def _write_report(report: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(_json_block(report) + "\n", encoding="utf-8")
    OUTPUT_PATH.write_text(_render_markdown(report), encoding="utf-8")


def main() -> int:
    started_at = datetime.now(timezone.utc)
    report: dict[str, Any] = {
        "status": "running",
        "data_classification": "synthetic",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "provider": {
            "base_url": settings.openai_base_url,
            "api_mode": settings.multi_agent_api_mode,
            "model": settings.multi_agent_model,
            "api_key_present": bool(settings.openai_api_key),
        },
        "output_policy": {
            "llm_outputs_modified": False,
            "validation_is_read_only": True,
            "schema_invalid_json_objects_are_preserved": True,
            "derived_profile_is_separate_from_llm_outputs": True,
        },
        "inputs": {
            "vacancy": VACANCY_TEXT,
            "resume": RESUME_TEXT,
            "alternative_vacancy": ALTERNATIVE_VACANCY_TEXT,
            "answers": [],
        },
        "events": [],
        "agent_runs": [],
        "run_statistics": {},
        "artifacts": [],
        "evidence_catalogs": {},
        "resolved_evidence": [],
        "candidate_feedback": None,
        "errors": [],
    }
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+pysqlite:///{CHECKPOINT_PATH.resolve()}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        try:
            if not settings.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            if settings.multi_agent_api_mode != "chat_completions":
                raise RuntimeError(
                    "MULTI_AGENT_API_MODE must be chat_completions for VseGPT"
                )
            primary, _alternative, invitation, interview = _seed(db)
            agents = build_openai_interview_agents(
                api_key=settings.openai_api_key,
                model=settings.multi_agent_model,
                base_url=settings.openai_base_url,
                timeout_seconds=settings.multi_agent_timeout_seconds,
                api_mode=settings.multi_agent_api_mode,
            )
            harness = MultiAgentHarness(
                db,
                agents,
                max_attempts=max(
                    CHECKPOINT_MAX_ATTEMPTS,
                    settings.multi_agent_max_attempts,
                ),
                strong_pool_min_readiness=settings.strong_pool_min_readiness,
                strong_pool_min_coverage=settings.strong_pool_min_coverage,
                alternative_min_fit=settings.alternative_vacancy_min_fit,
                alternative_max_grade_distance=settings.alternative_max_grade_distance,
                personalization_cap=settings.multi_agent_personalization_cap,
            )
            harness.create_session(
                vacancy_id=primary.id,
                invitation_id=invitation.id,
                actor_id=ACTOR_ID,
                idempotency_key=f"synthetic-agent-session-{PIPELINE_REVISION}",
            )
            report["evidence_catalogs"]["resume"] = harness._evidence_catalog(
                RESUME_TEXT,
                "resume",
            )
            report["evidence_catalogs"]["requirements"] = (
                harness._requirement_catalog(VACANCY_TEXT, None)
            )
            _retry_stage(
                "resume_relevance",
                lambda: harness.run_resume_analysis(
                    vacancy_id=primary.id,
                    invitation_id=invitation.id,
                    idempotency_key=f"synthetic-resume-analysis-{PIPELINE_REVISION}",
                ),
                report["events"],
            )
            plan_artifact = _retry_stage(
                "question_plan",
                lambda: harness.run_question_plan(
                    vacancy_id=primary.id,
                    invitation_id=invitation.id,
                    idempotency_key=f"synthetic-question-plan-{PIPELINE_REVISION}",
                ),
                report["events"],
            )
            plan = QuestionPlanOutput.model_validate(plan_artifact.payload)
            baseline_questions = [
                question
                for question in plan.questions
                if question.kind is QuestionKind.BASELINE
            ]
            for index, question in enumerate(baseline_questions, start=1):
                transcript = _answer_for(question)
                response = _stored_response(
                    db, interview.id, question.question_id, transcript
                )
                report["inputs"]["answers"].append(
                    {
                        "response_id": str(response.id),
                        "question_id": str(question.question_id),
                        "question": question.prompt,
                        "answer": transcript,
                    }
                )
                report["evidence_catalogs"].setdefault("answers", {})[
                    str(response.id)
                ] = harness._evidence_catalog(
                    transcript,
                    f"answer:{response.id}",
                )
                _retry_stage(
                    f"answer_assessment_{index}",
                    lambda response=response, index=index: harness.assess_answer(
                        vacancy_id=primary.id,
                        invitation_id=invitation.id,
                        response_id=response.id,
                        idempotency_key=(
                            f"synthetic-answer-assessment-{index}-{PIPELINE_REVISION}"
                        ),
                    ),
                    report["events"],
                )
            finalization = _retry_stage(
                "finalize_integrity_and_alternatives",
                lambda: harness.finalize(
                    vacancy_id=primary.id,
                    invitation_id=invitation.id,
                    idempotency_key=f"synthetic-finalization-{PIPELINE_REVISION}",
                ),
                report["events"],
            )
            feedback = _retry_stage(
                "candidate_feedback",
                lambda: harness.generate_candidate_feedback(
                    vacancy_id=primary.id,
                    invitation_id=invitation.id,
                    actor_id=ACTOR_ID,
                    idempotency_key=(
                        f"synthetic-candidate-feedback-{PIPELINE_REVISION}"
                    ),
                ),
                report["events"],
            )
            session_view = harness.get_session(
                vacancy_id=primary.id, invitation_id=invitation.id
            )
            report["artifacts"] = [
                artifact.model_dump(mode="json") for artifact in session_view.artifacts
            ]
            artifact_models = [
                db.get(AgentArtifact, artifact.id)
                for artifact in session_view.artifacts
            ]
            resume_model = next(
                item
                for item in artifact_models
                if item is not None and item.kind == "resume_relevance"
            )
            plan_model = next(
                item
                for item in artifact_models
                if item is not None and item.kind == "question_plan"
            )
            assessment_models = [
                item
                for item in artifact_models
                if item is not None and item.kind == "answer_assessment"
            ]
            report["evidence_catalogs"]["candidate_feedback"] = (
                harness._feedback_evidence_catalog(
                    resume_model,
                    plan_model,
                    assessment_models,
                )
            )
            report["candidate_feedback"] = feedback.artifact.model_dump(mode="json")
            profile = finalization.profile.payload
            report["summary"] = (
                f"Профиль построен: readiness={profile['overall_readiness']}, "
                f"coverage={profile['overall_coverage']}, "
                f"strong_pool_eligible={profile['strong_pool_eligible']}. "
                f"Альтернативных совпадений: {len(finalization.alternative_matches)}; "
                f"позиция в рейтинге: "
                f"{finalization.ranking.entries[0].rank if finalization.ranking.entries else 'нет'}. "
                "Черновик обратной связи создан, но не опубликован без проверки человеком."
            )
            report["status"] = "succeeded"
        except Exception as error:
            report["status"] = "failed"
            report["errors"] = _exception_chain(error)
            report["summary"] = "Прогон остановлен; подробности находятся в разделе ошибок."
        finally:
            report["agent_runs"] = _agent_runs(db)
            report["run_statistics"] = {
                "total": len(report["agent_runs"]),
                "succeeded": sum(
                    item["status"] == "succeeded"
                    for item in report["agent_runs"]
                ),
                "invalid_output": sum(
                    item["status"] == "invalid_output"
                    for item in report["agent_runs"]
                ),
                "provider_failed": sum(
                    item["status"] == "provider_failed"
                    for item in report["agent_runs"]
                ),
                "invalid_outputs_with_preserved_payload": sum(
                    item["status"] == "invalid_output"
                    and item["output_payload"] is not None
                    for item in report["agent_runs"]
                ),
            }
            report["resolved_evidence"] = _resolved_evidence_view(report)
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
            _write_report(report)
    engine.dispose()
    print(f"status={report['status']}")
    print(f"report={OUTPUT_PATH}")
    print(f"raw_report={RAW_OUTPUT_PATH}")
    return 0 if report["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
