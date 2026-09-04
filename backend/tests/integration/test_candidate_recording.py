import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.candidate import ConfirmUploadRequest, InvitationView, TranscriptView, UploadGrant, UploadGrantRequest, get_workflow
from app.main import app
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
