from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.candidate import (
    MonitoringEvidenceGrantRequest,
    MonitoringEventRequest,
    UploadGrantRequest,
)
from app.models.interview import (
    Base,
    InterviewInvitation,
    InterviewMonitoringEvent,
    InterviewSession,
)
from app.security.invitations import digest_invitation_secret
from app.services.candidate_workflow import SqlCandidateWorkflow


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, int] = {}

    def create_upload_url(self, key: str, content_type: str) -> str:
        return f"https://storage.invalid/{key}?type={content_type}"

    def object_exists(self, key: str) -> bool:
        return key in self.objects

    def object_size(self, key: str) -> int:
        return self.objects[key]

    def download_to(self, key: str, destination: Path) -> None:
        raise AssertionError("download is not expected")


class CandidateWorkflowMonitoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite://")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(self.engine, expire_on_commit=False)()
        self.storage = FakeStorage()
        self.secret = "synthetic-secret"
        now = datetime.now(timezone.utc)
        invitation = InterviewInvitation(
            token_digest=digest_invitation_secret(self.secret),
            expires_at=now + timedelta(hours=1),
        )
        self.db.add(invitation)
        self.db.flush()
        self.db.add(
            InterviewSession(invitation_id=invitation.id, consented_at=now)
        )
        self.db.commit()
        self.workflow = SqlCandidateWorkflow(self.db, self.storage)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_face_event_is_idempotent_and_uses_server_owned_object_key(self) -> None:
        question_id = uuid4()
        event_id = uuid4()
        response = self.workflow.create_upload_grant(
            self.secret,
            UploadGrantRequest(
                question_id=question_id, content_type="audio/webm"
            ),
        )
        evidence_request = MonitoringEvidenceGrantRequest(
            client_event_id=event_id,
            response_id=response.response_id,
            question_id=question_id,
            content_type="video/webm",
        )

        evidence_grant = self.workflow.create_monitoring_evidence_grant(
            self.secret, evidence_request
        )
        expected_key = evidence_grant.upload_url.removeprefix(
            "https://storage.invalid/"
        ).split("?", maxsplit=1)[0]
        self.assertEqual(
            expected_key,
            f"monitoring/{self.workflow.resolve(self.secret).session_id}/{event_id}.webm",
        )
        self.storage.objects[expected_key] = 128_000
        request = MonitoringEventRequest(
            client_event_id=event_id,
            response_id=response.response_id,
            question_id=question_id,
            kind="face_missing",
            started_at_ms=1_000,
            ended_at_ms=7_000,
            detector_name="mediapipe_face_detector",
            detector_version="face_presence_v1",
            evidence_content_type="video/webm",
            evidence_checksum="a" * 64,
        )

        first = self.workflow.record_monitoring_event(self.secret, request)
        second = self.workflow.record_monitoring_event(self.secret, request)

        self.assertEqual(first.id, event_id)
        self.assertEqual(second.id, event_id)
        self.assertEqual(
            self.db.scalar(select(func.count(InterviewMonitoringEvent.id))), 1
        )

        oversized_event_id = uuid4()
        oversized_key = (
            f"monitoring/{self.workflow.resolve(self.secret).session_id}/"
            f"{oversized_event_id}.webm"
        )
        self.storage.objects[oversized_key] = 2_000_001
        oversized = self.workflow.record_monitoring_event(
            self.secret,
            request.model_copy(
                update={"client_event_id": oversized_event_id}
            ),
        )
        self.assertIsNone(oversized)
        self.assertEqual(
            self.db.scalar(select(func.count(InterviewMonitoringEvent.id))), 1
        )


if __name__ == "__main__":
    unittest.main()
