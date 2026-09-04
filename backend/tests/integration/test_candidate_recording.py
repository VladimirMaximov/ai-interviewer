import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.candidate import (
    ConfirmUploadRequest,
    InvitationView,
    MonitoringEvidenceGrant,
    MonitoringEventView,
    TranscriptView,
    UploadGrant,
    UploadGrantRequest,
    get_workflow,
)
from app.main import app
from app.domain.proctoring import MonitoringEventKind, MonitoringReviewStatus
from app.models.interview import TranscriptionStatus


class Workflow:
    def __init__(self) -> None:
        self.session_id = uuid4()
        self.response_id = uuid4()

    def resolve(self, secret: str):
        return InvitationView(session_id=self.session_id, consented=False) if secret == "valid" else None

    def consent(self, secret: str):
        return InvitationView(session_id=self.session_id, consented=True) if secret == "valid" else None

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
