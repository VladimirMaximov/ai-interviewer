import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # Registers foreign-key target tables.
from app.models.interview import Base, CandidateResponse, CodeAnswer, InterviewFollowUpQuestion, InterviewInvitation, InterviewSession, RuntimeEvaluationJob, RuntimeEvaluationStatus, TranscriptionStatus
from app.services.runtime_evaluation import RuntimeEvaluationDecision, RuntimeEvaluationService


class TwoPromptEvaluator:
    def evaluate(self, request):
        return RuntimeEvaluationDecision(confidence=0.7, follow_up_questions=["Уточните архитектуру.", "Какие были ограничения?"])


class MalformedEvaluator:
    def evaluate(self, request):
        return type("Decision", (), {"confidence": None, "follow_up_questions": ["a", "b", "c"]})()


class RuntimeEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.sessions = sessionmaker(bind=engine)

    def _response(self, *, kind: str = "spoken"):
        question_id = uuid4()
        config = {"live_coding_enabled": kind == "coding", "blocks": [{"id": str(uuid4()), "title": "Тест", "topic": "test", "questions": [{"id": str(question_id), "text": "Опишите решение.", "kind": kind, "follow_up_after_answer": True}]}]}
        with self.sessions() as db:
            invitation = InterviewInvitation(token_digest="a" * 64, expires_at=datetime.now(timezone.utc) + timedelta(days=1), question_config=config)
            db.add(invitation)
            db.flush()
            session = InterviewSession(invitation_id=invitation.id)
            db.add(session)
            db.flush()
            response = CandidateResponse(session_id=session.id, question_id=question_id, storage_key=None, content_type="text/plain" if kind == "coding" else "video/webm", checksum="", transcription_status=TranscriptionStatus.COMPLETED, transcript_text="Голосовое объяснение" if kind == "coding" else "Голосовой ответ", start_offset_ms=1_000, end_offset_ms=9_000)
            db.add(response)
            db.flush()
            if kind == "coding":
                db.add(CodeAnswer(response_id=response.id, language="Python", source_code="return 42", start_offset_ms=1_000, end_offset_ms=9_000, saved_at=datetime.now(timezone.utc)))
            response_id = response.id
            db.commit()
        return response_id

    def test_creates_at_most_two_prompts_and_only_one_job(self) -> None:
        response_id = self._response()
        service = RuntimeEvaluationService(self.sessions, TwoPromptEvaluator())
        service.evaluate_completed_response(response_id)
        service.evaluate_completed_response(response_id)
        with self.sessions() as db:
            jobs = list(db.scalars(select(RuntimeEvaluationJob)))
            prompts = list(db.scalars(select(InterviewFollowUpQuestion)))
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].status, RuntimeEvaluationStatus.COMPLETED)
        self.assertEqual(len(prompts), 2)

    def test_coding_answer_is_sent_as_text(self) -> None:
        response_id = self._response(kind="coding")
        service = RuntimeEvaluationService(self.sessions, TwoPromptEvaluator())
        service.evaluate_completed_response(response_id)
        with self.sessions() as db:
            job = db.scalar(select(RuntimeEvaluationJob))
        self.assertEqual(job.spoken_text, "Голосовое объяснение")
        self.assertEqual(job.source_code, "return 42")
        self.assertEqual(job.language, "Python")
        self.assertEqual(job.status, RuntimeEvaluationStatus.COMPLETED)

    def test_malformed_decision_fails_without_creating_prompts(self) -> None:
        response_id = self._response()
        RuntimeEvaluationService(self.sessions, MalformedEvaluator()).evaluate_completed_response(response_id)
        with self.sessions() as db:
            job = db.scalar(select(RuntimeEvaluationJob))
            prompts = list(db.scalars(select(InterviewFollowUpQuestion)))
        self.assertEqual(job.status, RuntimeEvaluationStatus.FAILED)
        self.assertEqual(prompts, [])
