"""Run the architecture POC with an optional synthetic interview."""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from wsgiref.simple_server import make_server
from wsgiref.simple_server import WSGIRequestHandler

from interview_platform.application.assessment_services import AssessmentService
from interview_platform.application.feedback_services import FeedbackService
from interview_platform.application.hiring_services import HiringServices
from interview_platform.application.ranking_services import DecisionService, RankingService
from interview_platform.application.role_services import RoleService
from interview_platform.application.services import InterviewService, token_digest
from interview_platform.application.vacancy_services import VacancyService
from interview_platform.config import Settings
from interview_platform.domain.competencies import load_framework
from interview_platform.domain.models import InterviewStatus
from interview_platform.infrastructure.evaluation_stubs import DeterministicEvidenceEvaluator
from interview_platform.infrastructure.sqlite_hiring_repository import SQLiteHiringRepository
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.sqlite_role_repository import SQLiteRoleReviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub
from interview_platform.web.app import create_app


DEMO_TOKEN = "synthetic-demo-invitation-token-000001"
VACANCY_DEMO_TOKENS = (
    "synthetic-vacancy-candidate-token-000001",
    "synthetic-vacancy-candidate-token-000002",
    "synthetic-vacancy-candidate-token-000003",
)
DEMO_QUESTIONS = [
    {
        "prompt": "Расскажите о технически сложной задаче и вашей роли в её решении.",
        "required": True,
    },
    {
        "prompt": "Как вы проверяете качество и надёжность Python-кода?",
        "required": True,
    },
    {
        "prompt": "Какие данные вам нужны, чтобы принять архитектурное решение?",
        "required": True,
    },
]


class RedactingRequestHandler(WSGIRequestHandler):
    """Keep bearer invitation tokens out of local access logs."""

    def log_message(self, format: str, *args) -> None:
        safe_args = tuple(
            re.sub(r"(/candidate/(?:interviews/)?)[^/\s?]+", r"\1[REDACTED]", str(value))
            for value in args
        )
        super().log_message(format, *safe_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AI Interviewer architecture POC")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-path", default="interview-platform.sqlite3")
    parser.add_argument("--manager-key", help="Overrides INTERVIEW_MANAGER_KEY")
    parser.add_argument("--recruiter-key", help="Overrides INTERVIEW_RECRUITER_KEY")
    parser.add_argument(
        "--manager-id",
        help="Manager assignment id (defaults to INTERVIEW_MANAGER_ID or hiring-manager)",
    )
    parser.add_argument("--seed-demo", action="store_true", help="Create an idempotent synthetic interview")
    parser.add_argument(
        "--seed-vacancy-assessment-demo",
        action="store_true",
        help="Create an idempotent vacancy, approved context, and three assessed candidates",
    )
    return parser


def seed_demo(service: InterviewService, repository: SQLiteInterviewRepository) -> str:
    if repository.get_by_token_digest(token_digest(DEMO_TOKEN)) is None:
        service.create_interview(
            candidate_alias="synthetic-candidate-001",
            position_title="Python Developer · architecture POC",
            questions=DEMO_QUESTIONS,
            invitation_token=DEMO_TOKEN,
        )
    return DEMO_TOKEN


def build_hiring_services(
    settings: Settings,
    repository: SQLiteHiringRepository,
    interviews: InterviewService,
) -> HiringServices:
    framework_path = Path(__file__).with_name("data") / "competency_framework.v1.json"
    vacancies = VacancyService(
        repository,
        load_framework(framework_path),
        max_context_bytes=settings.max_context_bytes,
        max_context_chars=settings.max_context_chars,
        minimum_evidence_coverage=settings.minimum_evidence_coverage,
        interview_service=interviews,
    )
    return HiringServices(
        vacancies=vacancies,
        assessments=AssessmentService(
            repository,
            interviews,
            DeterministicEvidenceEvaluator(),
        ),
        rankings=RankingService(repository, interviews),
        decisions=DecisionService(repository, interviews),
        feedback=FeedbackService(repository, interviews),
    )


