"""Small WSGI adapter with isolated candidate, recruiter, and manager routes."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import default as email_policy
from http import HTTPStatus
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs

from interview_platform.application.services import InterviewService
from interview_platform.application.hiring_services import HiringServices
from interview_platform.application.role_services import RoleService
from interview_platform.domain.errors import (
    AssessmentOutputError,
    AssessmentProviderError,
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)

from .auth import (
    manager_api_authorized,
    manager_basic_authorized,
    recruiter_api_authorized,
    recruiter_basic_authorized,
    same_origin,
)
from .presenters import (
    assigned_manager_detail_page,
    assigned_manager_list_page,
    candidate_interview,
    candidate_page,
    error_page,
    interview_summary,
    invitation_created_page,
    manager_detail_page,
    manager_interview,
    manager_list_page,
    manager_review_dict,
    portal_landing_page,
    product_overview_page,
    recruiter_detail_page,
    recruiter_list_page,
    recruiter_review_dict,
    staff_interview,
    vacancy_detail_page,
    vacancy_list_page,
)


LOGGER = logging.getLogger(__name__)
MAX_BODY_BYTES = 1_000_000


@dataclass(slots=True)
class Response:
    status: int
    body: bytes
    content_type: str
    headers: list[tuple[str, str]] = field(default_factory=list)


class HTTPError(Exception):
    def __init__(self, status: int, message: str, code: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class InterviewWebApp:
    def __init__(
        self,
        service: InterviewService,
        capture,
        *,
        manager_key: str,
        recruiter_key: str | None = None,
        manager_id: str = "hiring-manager",
        roles: RoleService | None = None,
        hiring: HiringServices | None = None,
    ) -> None:
        self.service = service
        self.capture = capture
        self.manager_key = manager_key
        self.recruiter_key = recruiter_key
        self.manager_id = manager_id
        self.roles = roles
        self.hiring = hiring
        self.styles_path = Path(__file__).with_name("static") / "styles.css"

    def __call__(self, environ: dict, start_response: Callable):
        is_api = str(environ.get("PATH_INFO", "")).startswith("/api/") or (
            environ.get("PATH_INFO") == "/health"
        )
        try:
            response = self._dispatch(environ)
        except DomainError as exc:
            status = 422
            if isinstance(exc, NotFoundError):
                status = 404
            elif isinstance(exc, ConflictError):
                status = 409
            elif isinstance(exc, AssessmentOutputError):
                status = 502
            elif isinstance(exc, AssessmentProviderError):
                status = 503
            response = self._error_response(status, exc.code, exc.message, exc.details, is_api)
        except HTTPError as exc:
            response = self._error_response(exc.status, exc.code, exc.message, {}, is_api)
        except Exception:
            LOGGER.exception("Unhandled interview platform request failure")
            response = self._error_response(
                500,
                "internal_error",
                "Внутренняя ошибка. Попробуйте ещё раз.",
                {},
                is_api,
            )

        status_line = f"{response.status} {HTTPStatus(response.status).phrase}"
        headers = [
            ("Content-Type", response.content_type),
            ("Content-Length", str(len(response.body))),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            (
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'",
            ),
        ] + response.headers
        start_response(status_line, headers)
        return [response.body]

    def _dispatch(self, environ: dict) -> Response:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))

        if method == "GET" and path == "/health":
            return self._json(200, {"status": "ok"})
        if method == "GET" and path == "/static/styles.css":
            return Response(200, self.styles_path.read_bytes(), "text/css; charset=utf-8")
        if method == "GET" and path == "/static/product.css":
            return Response(
                200,
                self.styles_path.with_name("product.css").read_bytes(),
                "text/css; charset=utf-8",
            )
        if method == "GET" and path == "/":
            return self._html(200, portal_landing_page())
        if method == "GET" and path in {"/product", "/product/"}:
            return self._html(200, product_overview_page())

        if path.startswith("/api/recruiter/"):
            if self.recruiter_key is None or not recruiter_api_authorized(
                environ, self.recruiter_key
            ):
                raise HTTPError(401, "recruiter authorization required", "unauthorized")
            return self._recruiter_api(environ, method, path)
        if path.startswith("/api/manager/"):
            if not manager_api_authorized(environ, self.manager_key):
                raise HTTPError(401, "manager authorization required", "unauthorized")
            return self._manager_api(environ, method, path)
        if path.startswith("/api/candidate/"):
            return self._candidate_api(environ, method, path)
        if path == "/manager" or path.startswith("/manager/"):
            if not manager_basic_authorized(environ, self.manager_key):
                return Response(
                    401,
                    b"Manager authorization required",
                    "text/plain; charset=utf-8",
                    [("WWW-Authenticate", 'Basic realm="Interview manager", charset="UTF-8"')],
                )
            if method == "POST" and not same_origin(environ):
                raise HTTPError(403, "same-origin form submission required", "forbidden")
            return self._manager_html(environ, method, path)
        if path == "/recruiter" or path.startswith("/recruiter/"):
            if self.recruiter_key is None or not recruiter_basic_authorized(
                environ, self.recruiter_key
            ):
                return Response(
                    401,
                    b"Recruiter authorization required",
                    "text/plain; charset=utf-8",
                    [("WWW-Authenticate", 'Basic realm="Interview recruiter", charset="UTF-8"')],
                )
            if method == "POST" and not same_origin(environ):
                raise HTTPError(403, "same-origin form submission required", "forbidden")
            return self._recruiter_html(environ, method, path)
        if path.startswith("/candidate/"):
            if method == "POST" and not same_origin(environ):
                raise HTTPError(403, "same-origin form submission required", "forbidden")
            return self._candidate_html(environ, method, path)
        raise NotFoundError("page not found")

    def _recruiter_api(self, environ: dict, method: str, path: str) -> Response:
        roles = self._require_roles()
        if path == "/api/recruiter/interviews" and method == "GET":
            interviews = []
            for interview in roles.list_for_recruiter():
                recruiter_review = roles.recruiter_review(interview.id)
                manager_review = roles.reviews.get_manager_review(interview.id)
                interviews.append(staff_interview(interview, recruiter_review, manager_review))
            return self._json(200, {"interviews": interviews})
        if path == "/api/recruiter/interviews" and method == "POST":
            data = self._json_body(environ)
            created = self.service.create_interview(
                candidate_alias=self._string(data, "candidate_alias"),
                position_title=self._string(data, "position_title"),
                questions=data.get("questions"),
            )
            return self._json(
                201,
                {
                    "interview": staff_interview(created.interview, None, None),
                    "invitation_token": created.invitation_token,
                    "candidate_url": self._absolute_url(
                        environ, f"/candidate/{created.invitation_token}"
                    ),
                },
            )

        match = re.fullmatch(r"/api/recruiter/interviews/([^/]+)", path)
        if match and method == "GET":
            interview = roles.get_for_recruiter(match.group(1))
            review = roles.recruiter_review(interview.id)
            manager_review = roles.reviews.get_manager_review(interview.id)
            return self._json(200, staff_interview(interview, review, manager_review))

        match = re.fullmatch(r"/api/recruiter/interviews/([^/]+)/review", path)
        if match and method == "PUT":
            review = self._save_recruiter_review_from_data(
                match.group(1), self._json_body(environ)
            )
            return self._json(200, recruiter_review_dict(review))
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _candidate_api(self, environ: dict, method: str, path: str) -> Response:
        match = re.fullmatch(r"/api/candidate/interviews/([^/]+)/feedback-timeline", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(200, hiring.feedback.candidate_timeline(match.group(1)))

        match = re.fullmatch(r"/api/candidate/interviews/([^/]+)", path)
        if match and method == "GET":
            interview = self.service.get_candidate_interview(match.group(1))
            return self._json(200, self._candidate_payload(interview, match.group(1)))

        match = re.fullmatch(r"/api/candidate/interviews/([^/]+)/start", path)
        if match and method == "POST":
            data = self._json_body(environ)
            interview = self.service.start_interview(match.group(1), consent=data.get("consent") is True)
            return self._json(200, self._candidate_payload(interview, match.group(1)))

        match = re.fullmatch(r"/api/candidate/interviews/([^/]+)/answers/([^/]+)", path)
        if match and method == "PUT":
            data = self._json_body(environ)
            if not isinstance(data.get("content"), str):
                raise ValidationError("content must be a string", details={"field": "content"})
            interview = self.service.save_answer(
                match.group(1),
                question_id=match.group(2),
                content=data["content"],
            )
            return self._json(200, self._candidate_payload(interview, match.group(1)))

        match = re.fullmatch(r"/api/candidate/interviews/([^/]+)/complete", path)
        if match and method == "POST":
            interview = self.service.complete_interview(match.group(1))
            return self._json(200, self._candidate_payload(interview, match.group(1)))
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _manager_api(self, environ: dict, method: str, path: str) -> Response:
        hiring = self.hiring
        assigned_match = re.fullmatch(r"/api/manager/interviews/([^/]+)(?:/.*)?", path)
        if self.roles is not None and assigned_match:
            self.roles.get_for_manager(assigned_match.group(1), self.manager_id)
            if method in {"POST", "PUT"} and re.fullmatch(
                r"/api/manager/interviews/[^/]+/(?:decisions|feedback-entries(?:/.*)?)",
                path,
            ):
                raise HTTPError(
                    405,
                    "manager review uses the separate decision endpoint",
                    "method_not_allowed",
                )
        if path == "/api/manager/competency-frameworks/current" and method == "GET":
            hiring = self._require_hiring()
            query = parse_qs(str(environ.get("QUERY_STRING", "")))
            return self._json(
                200,
                hiring.vacancies.get_framework(
                    query.get("role_key", [None])[-1],
                    query.get("level_key", [None])[-1],
                ),
            )
        if path == "/api/manager/vacancies" and method == "GET":
            hiring = self._require_hiring()
            return self._json(200, {"vacancies": hiring.vacancies.list_vacancies()})
        if path == "/api/manager/vacancies" and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            role_key = data.get("role_key", data.get("role_profile_id"))
            return self._json(
                201,
                hiring.vacancies.create_vacancy(
                    title=self._string(data, "title"),
                    role_key=self._required_value(role_key, "role_key"),
                    target_level_key=self._string(data, "target_level_key"),
                    owner_actor_id=self._string(data, "owner_actor_id"),
                ),
            )

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(200, hiring.vacancies.get_vacancy(match.group(1)))

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)/context-sources", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            content_type = str(environ.get("CONTENT_TYPE", ""))
            if content_type.startswith("multipart/form-data"):
                source = self._multipart_source(environ)
            else:
                data = self._json_body(environ)
                source = {
                    "source_type": self._string(data, "source_type"),
                    "display_name": self._string(data, "display_name"),
                    "text": self._string(data, "text"),
                    "media_type": None,
                }
            result = hiring.vacancies.add_context_source(
                match.group(1),
                actor_id=self._actor_id(environ),
                **source,
            )
            return self._json(201, result)

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)/profile-drafts", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            source_ids = data.get("context_source_ids")
            if not isinstance(source_ids, list):
                raise ValidationError("context_source_ids must be a list")
            return self._json(
                201,
                hiring.vacancies.draft_profile(
                    match.group(1),
                    source_ids=source_ids,
                    actor_id=self._actor_id(environ),
                    idempotency_key=self._idempotency_key(environ),
                ),
            )

        profile_match = re.fullmatch(
            r"/api/manager/vacancies/([^/]+)/profile-versions/([^/]+)", path
        )
        if profile_match and method == "GET":
            hiring = self._require_hiring()
            profile = hiring.vacancies.get_profile(profile_match.group(2))
            if profile["vacancy_id"] != profile_match.group(1):
                raise NotFoundError("vacancy profile not found")
            return self._json(200, profile)
        if profile_match and method == "PUT":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            criteria = data.get("criteria")
            if not isinstance(criteria, list):
                raise ValidationError("criteria must be a list")
            result = hiring.vacancies.update_profile(
                profile_match.group(2),
                summary=self._string(data, "summary"),
                criteria=criteria,
                actor_id=self._actor_id(environ),
            )
            return self._json(200, result)

        match = re.fullmatch(
            r"/api/manager/vacancies/([^/]+)/profile-versions/([^/]+)/approve", path
        )
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            if data.get("confirm_no_automatic_rejection") is not True:
                raise ValidationError("confirm_no_automatic_rejection must be true")
            return self._json(
                200,
                hiring.vacancies.approve_profile(
                    match.group(1),
                    match.group(2),
                    actor_id=self._actor_id(environ),
                    idempotency_key=self._idempotency_key(environ),
                ),
            )

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)/assessment-contexts", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            profile_id = data.get(
                "profile_version_id", data.get("vacancy_profile_version_id")
            )
            return self._json(
                201,
                hiring.vacancies.create_snapshot(
                    match.group(1),
                    profile_id=profile_id,
                    idempotency_key=self._idempotency_key(environ),
                ),
            )

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)/interviews", path)
        if match and method == "POST":
            if self.roles is not None:
                raise HTTPError(
                    405,
                    "only recruiters can create interview invitations",
                    "method_not_allowed",
                )
            hiring = self._require_hiring()
            data = self._json_body(environ)
            snapshot_id = data.get(
                "snapshot_id", data.get("assessment_context_snapshot_id")
            )
            created = hiring.vacancies.create_interview(
                match.group(1),
                snapshot_id=self._required_value(snapshot_id, "snapshot_id"),
                candidate_alias=self._string(data, "candidate_alias"),
            )
            return self._json(
                201,
                {
                    "interview_id": created["interview"].id,
                    "vacancy_id": created["vacancy_id"],
                    "assessment_context_snapshot_id": created[
                        "assessment_context_snapshot_id"
                    ],
                    "invitation_token": created["invitation_token"],
                    "candidate_url": self._absolute_url(
                        environ, f"/candidate/{created['invitation_token']}"
                    ),
                },
            )

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)/assessment-runs", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(
                200, {"assessment_runs": hiring.assessments.list_runs(match.group(1))}
            )
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            result = hiring.assessments.create_run(
                match.group(1),
                reason=self._string(data, "reason"),
                idempotency_key=self._idempotency_key(environ),
            )
            return self._json(202, result)

        match = re.fullmatch(
            r"/api/manager/interviews/([^/]+)/assessment-runs/([^/]+)", path
        )
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(200, hiring.assessments.get_run(*match.groups()))

        match = re.fullmatch(r"/api/manager/vacancies/([^/]+)/ranking-snapshots", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            run_ids = data.get("assessment_run_ids")
            if not isinstance(run_ids, list):
                raise ValidationError("assessment_run_ids must be a list")
            result = hiring.rankings.create_snapshot(
                match.group(1),
                assessment_run_ids=run_ids,
                idempotency_key=self._idempotency_key(environ),
            )
            return self._json(201, result)

        match = re.fullmatch(
            r"/api/manager/vacancies/([^/]+)/ranking-snapshots/([^/]+)", path
        )
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(200, hiring.rankings.get_snapshot(*match.groups()))

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)/decisions", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(
                200, {"decisions": hiring.decisions.list_decisions(match.group(1))}
            )
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            result = hiring.decisions.create_decision(
                match.group(1),
                actor_id=self._actor_id(environ),
                actor_role=self._string(data, "actor_role"),
                decision=self._string(data, "decision"),
                reason=self._string(data, "reason"),
                idempotency_key=self._idempotency_key(environ),
                evidence_reference_ids=data.get("evidence_reference_ids"),
                supersedes_decision_id=data.get("supersedes_decision_id"),
            )
            return self._json(201, result)

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)/feedback-entries", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            return self._json(
                200, {"feedback_entries": hiring.feedback.list_entries(match.group(1))}
            )
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            source_run_id = data.get("source_assessment_run_id")
            if source_run_id and data.get("source_kind") == "ai_assisted":
                result = hiring.feedback.create_preliminary_draft(
                    match.group(1),
                    source_run_id,
                    idempotency_key=self._idempotency_key(environ),
                )
            else:
                result = hiring.feedback.create_entry(
                    match.group(1),
                    actor_id=self._actor_id(environ),
                    idempotency_key=self._idempotency_key(environ),
                    **self._feedback_content(data, include_stage=True),
                )
            return self._json(201, result)

        match = re.fullmatch(
            r"/api/manager/interviews/([^/]+)/feedback-entries/([^/]+)/revisions", path
        )
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._json_body(environ)
            result = hiring.feedback.add_revision(
                match.group(1),
                match.group(2),
                actor_id=self._actor_id(environ),
                content=self._feedback_content(data),
            )
            return self._json(201, result["revisions"][-1])

        match = re.fullmatch(
            r"/api/manager/interviews/([^/]+)/feedback-entries/([^/]+)/revisions/([^/]+)/publish",
            path,
        )
        if match and method == "POST":
            hiring = self._require_hiring()
            result = hiring.feedback.publish_revision(
                match.group(1),
                match.group(2),
                match.group(3),
                actor_id=self._actor_id(environ),
            )
            revision = next(
                item for item in result["revisions"] if item["id"] == match.group(3)
            )
            return self._json(200, revision)

        if path == "/api/manager/interviews" and method == "GET":
            if self.roles is not None:
                return self._json(
                    200,
                    {
                        "interviews": [
                            staff_interview(
                                item,
                                self.roles.recruiter_review(item.id),
                                self.roles.manager_review(item.id, self.manager_id),
                            )
                            for item in self.roles.list_for_manager(self.manager_id)
                        ]
                    },
                )
            return self._json(
                200,
                {"interviews": [interview_summary(item) for item in self.service.list_interviews()]},
            )
        if path == "/api/manager/interviews" and method == "POST":
            if self.roles is not None:
                raise HTTPError(
                    405,
                    "only recruiters can create interview invitations",
                    "method_not_allowed",
                )
            data = self._json_body(environ)
            created = self.service.create_interview(
                candidate_alias=self._string(data, "candidate_alias"),
                position_title=self._string(data, "position_title"),
                questions=data.get("questions"),
            )
            candidate_url = self._absolute_url(
                environ,
                f"/candidate/{created.invitation_token}",
            )
            return self._json(
                201,
                {
                    "interview": interview_summary(created.interview),
                    "invitation_token": created.invitation_token,
                    "candidate_url": candidate_url,
                },
            )

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)", path)
        if match and method == "GET":
            if self.roles is not None:
                interview = self.roles.get_for_manager(match.group(1), self.manager_id)
                return self._json(
                    200,
                    staff_interview(
                        interview,
                        self.roles.recruiter_review(interview.id),
                        self.roles.manager_review(interview.id, self.manager_id),
                    ),
                )
            return self._json(200, manager_interview(self.service.get_manager_interview(match.group(1))))

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)/decision", path)
        if match and method == "PUT" and self.roles is not None:
            data = self._json_body(environ)
            review = self.roles.save_manager_review(
                match.group(1),
                self.manager_id,
                manager_decision=self._string(data, "manager_decision"),
                notes=self._string(data, "notes"),
            )
            return self._json(200, manager_review_dict(review))

        match = re.fullmatch(r"/api/manager/interviews/([^/]+)/feedback", path)
        if match and method == "PUT" and self.roles is None:
            data = self._json_body(environ)
            interview = self._save_feedback_from_data(match.group(1), data)
            return self._json(200, manager_interview(interview)["feedback"])
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _candidate_html(self, environ: dict, method: str, path: str) -> Response:
        match = re.fullmatch(r"/candidate/([^/]+)", path)
        if match and method == "GET":
            token = match.group(1)
            timeline = None
            if self.hiring is not None:
                timeline = self.hiring.feedback.candidate_timeline(token)
            published_feedback = None
            if self.roles is not None:
                published_feedback = self.roles.candidate_feedback(token)
            return self._html(
                200,
                candidate_page(
                    self.service.get_candidate_interview(token),
                    token,
                    self.capture,
                    timeline=timeline,
                    published_feedback=published_feedback,
                    role_feedback_enabled=self.roles is not None,
                ),
            )

        match = re.fullmatch(r"/candidate/([^/]+)/start", path)
        if match and method == "POST":
            data = self._form_body(environ)
            self.service.start_interview(match.group(1), consent=data.get("consent") == "yes")
            return self._redirect(f"/candidate/{match.group(1)}")

        match = re.fullmatch(r"/candidate/([^/]+)/answers/([^/]+)", path)
        if match and method == "POST":
            data = self._form_body(environ)
            self.service.save_answer(
                match.group(1),
                question_id=match.group(2),
                content=data.get("content", ""),
            )
            return self._redirect(f"/candidate/{match.group(1)}")

        match = re.fullmatch(r"/candidate/([^/]+)/complete", path)
        if match and method == "POST":
            self.service.complete_interview(match.group(1))
            return self._redirect(f"/candidate/{match.group(1)}")
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _recruiter_html(self, environ: dict, method: str, path: str) -> Response:
        roles = self._require_roles()
        if path == "/recruiter" and method == "GET":
            interviews = roles.list_for_recruiter()
            reviews = {
                item.id: review
                for item in interviews
                if (review := roles.recruiter_review(item.id)) is not None
            }
            return self._html(200, recruiter_list_page(interviews, reviews))
        if path == "/recruiter/interviews" and method == "POST":
            data = self._form_body(environ)
            questions = [
                {"prompt": line.strip(), "required": True}
                for line in data.get("questions", "").splitlines()
                if line.strip()
            ]
            created = self.service.create_interview(
                candidate_alias=data.get("candidate_alias", ""),
                position_title=data.get("position_title", ""),
                questions=questions,
            )
            candidate_url = self._absolute_url(
                environ, f"/candidate/{created.invitation_token}"
            )
            return self._html(
                201, invitation_created_page(candidate_url, portal="recruiter")
            )

        match = re.fullmatch(r"/recruiter/interviews/([^/]+)", path)
        if match and method == "GET":
            interview = roles.get_for_recruiter(match.group(1))
            return self._html(
                200,
                recruiter_detail_page(
                    interview,
                    roles.recruiter_review(interview.id),
                    roles.reviews.get_manager_review(interview.id),
                    self.manager_id,
                ),
            )

        match = re.fullmatch(r"/recruiter/interviews/([^/]+)/review", path)
        if match and method == "POST":
            data = self._form_body(environ)
            evidence_kind = data.get("evidence_kind", "")
            self._save_recruiter_review_from_data(
                match.group(1),
                {
                    "candidate_summary": data.get("candidate_summary", ""),
                    "strengths": self._lines(data.get("strengths", "")),
                    "risks": self._lines(data.get("risks", "")),
                    "next_steps": data.get("next_steps", ""),
                    "internal_notes": data.get("internal_notes", ""),
                    "recruiter_decision": data.get("recruiter_decision", ""),
                    "assigned_manager": data.get("assigned_manager", ""),
                    "evidence": [
                        {
                            "kind": evidence_kind,
                            "question_id": data.get("question_id", ""),
                            "excerpt": (
                                data.get("excerpt", "")
                                if evidence_kind == "answer_excerpt"
                                else None
                            ),
                            "note": data.get("evidence_note", ""),
                        }
                    ],
                    "publish": data.get("publish") == "yes",
                },
            )
            return self._redirect(f"/recruiter/interviews/{match.group(1)}")
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _manager_html(self, environ: dict, method: str, path: str) -> Response:
        if path == "/manager" and method == "GET":
            if self.roles is not None:
                return self._html(
                    200,
                    assigned_manager_list_page(
                        self.roles.list_for_manager(self.manager_id), self.manager_id
                    ),
                )
            return self._html(200, manager_list_page(self.service.list_interviews()))

        assigned_match = re.fullmatch(r"/manager/interviews/([^/]+)(?:/.*)?", path)
        if self.roles is not None and assigned_match:
            interview = self.roles.get_for_manager(
                assigned_match.group(1), self.manager_id
            )
            if path == f"/manager/interviews/{interview.id}" and method == "GET":
                return self._html(
                    200,
                    assigned_manager_detail_page(
                        interview,
                        self.roles.recruiter_review(interview.id),
                        self.roles.manager_review(interview.id, self.manager_id),
                    ),
                )
            if path == f"/manager/interviews/{interview.id}/decision" and method == "POST":
                data = self._form_body(environ)
                self.roles.save_manager_review(
                    interview.id,
                    self.manager_id,
                    manager_decision=data.get("manager_decision", ""),
                    notes=data.get("notes", ""),
                )
                return self._redirect(f"/manager/interviews/{interview.id}")
            if method == "POST" and re.fullmatch(
                r"/manager/interviews/[^/]+/(?:decisions|feedback-entries)", path
            ):
                raise HTTPError(
                    405,
                    "manager review uses the separate decision form",
                    "method_not_allowed",
                )
        if path == "/manager/vacancies" and method == "GET":
            hiring = self._require_hiring()
            return self._html(
                200,
                vacancy_list_page(
                    hiring.vacancies.list_vacancies(),
                    hiring.vacancies.get_framework(),
                ),
            )
        if path == "/manager/vacancies" and method == "POST":
            hiring = self._require_hiring()
            data = self._form_body(environ)
            role_key, separator, level_key = data.get("role_level", "").partition(":")
            if not separator:
                raise ValidationError("role and level selection is required")
            vacancy = hiring.vacancies.create_vacancy(
                title=data.get("title", ""),
                role_key=role_key,
                target_level_key=level_key,
                owner_actor_id="manager-browser",
            )
            return self._redirect(f"/manager/vacancies/{vacancy['id']}")

        match = re.fullmatch(r"/manager/vacancies/([^/]+)", path)
        if match and method == "GET":
            hiring = self._require_hiring()
            vacancy_id = match.group(1)
            vacancy = hiring.vacancies.get_vacancy(vacancy_id)
            profiles = hiring.vacancies.repository.list_profiles(vacancy_id)
            assignments = hiring.vacancies.repository.list_assignments(vacancy_id)
            return self._html(
                200,
                vacancy_detail_page(
                    vacancy,
                    hiring.vacancies.list_context_sources(vacancy_id),
                    profiles,
                    hiring.vacancies.list_snapshots(vacancy_id),
                    assignments,
                    hiring.rankings.list_snapshots(vacancy_id),
                    can_invite=self.roles is None,
                ),
            )

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/sources", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            if str(environ.get("CONTENT_TYPE", "")).startswith("multipart/form-data"):
                hiring.vacancies.add_context_source(
                    match.group(1),
                    actor_id="manager-browser",
                    **self._multipart_source(environ),
                )
            else:
                data = self._form_body(environ)
                hiring.vacancies.add_context_source(
                    match.group(1),
                    source_type=data.get("source_type", "phrase"),
                    display_name=data.get("display_name", "manager brief"),
                    text=data.get("text", ""),
                    actor_id="manager-browser",
                )
            return self._redirect(f"/manager/vacancies/{match.group(1)}")

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/draft", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            source_ids = [
                item["id"] for item in hiring.vacancies.list_context_sources(match.group(1))
            ]
            hiring.vacancies.draft_profile(
                match.group(1), source_ids=source_ids, actor_id="manager-browser"
            )
            return self._redirect(f"/manager/vacancies/{match.group(1)}")

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/profiles/([^/]+)/approve", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            hiring.vacancies.approve_profile(
                match.group(1), match.group(2), actor_id="manager-browser"
            )
            return self._redirect(f"/manager/vacancies/{match.group(1)}")

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/snapshot", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            hiring.vacancies.create_snapshot(match.group(1))
            return self._redirect(f"/manager/vacancies/{match.group(1)}")

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/interviews", path)
        if match and method == "POST":
            if self.roles is not None:
                raise HTTPError(
                    405,
                    "only recruiters can create interview invitations",
                    "method_not_allowed",
                )
            hiring = self._require_hiring()
            data = self._form_body(environ)
            created = hiring.vacancies.create_interview(
                match.group(1),
                snapshot_id=data.get("snapshot_id", ""),
                candidate_alias=data.get("candidate_alias", ""),
            )
            candidate_url = self._absolute_url(
                environ, f"/candidate/{created['invitation_token']}"
            )
            return self._html(201, invitation_created_page(candidate_url))

        match = re.fullmatch(r"/manager/vacancies/([^/]+)/ranking", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._form_body(environ)
            context_snapshot_id = data.get("context_snapshot_id", "")
            run_ids = []
            for assignment in hiring.vacancies.repository.list_assignments(match.group(1)):
                if assignment["context_snapshot_id"] != context_snapshot_id:
                    continue
                runs = hiring.assessments.list_runs(assignment["interview_id"])
                completed = [item for item in runs if item["status"] == "completed"]
                if completed:
                    run_ids.append(completed[-1]["id"])
            result = hiring.rankings.create_snapshot(
                match.group(1),
                assessment_run_ids=run_ids,
                idempotency_key=(
                    f"browser-ranking-{match.group(1)}-{context_snapshot_id}-{len(run_ids)}"
                ),
            )
            return self._redirect(
                f"/manager/vacancies/{match.group(1)}#ranking-{result['id']}"
            )
        if path == "/manager/interviews" and method == "POST":
            if self.roles is not None:
                raise HTTPError(
                    405,
                    "only recruiters can create interview invitations",
                    "method_not_allowed",
                )
            data = self._form_body(environ)
            questions = [
                {"prompt": line.strip(), "required": True}
                for line in data.get("questions", "").splitlines()
                if line.strip()
            ]
            created = self.service.create_interview(
                candidate_alias=data.get("candidate_alias", ""),
                position_title=data.get("position_title", ""),
                questions=questions,
            )
            candidate_url = self._absolute_url(environ, f"/candidate/{created.invitation_token}")
            return self._html(201, invitation_created_page(candidate_url))

        match = re.fullmatch(r"/manager/interviews/([^/]+)", path)
        if match and method == "GET" and self.roles is None:
            interview = self.service.get_manager_interview(match.group(1))
            assessment_runs = []
            decisions = []
            feedback_entries = []
            vacancy_aware = False
            if self.hiring is not None:
                assignment = self.hiring.vacancies.repository.get_assignment(interview.id)
                if assignment is not None:
                    vacancy_aware = True
                    assessment_runs = self.hiring.assessments.list_runs(interview.id)
                    decisions = self.hiring.decisions.list_decisions(interview.id)
                    feedback_entries = self.hiring.feedback.list_entries(interview.id)
            return self._html(
                200,
                manager_detail_page(
                    interview,
                    vacancy_aware=vacancy_aware,
                    assessment_runs=assessment_runs,
                    decisions=decisions,
                    feedback_entries=feedback_entries,
                ),
            )

        match = re.fullmatch(r"/manager/interviews/([^/]+)/assessment-runs", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            previous = hiring.assessments.list_runs(match.group(1))
            hiring.assessments.create_run(
                match.group(1),
                reason="initial" if not previous else "manual_retry",
                idempotency_key=f"browser-assessment-{match.group(1)}-{len(previous) + 1}",
            )
            return self._redirect(f"/manager/interviews/{match.group(1)}")

        match = re.fullmatch(r"/manager/interviews/([^/]+)/decisions", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._form_body(environ)
            previous = hiring.decisions.list_decisions(match.group(1))
            hiring.decisions.create_decision(
                match.group(1),
                actor_id="manager-browser",
                actor_role=data.get("actor_role", "hiring_manager"),
                decision=data.get("decision", "hold"),
                reason=data.get("reason", ""),
                idempotency_key=f"browser-decision-{match.group(1)}-{len(previous) + 1}",
            )
            return self._redirect(f"/manager/interviews/{match.group(1)}")

        match = re.fullmatch(r"/manager/interviews/([^/]+)/feedback-entries", path)
        if match and method == "POST":
            hiring = self._require_hiring()
            data = self._form_body(environ)
            entry = hiring.feedback.create_entry(
                match.group(1),
                stage=data.get("stage", "post_human_review"),
                source_kind="human_authored",
                actor_id="manager-browser",
                assessment_scope=self._lines(data.get("assessment_scope", "")),
                strengths=self._lines(data.get("strengths", "")),
                growth_areas=self._lines(data.get("growth_areas", "")),
                evidence_gaps=self._lines(data.get("evidence_gaps", "")),
                limitations=self._lines(data.get("limitations", "")),
                next_steps=data.get("next_steps", ""),
                internal_notes=data.get("internal_notes", ""),
                assessment_evidence_ids=[],
            )
            if data.get("publish") == "yes":
                hiring.feedback.publish_revision(
                    match.group(1),
                    entry["id"],
                    entry["revisions"][0]["id"],
                    actor_id="manager-browser",
                )
            return self._redirect(f"/manager/interviews/{match.group(1)}")

        match = re.fullmatch(r"/manager/interviews/([^/]+)/feedback", path)
        if match and method == "POST" and self.roles is None:
            data = self._form_body(environ)
            evidence_kind = data.get("evidence_kind", "")
            interview = self.service.save_feedback(
                match.group(1),
                candidate_summary=data.get("candidate_summary", ""),
                strengths=self._lines(data.get("strengths", "")),
                risks=self._lines(data.get("risks", "")),
                next_steps=data.get("next_steps", ""),
                internal_notes=data.get("internal_notes", ""),
                manager_decision=data.get("manager_decision", ""),
                evidence=[
                    {
                        "kind": evidence_kind,
                        "question_id": data.get("question_id", ""),
                        "excerpt": data.get("excerpt", "")
                        if evidence_kind == "answer_excerpt"
                        else None,
                        "note": data.get("evidence_note", ""),
                    }
                ],
                publish=data.get("publish") == "yes",
            )
            return self._redirect(f"/manager/interviews/{interview.id}")
        self._method_or_not_found(path)
        raise AssertionError("unreachable")

    def _save_feedback_from_data(self, interview_id: str, data: dict):
        strengths = data.get("strengths")
        risks = data.get("risks")
        evidence = data.get("evidence")
        if not isinstance(strengths, list) or not isinstance(risks, list):
            raise ValidationError("strengths and risks must be lists")
        return self.service.save_feedback(
            interview_id,
            candidate_summary=self._string(data, "candidate_summary"),
            strengths=strengths,
            risks=risks,
            next_steps=self._string(data, "next_steps"),
            internal_notes=self._string(data, "internal_notes", required=False),
            manager_decision=self._string(data, "manager_decision"),
            evidence=evidence,
            publish=data.get("publish"),
        )

    def _save_recruiter_review_from_data(self, interview_id: str, data: dict):
        strengths = data.get("strengths")
        risks = data.get("risks")
        evidence = data.get("evidence")
        if not isinstance(strengths, list) or not isinstance(risks, list):
            raise ValidationError("strengths and risks must be lists")
        if not isinstance(evidence, list):
            raise ValidationError("evidence must be a list")
        return self._require_roles().save_recruiter_review(
            interview_id,
            candidate_summary=self._string(data, "candidate_summary"),
            strengths=strengths,
            risks=risks,
            next_steps=self._string(data, "next_steps"),
            internal_notes=self._string(data, "internal_notes", required=False),
            recruiter_decision=self._string(data, "recruiter_decision"),
            assigned_manager=data.get("assigned_manager"),
            evidence=evidence,
            publish=data.get("publish"),
        )

    def _candidate_payload(self, interview, token: str) -> dict:
        payload = candidate_interview(interview, self.capture)
        if self.roles is not None:
            payload["feedback"] = self.roles.candidate_feedback(token)
        return payload

    @staticmethod
    def _string(data: dict, field: str, *, required: bool = True) -> str:
        value = data.get(field, "")
        if not isinstance(value, str) or (required and not value.strip()):
            raise ValidationError(f"{field} must be a string", details={"field": field})
        return value

    @staticmethod
    def _required_value(value, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{field} must be a string", details={"field": field})
        return value

    def _require_hiring(self) -> HiringServices:
        if self.hiring is None:
            raise NotFoundError("vacancy assessment feature is not configured")
        return self.hiring

    def _require_roles(self) -> RoleService:
        if self.roles is None:
            raise NotFoundError("three-role interview feature is not configured")
        return self.roles

    @staticmethod
    def _actor_id(environ: dict) -> str:
        value = str(environ.get("HTTP_X_ACTOR_ID", "manager-api")).strip()
        return value or "manager-api"

    @staticmethod
    def _idempotency_key(environ: dict) -> str:
        value = str(environ.get("HTTP_IDEMPOTENCY_KEY", "")).strip()
        if len(value) < 8 or len(value) > 128:
            raise ValidationError("Idempotency-Key must contain 8 to 128 characters")
        return value

    @staticmethod
    def _feedback_content(data: dict, *, include_stage: bool = False) -> dict:
        list_fields = (
            "assessment_scope",
            "strengths",
            "growth_areas",
            "evidence_gaps",
            "limitations",
            "assessment_evidence_ids",
        )
        for field in list_fields:
            if field in data and not isinstance(data[field], list):
                raise ValidationError(f"{field} must be a list")
        result = {
            "source_kind": data.get("source_kind", "human_authored"),
            "assessment_scope": data.get("assessment_scope", []),
            "strengths": data.get("strengths", []),
            "growth_areas": data.get("growth_areas", []),
            "evidence_gaps": data.get("evidence_gaps", []),
            "limitations": data.get("limitations", []),
            "next_steps": data.get("next_steps", ""),
            "internal_notes": data.get("internal_notes", ""),
            "assessment_evidence_ids": data.get("assessment_evidence_ids", []),
            "correction_of_revision_id": data.get("correction_of_revision_id"),
        }
        if include_stage:
            result["stage"] = data.get("stage", "post_human_review")
        else:
            result.pop("source_kind")
        return result

    def _multipart_source(self, environ: dict) -> dict:
        content_type = str(environ.get("CONTENT_TYPE", ""))
        body = self._read_body(environ)
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + body
        )
        file_part = next(
            (part for part in message.iter_parts() if part.get_filename()), None
        )
        if file_part is None:
            raise ValidationError("multipart request requires a file")
        return {
            "source_type": "file",
            "display_name": file_part.get_filename() or "context.txt",
            "text": file_part.get_payload(decode=True) or b"",
            "media_type": file_part.get_content_type(),
        }

    @staticmethod
    def _lines(value: str) -> list[str]:
        return [line.strip() for line in value.splitlines() if line.strip()]

    @staticmethod
    def _method_or_not_found(path: str) -> None:
        known_prefixes = ("/api/", "/candidate/", "/manager/", "/recruiter/")
        if path.startswith(known_prefixes):
            raise HTTPError(405, "method not allowed", "method_not_allowed")
        raise NotFoundError("page not found")

    @staticmethod
    def _absolute_url(environ: dict, path: str) -> str:
        return f"{environ.get('wsgi.url_scheme', 'http')}://{environ.get('HTTP_HOST', '127.0.0.1:8000')}{path}"

    @staticmethod
    def _read_body(environ: dict) -> bytes:
        raw_length = environ.get("CONTENT_LENGTH", "0") or "0"
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValidationError("content length is invalid") from exc
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValidationError("request body is too large")
        return environ["wsgi.input"].read(length)

    def _json_body(self, environ: dict) -> dict:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0]
        if content_type != "application/json":
            raise ValidationError("Content-Type must be application/json")
        try:
            data = json.loads(self._read_body(environ).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError("request body must contain valid JSON") from exc
        if not isinstance(data, dict):
            raise ValidationError("request body must be a JSON object")
        return data

    def _form_body(self, environ: dict) -> dict[str, str]:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0]
        if content_type != "application/x-www-form-urlencoded":
            raise ValidationError("form encoding is required")
        try:
            raw = self._read_body(environ).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("form body must be UTF-8") from exc
        return {key: values[-1] for key, values in parse_qs(raw, keep_blank_values=True).items()}

    @staticmethod
    def _json(status: int, payload) -> Response:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return Response(status, body, "application/json; charset=utf-8")

    @staticmethod
    def _html(status: int, body: str) -> Response:
        return Response(status, body.encode("utf-8"), "text/html; charset=utf-8")

    @staticmethod
    def _redirect(location: str) -> Response:
        return Response(303, b"", "text/plain; charset=utf-8", [("Location", location)])

    def _error_response(
        self,
        status: int,
        code: str,
        message: str,
        details: dict,
        is_api: bool,
    ) -> Response:
        if is_api:
            return self._json(status, {"error": {"code": code, "message": message, "details": details}})
        return self._html(status, error_page(message, status))


def create_app(
    service: InterviewService,
    capture,
    *,
    manager_key: str,
    recruiter_key: str | None = None,
    manager_id: str = "hiring-manager",
    roles: RoleService | None = None,
    hiring: HiringServices | None = None,
) -> InterviewWebApp:
    return InterviewWebApp(
        service,
        capture,
        manager_key=manager_key,
        recruiter_key=recruiter_key,
        manager_id=manager_id,
        roles=roles,
        hiring=hiring,
    )
