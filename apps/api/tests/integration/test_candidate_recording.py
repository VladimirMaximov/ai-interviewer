import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.candidate import (
    CandidateQuestion,
    CodeAnswerRequest,
    ConfirmUploadRequest,
    FollowUpQuestionView,
    InvitationView,
    MonitoringEvidenceGrant,
    MonitoringEventView,
    ResponseSegmentView,
    TranscriptView,
    UploadGrant,
    UploadGrantRequest,
    get_workflow,
)
from app.interview_config import QuestionKind
from app.main import app
from app.domain.proctoring import MonitoringEventKind, MonitoringReviewStatus
from app.domain.interview_runtime import PresenterFallback, PresenterState, PresenterStatus
from app.models.interview import FollowUpStatus, TranscriptionStatus


class Workflow:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.response_id = uuid4()
        self.follow_up_id = uuid4()

    def resolve(self, secret: str):
        return InvitationView(session_id=self.session_id, consented=False, questions=[CandidateQuestion(id=uuid4(), text="Синтетический вопрос", kind=QuestionKind.SPOKEN)]) if secret == "valid" else None

    def consent(self, secret: str):
        return InvitationView(session_id=self.session_id, consented=True, questions=[CandidateQuestion(id=uuid4(), text="Синтетический вопрос", kind=QuestionKind.SPOKEN)]) if secret == "valid" else None

    def create_upload_grant(self, secret: str, request: UploadGrantRequest):
        if secret != "valid":
            return None
        return UploadGrant(response_id=self.response_id, storage_key="responses/test.webm", upload_url="https://storage/upload")

    def confirm_upload(self, secret: str, request: ConfirmUploadRequest):
        return TranscriptView(status=TranscriptionStatus.PROCESSING) if secret == "valid" else None

    def transcript(self, secret: str, response_id):
        if secret != "valid":
            return None
        return TranscriptView(status=TranscriptionStatus.COMPLETED, text="Синтетический ответ")

    def create_monitoring_evidence_grant(self, secret: str, request):
        if secret != "valid" or request.response_id != self.response_id:
            return None
        return MonitoringEvidenceGrant(
            client_event_id=request.client_event_id,
            upload_url="https://storage/monitoring-upload",
        )

    def record_monitoring_event(self, secret: str, request):
        if secret != "valid" or request.response_id != self.response_id:
            return None
        return MonitoringEventView(
            id=request.client_event_id,
            kind=request.kind,
            started_at_ms=request.started_at_ms,
            ended_at_ms=request.ended_at_ms,
            review_status=MonitoringReviewStatus.PENDING,
        )

    def follow_up_questions(self, secret: str):
        if secret != "valid":
            return None
        return [FollowUpQuestionView(
            id=self.follow_up_id,
            source_response_id=self.response_id,
            text="Что было результатом проекта?",
            status=FollowUpStatus.PRESENTED,
        )]

    def avatar_video_url(self, secret: str, question_id):
        if secret != "valid":
            return None
        return "https://storage/private-avatar.mp4"

    def presenter_state(self, secret: str, question_id):
        if secret != "valid":
            return None
        return PresenterState(
            question_id=question_id,
            status=PresenterStatus.READY,
            audio_url="https://storage/private-question.wav",
            avatar_url="https://storage/private-avatar.mp4",
            static_portrait_url="/candidate/valid/avatar-frame/idle",
            fallback=PresenterFallback.NONE,
        )

    def save_code_answer(self, secret: str, request: CodeAnswerRequest):
        if secret != "valid" or not request.source_code.strip():
            return None
        return ResponseSegmentView(
            response_id=self.response_id,
            status=TranscriptionStatus.COMPLETED,
        )


class CandidateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = Workflow()
        app.dependency_overrides[get_workflow] = lambda: self.workflow
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_valid_link_can_consent_request_upload_and_read_transcript(self) -> None:
        self.assertEqual(self.client.get("/candidate/valid").status_code, 200)
        self.assertTrue(self.client.post("/candidate/valid/consent").json()["consented"])
        grant = self.client.post("/candidate/valid/upload-grants", json={"question_id": str(uuid4()), "content_type": "audio/webm"})
        self.assertEqual(grant.status_code, 200)
        confirmation = self.client.post("/candidate/valid/responses/confirm", json={"response_id": str(self.workflow.response_id), "checksum": "a" * 64})
        self.assertEqual(confirmation.json()["status"], "processing")
        transcript = self.client.get(f"/candidate/valid/responses/{self.workflow.response_id}/transcript")
        self.assertEqual(transcript.json()["text"], "Синтетический ответ")

    def test_invalid_link_reveals_no_details(self) -> None:
        response = self.client.get("/candidate/not-a-real-secret")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("secret", response.json()["detail"].lower())

    def test_browser_can_save_bounded_face_event_for_response(self) -> None:
        question_id = uuid4()
        event_id = uuid4()
        grant = self.client.post(
            "/candidate/valid/monitoring-evidence-grants",
            json={
                "client_event_id": str(event_id),
                "response_id": str(self.workflow.response_id),
                "question_id": str(question_id),
                "content_type": "video/webm",
            },
        )
        self.assertEqual(grant.status_code, 200)
        event = self.client.post(
            "/candidate/valid/monitoring-events",
            json={
                "client_event_id": str(event_id),
                "response_id": str(self.workflow.response_id),
                "question_id": str(question_id),
                "kind": MonitoringEventKind.FACE_MISSING,
                "started_at_ms": 5_000,
                "ended_at_ms": 9_000,
                "detector_name": "mediapipe_face_detector",
                "detector_version": "face_presence_v1",
            },
        )
        self.assertEqual(event.status_code, 200)
        self.assertEqual(event.json()["review_status"], "pending")

    def test_browser_event_rejects_reversed_interval(self) -> None:
        response = self.client.post(
            "/candidate/valid/monitoring-events",
            json={
                "client_event_id": str(uuid4()),
                "response_id": str(self.workflow.response_id),
                "question_id": str(uuid4()),
                "kind": "face_missing",
                "started_at_ms": 9_000,
                "ended_at_ms": 5_000,
                "detector_name": "mediapipe_face_detector",
                "detector_version": "face_presence_v1",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_candidate_can_read_ready_follow_up_without_waiting(self) -> None:
        response = self.client.get("/candidate/valid/follow-ups")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["source_response_id"], str(self.workflow.response_id))
        self.assertEqual(response.json()[0]["status"], "presented")

    def test_candidate_can_save_code_with_its_recording_offsets(self) -> None:
        response = self.client.post("/candidate/valid/code-answers", json={
            "question_id": str(uuid4()),
            "language": "Python",
            "source_code": "def solve():\n    return 42",
            "start_offset_ms": 1_000,
            "end_offset_ms": 8_000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")

    def test_candidate_avatar_is_a_token_scoped_temporary_redirect(self) -> None:
        question_id = uuid4()
        response = self.client.get(
            f"/candidate/valid/questions/{question_id}/avatar",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "https://storage/private-avatar.mp4")
        self.assertEqual(
            self.client.get(
                f"/candidate/not-a-real-secret/questions/{question_id}/avatar",
                follow_redirects=False,
            ).status_code,
            404,
        )

    def test_candidate_presenter_state_contains_only_scoped_media(self) -> None:
        question_id = uuid4()
        response = self.client.get(
            f"/candidate/valid/questions/{question_id}/presenter"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")
        self.assertEqual(response.json()["question_id"], str(question_id))
        self.assertEqual(
            self.client.get(
                f"/candidate/not-a-real-secret/questions/{question_id}/presenter"
            ).status_code,
            404,
        )