def seed_vacancy_assessment_demo(
    hiring: HiringServices,
    interview_repository: SQLiteInterviewRepository,
) -> dict:
    vacancy = next(
        (
            item
            for item in hiring.vacancies.list_vacancies()
            if item["title"] == "Python Developer · vacancy-aware demo"
        ),
        None,
    )
    if vacancy is None:
        vacancy = hiring.vacancies.create_vacancy(
            title="Python Developer · vacancy-aware demo",
            role_key="software_engineer",
            target_level_key="middle",
            owner_actor_id="synthetic-manager",
        )
    sources = hiring.vacancies.list_context_sources(vacancy["id"])
    if not sources:
        sources = [
            hiring.vacancies.add_context_source(
                vacancy["id"],
                source_type="pasted_text",
                display_name="Synthetic hiring-manager brief",
                text=(
                    "Нужен опыт безопасной эволюции API без остановки клиентов. "
                    "Важно объяснять технические компромиссы через измеримый результат."
                ),
                actor_id="synthetic-manager",
            )
        ]
    vacancy = hiring.vacancies.get_vacancy(vacancy["id"])
    if vacancy.get("active_profile_version_id"):
        profile = hiring.vacancies.get_profile(vacancy["active_profile_version_id"])
    else:
        profile = hiring.vacancies.draft_profile(
            vacancy["id"],
            source_ids=[item["id"] for item in sources],
            actor_id="synthetic-manager",
        )
        profile = hiring.vacancies.approve_profile(
            vacancy["id"], profile["id"], actor_id="synthetic-manager"
        )
    snapshots = hiring.vacancies.list_snapshots(vacancy["id"])
    snapshot = next(
        (item for item in snapshots if item["profile_version_id"] == profile["id"]),
        None,
    )
    if snapshot is None:
        snapshot = hiring.vacancies.create_snapshot(
            vacancy["id"], profile_id=profile["id"]
        )

    runs = []
    interview_ids = []
    for index, token in enumerate(VACANCY_DEMO_TOKENS, start=1):
        interview = interview_repository.get_by_token_digest(token_digest(token))
        if interview is None:
            created = hiring.vacancies.create_interview(
                vacancy["id"],
                snapshot_id=snapshot["id"],
                candidate_alias=f"synthetic-vacancy-candidate-{index:03d}",
                invitation_token=token,
            )
            interview = created["interview"]
        interview_ids.append(interview.id)
        if interview.status is InterviewStatus.INVITED:
            interview = hiring.vacancies.interview_service.start_interview(token, consent=True)
        if interview.status is InterviewStatus.IN_PROGRESS:
            for question in interview.questions:
                if question.id not in interview.answers:
                    hiring.vacancies.interview_service.save_answer(
                        token,
                        question_id=question.id,
                        content=(
                            "В синтетическом проекте я описал ситуацию, личное действие, "
                            f"компромисс {index} и проверил результат по метрикам после запуска."
                        ),
                    )
            interview = hiring.vacancies.interview_service.complete_interview(token)
        runs.append(
            hiring.assessments.create_run(
                interview.id,
                reason="initial",
                idempotency_key=f"synthetic-assessment-run-{index:03d}",
            )
        )
    ranking = hiring.rankings.create_snapshot(
        vacancy["id"],
        assessment_run_ids=[item["id"] for item in runs],
        idempotency_key="synthetic-ranking-snapshot-001",
    )
    return {
        "vacancy": vacancy,
        "profile": profile,
        "snapshot": snapshot,
        "interview_ids": interview_ids,
        "assessment_run_ids": [item["id"] for item in runs],
        "ranking_snapshot_id": ranking["id"],
        "tokens": VACANCY_DEMO_TOKENS,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = Settings.from_values(
            manager_key=args.manager_key,
            recruiter_key=args.recruiter_key,
            manager_id=args.manager_id,
            db_path=args.db_path,
            host=args.host,
            port=args.port,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    database_parent = Path(settings.db_path).expanduser().resolve().parent
    database_parent.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInterviewRepository(settings.db_path)
    hiring_repository = SQLiteHiringRepository(settings.db_path)
    role_repository = SQLiteRoleReviewRepository(settings.db_path)
    capture = TextCaptureStub()
    service = InterviewService(repository, capture)
    hiring = build_hiring_services(settings, hiring_repository, service)
    roles = RoleService(service, role_repository)
    demo_token = seed_demo(service, repository) if args.seed_demo else None
    vacancy_demo = (
        seed_vacancy_assessment_demo(hiring, repository)
        if args.seed_vacancy_assessment_demo
        else None
    )
    app = create_app(
        service,
        capture,
        manager_key=settings.manager_key,
        recruiter_key=settings.recruiter_key,
        manager_id=settings.manager_id,
        roles=roles,
        hiring=hiring,
    )
    base_url = f"http://{settings.host}:{settings.port}"

    print(f"Portal selector: {base_url}/")
    print(f"Recruiter portal: {base_url}/recruiter (user: recruiter)")
    print(f"Manager portal: {base_url}/manager (user: manager, id: {settings.manager_id})")
    if demo_token:
        print(f"Synthetic candidate: {base_url}/candidate/{demo_token}")
    if vacancy_demo:
        print(f"Synthetic vacancy: {base_url}/manager/vacancies/{vacancy_demo['vacancy']['id']}")
        for index, token in enumerate(vacancy_demo["tokens"], start=1):
            print(f"Synthetic vacancy candidate {index}: {base_url}/candidate/{token}")
        print(f"Assessment context: {vacancy_demo['snapshot']['id']}")
        print(f"Ranking snapshot: {vacancy_demo['ranking_snapshot_id']}")
    print("Video capture: text_stub (no camera, audio, or biometric analysis)")

    try:
        with make_server(
            settings.host,
            settings.port,
            app,
            handler_class=RedactingRequestHandler,
        ) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        role_repository.close()
        hiring_repository.close()
        repository.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
