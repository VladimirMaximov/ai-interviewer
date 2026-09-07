from datetime import datetime, timezone
import unittest
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.hiring_context  # noqa: F401
import app.models.manager_brief  # noqa: F401
from app.domain.hiring_context import (
    CandidateConsentRequiredError,
    HiringContextConflictError,
    HiringContextNotFoundError,
    ResumeUploaderRole,
)
from app.models.interview import (
    CandidateResponse,
    InterviewSession,
    TranscriptionStatus,
)
from app.models.interview import Base
from app.services.hiring_context import HiringContextService


class HiringContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(self.engine, expire_on_commit=False)()
        self.service = HiringContextService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _vacancy(self, key: str = "vacancy-key-001"):
        return self.service.create_vacancy(
            title="Backend developer",
            document=b"Python, FastAPI, PostgreSQL",
            filename="vacancy.txt",
            media_type="text/plain",
            actor_id="recruiter-test",
            idempotency_key=key,
        )

    def test_resume_is_versioned_matched_and_idempotent_after_consent(self) -> None:
        vacancy = self._vacancy()
        invitation = self.service.create_invitation(
            vacancy_id=vacancy.id,
            actor_id="recruiter-test",
            candidate_alias="synthetic-candidate",
            expires_in_hours=24,
        )
        with self.assertRaises(CandidateConsentRequiredError):
            self.service.upload_resume(
                secret=invitation.candidate_token,
                document=b"Python for five years",
                filename="resume.txt",
                media_type="text/plain",
                idempotency_key="resume-key-001",
            )

        self.db.add(
            InterviewSession(
                invitation_id=invitation.invitation_id,
                consented_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        first = self.service.upload_resume(
            secret=invitation.candidate_token,
            document=b"Python for five years",
            filename="resume.txt",
            media_type="text/plain",
            idempotency_key="resume-key-001",
        )
        replay = self.service.upload_resume(
            secret=invitation.candidate_token,
            document=b"Python for five years",
            filename="renamed.txt",
            media_type="text/plain",
            idempotency_key="resume-key-001",
        )
        with self.assertRaises(HiringContextConflictError):
            self.service.upload_resume(
                secret=invitation.candidate_token,
                document=b"Different content",
                filename="resume.txt",
                media_type="text/plain",
                idempotency_key="resume-key-001",
            )
        second = self.service.upload_resume(
            secret=invitation.candidate_token,
            document=b"Python and PostgreSQL for five years",
            filename="resume-v2.txt",
            media_type="text/plain",
            idempotency_key="resume-key-002",
        )

        self.assertIsNotNone(first)
        self.assertEqual(first.uploaded_by_role, ResumeUploaderRole.CANDIDATE)
        self.assertEqual(replay.id, first.id)
        self.assertEqual(second.vacancy_id, vacancy.id)
        self.assertEqual(second.version, 2)
        self.assertEqual(
            self.service.candidate_resume(invitation.candidate_token).id,
            second.id,
        )

    def test_recruiter_can_upload_before_consent_with_audited_source(self) -> None:
        vacancy = self._vacancy("vacancy-recruiter-upload")
        other_vacancy = self._vacancy("vacancy-recruiter-upload-other")
        invitation = self.service.create_invitation(
            vacancy_id=vacancy.id,
            actor_id="recruiter-test",
            candidate_alias="synthetic-candidate",
            expires_in_hours=24,
        )

        uploaded = self.service.recruiter_upload_resume(
            vacancy_id=vacancy.id,
            invitation_id=invitation.invitation_id,
            actor_id="recruiter-test",
            document=b"Resume supplied by recruiter",
            filename="resume.txt",
            media_type="text/plain",
            idempotency_key="recruiter-resume-001",
        )
        replay = self.service.recruiter_upload_resume(
            vacancy_id=vacancy.id,
            invitation_id=invitation.invitation_id,
            actor_id="recruiter-test",
            document=b"Resume supplied by recruiter",
            filename="renamed.txt",
            media_type="text/plain",
            idempotency_key="recruiter-resume-001",
        )

        self.assertEqual(uploaded.version, 1)
        self.assertEqual(uploaded.uploaded_by_role, ResumeUploaderRole.RECRUITER)
        self.assertEqual(replay.id, uploaded.id)
        with self.assertRaises(HiringContextConflictError):
            self.service.recruiter_upload_resume(
                vacancy_id=vacancy.id,
                invitation_id=invitation.invitation_id,
                actor_id="recruiter-test",
                document=b"Conflicting recruiter upload",
                filename="resume.txt",
                media_type="text/plain",
                idempotency_key="recruiter-resume-001",
            )
        self.assertEqual(
            self.service.candidate_resume(invitation.candidate_token).id,
            uploaded.id,
        )
        with self.assertRaises(HiringContextNotFoundError):
            self.service.recruiter_upload_resume(
                vacancy_id=other_vacancy.id,
                invitation_id=invitation.invitation_id,
                actor_id="recruiter-test",
                document=b"Wrong vacancy",
                filename="resume.txt",
                media_type="text/plain",
                idempotency_key="recruiter-resume-002",
            )

        self.db.add(
            InterviewSession(
                invitation_id=invitation.invitation_id,
                consented_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        candidate_version = self.service.upload_resume(
            secret=invitation.candidate_token,
            document=b"Resume replaced by candidate",
            filename="candidate-resume.txt",
            media_type="text/plain",
            idempotency_key="candidate-resume-002",
        )
        context = self.service.build_agent_context(
            vacancy_id=vacancy.id,
            invitation_id=invitation.invitation_id,
        )

        self.assertEqual(candidate_version.version, 2)
        self.assertEqual(
            candidate_version.uploaded_by_role, ResumeUploaderRole.CANDIDATE
        )
        self.assertEqual(
            context.resume.uploaded_by_role, ResumeUploaderRole.CANDIDATE
        )

    def test_conflicting_idempotency_key_does_not_overwrite_vacancy(self) -> None:
        original = self._vacancy()
        replay = self._vacancy()
        self.assertEqual(replay.id, original.id)

        with self.assertRaises(HiringContextConflictError):
            self.service.create_vacancy(
                title="Different role",
                document=b"Go",
                filename="vacancy.txt",
                media_type="text/plain",
                actor_id="recruiter-test",
                idempotency_key="vacancy-key-001",
            )

    def test_agent_context_is_candidate_and_vacancy_isolated(self) -> None:
        first_vacancy = self._vacancy("vacancy-key-first")
        second_vacancy = self._vacancy("vacancy-key-second")
        first_invitation = self.service.create_invitation(
            vacancy_id=first_vacancy.id,
            actor_id="recruiter-test",
            candidate_alias="synthetic-one",
            expires_in_hours=24,
        )
        second_invitation = self.service.create_invitation(
            vacancy_id=second_vacancy.id,
            actor_id="recruiter-test",
            candidate_alias="synthetic-two",
            expires_in_hours=24,
        )
        first_session = InterviewSession(
            invitation_id=first_invitation.invitation_id,
            consented_at=datetime.now(timezone.utc),
        )
        second_session = InterviewSession(
            invitation_id=second_invitation.invitation_id,
            consented_at=datetime.now(timezone.utc),
        )
        self.db.add_all([first_session, second_session])
        self.db.commit()
        self.db.refresh(first_session)
        self.service.upload_resume(
            secret=first_invitation.candidate_token,
            document=b"First candidate resume",
            filename="resume.txt",
            media_type="text/plain",
            idempotency_key="resume-first-001",
        )
        self.service.upload_resume(
            secret=second_invitation.candidate_token,
            document=b"Second candidate resume",
            filename="resume.txt",
            media_type="text/plain",
            idempotency_key="resume-second-001",
        )
        self.db.add(
            CandidateResponse(
                session_id=first_session.id,
                question_id=uuid4(),
                storage_key="responses/synthetic.webm",
                content_type="audio/webm",
                checksum="a" * 64,
                transcription_status=TranscriptionStatus.COMPLETED,
                transcript_text="First candidate answer",
                created_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()

        context = self.service.build_agent_context(
            vacancy_id=first_vacancy.id,
            invitation_id=first_invitation.invitation_id,
        )

        self.assertEqual(context.resume.untrusted_text, "First candidate resume")
        self.assertEqual(context.answers[0].untrusted_text, "First candidate answer")
        self.assertTrue(context.policy.resume_is_claim_source_only)
        self.assertNotIn("Second candidate", context.model_dump_json())
        with self.assertRaises(HiringContextNotFoundError):
            self.service.build_agent_context(
                vacancy_id=second_vacancy.id,
                invitation_id=first_invitation.invitation_id,
            )


if __name__ == "__main__":
    unittest.main()
