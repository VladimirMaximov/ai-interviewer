from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from interview_platform.application.role_services import RoleService
from interview_platform.application.services import InterviewService
from interview_platform.infrastructure.sqlite_repository import SQLiteInterviewRepository
from interview_platform.infrastructure.sqlite_role_repository import SQLiteRoleReviewRepository
from interview_platform.infrastructure.video_stub import TextCaptureStub
from interview_platform.web.app import create_app


class WebTests(unittest.TestCase):
    manager_key = "manager-test-secret"
    recruiter_key = "recruiter-test-secret"
    manager_id = "engineering-manager"

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        database = Path(self.directory.name) / "web.sqlite3"
        self.repository = SQLiteInterviewRepository(database)
        self.role_repository = SQLiteRoleReviewRepository(database)
        self.capture = TextCaptureStub()
        self.service = InterviewService(self.repository, self.capture)
        self.roles = RoleService(self.service, self.role_repository)
        self.app = create_app(
            self.service,
            self.capture,
            manager_key=self.manager_key,
            recruiter_key=self.recruiter_key,
            manager_id=self.manager_id,
            roles=self.roles,
        )
        self.token = "web-test-invitation-token-value-000001"
        self.created = self.service.create_interview(
            candidate_alias="synthetic-web",
            position_title="Python Developer",
            questions=[{"prompt": "How do you choose storage?", "required": True}],
            invitation_token=self.token,
        )

    def tearDown(self) -> None:
        self.role_repository.close()
        self.repository.close()
        self.directory.cleanup()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_data=None,
        form_data=None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        environ: dict = {}
        setup_testing_defaults(environ)
        environ.update(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "HTTP_HOST": "testserver",
                "wsgi.url_scheme": "http",
            }
        )
        if json_data is not None:
            body = json.dumps(json_data).encode("utf-8")
            environ["CONTENT_TYPE"] = "application/json"
        elif form_data is not None:
            body = urlencode(form_data).encode("utf-8")
            environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
        else:
            body = b""
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input"] = io.BytesIO(body)
        for name, value in (headers or {}).items():
            environ["HTTP_" + name.upper().replace("-", "_")] = value
        captured = {}

        def start_response(status, response_headers):
            captured["status"] = status
            captured["headers"] = dict(response_headers)

        response_body = b"".join(self.app(environ, start_response))
        return int(captured["status"].split()[0]), captured["headers"], response_body

    @property
    def manager_headers(self) -> dict[str, str]:
        return {"X-Manager-Key": self.manager_key}

    @property
    def recruiter_headers(self) -> dict[str, str]:
        return {"X-Recruiter-Key": self.recruiter_key}

    def basic_headers(self, role: str) -> dict[str, str]:
        key = self.manager_key if role == "manager" else self.recruiter_key
        value = base64.b64encode(f"{role}:{key}".encode()).decode()
        return {"Authorization": f"Basic {value}"}

    def _submit_candidate(self) -> tuple[str, str]:
        question_id = self.created.interview.questions[0].id
        self.service.start_interview(self.token, consent=True)
        answer = "I compare transaction needs and operational cost before choosing storage."
        self.service.save_answer(self.token, question_id=question_id, content=answer)
        self.service.complete_interview(self.token)
        return question_id, answer

    def _recruiter_review(self, *, publish: bool) -> dict:
        question_id, _ = self._submit_candidate()
        return {
            "candidate_summary": "Good trade-off analysis",
            "strengths": ["Considers operations"],
            "risks": ["Needs more scale evidence"],
            "next_steps": "Discuss incidents with the team.",
            "internal_notes": "Recruiter-only secret note",
            "recruiter_decision": "advance",
            "assigned_manager": self.manager_id,
            "evidence": [
                {
                    "kind": "answer_excerpt",
                    "question_id": question_id,
                    "excerpt": "transaction needs",
                    "note": "Direct evidence from the stored answer",
                }
            ],
            "publish": publish,
        }

    def test_landing_and_candidate_journey(self) -> None:
        status, _, body = self.request("GET", "/")
        self.assertEqual(200, status)
        self.assertIn(b"/recruiter", body)
        self.assertIn(b"/manager", body)

        candidate_path = f"/api/candidate/interviews/{self.token}"
        status, _, body = self.request("GET", candidate_path)
        self.assertEqual(200, status)
        self.assertEqual("text_stub", json.loads(body)["capture"]["kind"])

        status, _, _ = self.request(
            "POST", candidate_path + "/start", json_data={"consent": True}
        )
        self.assertEqual(200, status)
        question_id = self.created.interview.questions[0].id
        status, _, body = self.request(
            "PUT",
            candidate_path + f"/answers/{question_id}",
            json_data={"content": "A saved answer"},
        )
        self.assertEqual("A saved answer", json.loads(body)["questions"][0]["answer"])
        status, _, body = self.request("POST", candidate_path + "/complete")
        self.assertEqual(200, status)
        self.assertEqual("submitted", json.loads(body)["status"])

    def test_html_posts_require_same_origin(self) -> None:
        path = f"/candidate/{self.token}/start"
        status, _, _ = self.request("POST", path, form_data={"consent": "yes"})
        self.assertEqual(403, status)
        status, headers, _ = self.request(
            "POST",
            path,
            form_data={"consent": "yes"},
            headers={"Origin": "http://testserver"},
        )
        self.assertEqual(303, status)
        self.assertEqual(f"/candidate/{self.token}", headers["Location"])

    def test_role_credentials_are_isolated(self) -> None:
        status, _, _ = self.request("GET", "/recruiter")
        self.assertEqual(401, status)
        status, _, _ = self.request(
            "GET", "/recruiter", headers=self.basic_headers("manager")
        )
        self.assertEqual(401, status)
        status, _, body = self.request(
            "GET", "/recruiter", headers=self.basic_headers("recruiter")
        )
        self.assertEqual(200, status)
        self.assertIn(b"synthetic-web", body)

        status, _, _ = self.request(
            "GET", "/api/recruiter/interviews", headers=self.manager_headers
        )
        self.assertEqual(401, status)
        status, _, body = self.request(
            "GET", "/api/manager/interviews", headers=self.manager_headers
        )
        self.assertEqual(200, status)
        self.assertEqual([], json.loads(body)["interviews"])

    def test_only_recruiter_can_create_invitation(self) -> None:
        request_data = {
            "candidate_alias": "synthetic-new",
            "position_title": "Backend Developer",
            "questions": [{"prompt": "Explain retries", "required": True}],
        }
        status, _, _ = self.request(
            "POST",
            "/api/manager/interviews",
            headers=self.manager_headers,
            json_data=request_data,
        )
        self.assertEqual(405, status)

        status, _, body = self.request(
            "POST",
            "/api/recruiter/interviews",
            headers=self.recruiter_headers,
            json_data=request_data,
        )
        payload = json.loads(body)
        self.assertEqual(201, status)
        self.assertIn(payload["invitation_token"], payload["candidate_url"])

    def test_recruiter_assignment_and_manager_decision_are_separate(self) -> None:
        review_data = self._recruiter_review(publish=False)
        interview_id = self.created.interview.id

        status, _, body = self.request(
            "PUT",
            f"/api/recruiter/interviews/{interview_id}/review",
            headers=self.recruiter_headers,
            json_data=review_data,
        )
        self.assertEqual(200, status)
        self.assertEqual("advance", json.loads(body)["recruiter_decision"])

        status, _, body = self.request(
            "GET", "/api/manager/interviews", headers=self.manager_headers
        )
        self.assertEqual(200, status)
        self.assertEqual(
            [interview_id], [item["id"] for item in json.loads(body)["interviews"]]
        )

        status, _, body = self.request(
            "PUT",
            f"/api/manager/interviews/{interview_id}/decision",
            headers=self.manager_headers,
            json_data={"manager_decision": "hold", "notes": "Need system-design depth."},
        )
        self.assertEqual(200, status)
        self.assertEqual("hold", json.loads(body)["manager_decision"])

        _, _, body = self.request(
            "GET",
            f"/api/recruiter/interviews/{interview_id}",
            headers=self.recruiter_headers,
        )
        payload = json.loads(body)
        self.assertEqual("advance", payload["recruiter_review"]["recruiter_decision"])
        self.assertEqual("hold", payload["manager_review"]["manager_decision"])

    def test_draft_hidden_and_published_feedback_is_candidate_safe(self) -> None:
        feedback = self._recruiter_review(publish=False)
        interview_id = self.created.interview.id
        self.request(
            "PUT",
            f"/api/recruiter/interviews/{interview_id}/review",
            headers=self.recruiter_headers,
            json_data=feedback,
        )
        _, _, body = self.request("GET", f"/api/candidate/interviews/{self.token}")
        self.assertIsNone(json.loads(body)["feedback"])

        feedback["publish"] = True
        status, _, _ = self.request(
            "PUT",
            f"/api/recruiter/interviews/{interview_id}/review",
            headers=self.recruiter_headers,
            json_data=feedback,
        )
        self.assertEqual(200, status)
        _, _, body = self.request("GET", f"/api/candidate/interviews/{self.token}")
        payload = json.loads(body)
        serialized = body.decode("utf-8")
        self.assertEqual("Good trade-off analysis", payload["feedback"]["candidate_summary"])
        self.assertNotIn("Recruiter-only secret note", serialized)
        self.assertNotIn("recruiter_decision", serialized)
        self.assertNotIn("risks", serialized)
        self.assertNotIn("manager_review", serialized)

    def test_unassigned_interview_is_not_disclosed_to_manager(self) -> None:
        status, _, _ = self.request(
            "GET",
            f"/api/manager/interviews/{self.created.interview.id}",
            headers=self.manager_headers,
        )
        self.assertEqual(404, status)

    def test_malformed_json_returns_safe_validation_error(self) -> None:
        environ: dict = {}
        setup_testing_defaults(environ)
        environ.update(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": "/api/recruiter/interviews",
                "HTTP_HOST": "testserver",
                "HTTP_X_RECRUITER_KEY": self.recruiter_key,
                "CONTENT_TYPE": "application/json",
                "CONTENT_LENGTH": "1",
                "wsgi.input": io.BytesIO(b"{"),
            }
        )
        captured = {}
        body = b"".join(
            self.app(environ, lambda status, headers: captured.update(status=status))
        )
        self.assertTrue(captured["status"].startswith("422"))
        self.assertEqual("validation_error", json.loads(body)["error"]["code"])


if __name__ == "__main__":
    unittest.main()
