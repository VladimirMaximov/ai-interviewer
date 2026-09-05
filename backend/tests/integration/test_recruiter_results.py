import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
import app.models.multi_agent  # noqa: F401
from app.api.hiring_context import get_interview_results_service, require_recruiter
from app.domain.hiring_context import VacancyStatus
from app.main import app
from app.models.hiring_context import Vacancy
from app.models.interview import (
    Base, CandidateResponse, CodeAnswer, InterviewInvitation, InterviewRecording,
    InterviewRecordingChunk, InterviewSession, InvitationStatus, TranscriptionStatus,
)
from app.services.interview_results import InterviewResultsService


class Storage:
    def create_download_url(self, key: str) -> str:
        return f"https://private.invalid/{key}"


class RecruiterResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine); self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        now = datetime.now(timezone.utc); question_id = uuid4()
        config = {"schema_version": 1, "live_coding_enabled": True, "blocks": [
            {"id": str(uuid4()), "key": "hard_skills", "title": "Hard skills", "topic": "hard_skills", "questions": [{"id": str(question_id), "text": "Напишите функцию", "kind": "coding", "language": "python"}]},
            {"id": str(uuid4()), "key": "soft_skills", "title": "Soft skills", "topic": "soft_skills", "questions": []},
            {"id": str(uuid4()), "key": "work_experience", "title": "Опыт", "topic": "work_experience", "questions": []},
        ]}
        with self.sessions() as db:
            vacancy = Vacancy(title="Python", source_filename="v.txt", media_type="text/plain", byte_size=1, extracted_text="x", content_hash="a" * 64, status=VacancyStatus.ACTIVE, created_by="r", idempotency_key="results-test", created_at=now, interview_config=config, interview_config_revision=1)
            db.add(vacancy); db.flush()
            invitation = InterviewInvitation(token_digest="b" * 64, vacancy_id=vacancy.id, candidate_alias="Synthetic", created_by="r", expires_at=now + timedelta(days=1), status=InvitationStatus.ACTIVE, question_config=config, follow_up_after_all_answers=False)
            db.add(invitation); db.flush()
            session = InterviewSession(invitation_id=invitation.id, consented_at=now, submitted_at=now); db.add(session); db.flush()
            response = CandidateResponse(session_id=session.id, question_id=question_id, storage_key=None, content_type="video/webm", checksum="", transcription_status=TranscriptionStatus.COMPLETED, transcript_text="Я объясняю решение", created_at=now, start_offset_ms=0, end_offset_ms=10_000, timed_out=False)
            db.add(response); db.flush()
            db.add(CodeAnswer(response_id=response.id, language="python", source_code="return 42", start_offset_ms=0, end_offset_ms=10_000, saved_at=now))
            recording = InterviewRecording(session_id=session.id, storage_key=f"recordings/{session.id}/x", content_type="video/webm", checksum="c", started_at=now, ended_at=now, duration_ms=10_000); db.add(recording); db.flush()
            db.add(InterviewRecordingChunk(recording_id=recording.id, sequence=0, storage_key=f"{recording.storage_key}/chunks/000000.webm", content_type="video/webm", start_offset_ms=0, end_offset_ms=10_000, checksum="d", uploaded_at=now)); db.commit()
            self.vacancy_id, self.session_id = vacancy.id, session.id
        app.dependency_overrides[require_recruiter] = lambda: "recruiter"
        app.dependency_overrides[get_interview_results_service] = lambda: InterviewResultsService(self.sessions(), Storage())
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear(); self.engine.dispose()

    def test_lists_real_session_without_inventing_score(self) -> None:
        response = self.client.get(f"/recruiter/vacancies/{self.vacancy_id}/interviews")
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["interviews"][0]
        self.assertEqual(item["status"], "completed")
        self.assertIsNone(item["score"])

    def test_detail_aligns_transcript_code_and_signed_chunk(self) -> None:
        response = self.client.get(f"/recruiter/vacancies/{self.vacancy_id}/interviews/{self.session_id}")
        self.assertEqual(response.status_code, 200, response.text)
        detail = response.json()
        self.assertEqual(detail["answers"][0]["transcript_text"], "Я объясняю решение")
        self.assertEqual(detail["answers"][0]["code"]["source_code"], "return 42")
        self.assertTrue(detail["media"][0]["url"].startswith("https://private.invalid/"))


if __name__ == "__main__": unittest.main()
