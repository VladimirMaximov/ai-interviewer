"""PostgreSQL-backed candidate workflow; object keys are always server-owned."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage import PrivateObjectStorage
from app.api.candidate import (
    ConfirmUploadRequest,
    InvitationView,
    TranscriptView,
    UploadGrant,
    UploadGrantRequest,
)
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    CandidateResponse,
    InterviewInvitation,
    InterviewSession,
    InvitationStatus,
    TranscriptionStatus,
)
from app.security.invitations import digest_invitation_secret


class SqlCandidateWorkflow:
    def __init__(
        self, session: Session, storage: PrivateObjectStorage, scheduler=None
    ) -> None:
        self.db, self.storage, self.scheduler = session, storage, scheduler

    def _session(self, secret: str) -> InterviewSession | None:
        invitation = self.db.scalar(
            select(InterviewInvitation).where(
                InterviewInvitation.token_digest == digest_invitation_secret(secret)
            )
        )
        if not invitation or invitation.status is not InvitationStatus.ACTIVE:
            return None
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        session = self.db.scalar(
            select(InterviewSession).where(
                InterviewSession.invitation_id == invitation.id
            )
        )
        if not session:
            session = InterviewSession(invitation_id=invitation.id)
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
        return session

    def _view(self, session: InterviewSession) -> InvitationView:
        invitation = self.db.get(InterviewInvitation, session.invitation_id)
        vacancy = (
            self.db.get(Vacancy, invitation.vacancy_id)
            if invitation and invitation.vacancy_id
            else None
        )
        resume = (
            self.db.scalar(
                select(CandidateResume.id)
                .where(CandidateResume.invitation_id == invitation.id)
                .limit(1)
            )
            if invitation
            else None
        )
        return InvitationView(
            session_id=session.id,
            consented=session.consented_at is not None,
            vacancy_id=vacancy.id if vacancy else None,
            vacancy_title=vacancy.title if vacancy else None,
            resume_uploaded=resume is not None,
        )

    def resolve(self, secret: str) -> InvitationView | None:
        session = self._session(secret)
        return self._view(session) if session else None

    def consent(self, secret: str) -> InvitationView | None:
        session = self._session(secret)
        if not session:
            return None
        if session.consented_at is None:
            session.consented_at = datetime.now(timezone.utc)
            self.db.commit()
        return self._view(session)

    def create_upload_grant(
        self, secret: str, request: UploadGrantRequest
    ) -> UploadGrant | None:
        session = self._session(secret)
        if not session or session.consented_at is None:
            return None
        response = CandidateResponse(
            session_id=session.id,
            question_id=request.question_id,
            storage_key=f"responses/{session.id}/{uuid4()}.webm",
            content_type=request.content_type,
            checksum="",
            transcription_status=TranscriptionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return UploadGrant(
            response_id=response.id,
            storage_key=response.storage_key,
            upload_url=self.storage.create_upload_url(
                response.storage_key, request.content_type
            ),
        )

    def confirm_upload(
        self, secret: str, request: ConfirmUploadRequest
    ) -> TranscriptView | None:
        session = self._session(secret)
        response = (
            self.db.get(CandidateResponse, request.response_id) if session else None
        )
        if (
            not response
            or response.session_id != session.id
            or not self.storage.object_exists(response.storage_key)
        ):
            return None
        response.checksum = request.checksum
        response.transcription_status = TranscriptionStatus.PROCESSING
        self.db.commit()
        if self.scheduler:
            self.scheduler.schedule(response.id, response.storage_key)
        return TranscriptView(status=response.transcription_status)

    def transcript(self, secret: str, response_id):
        session = self._session(secret)
        response = self.db.get(CandidateResponse, response_id) if session else None
        if not response or response.session_id != session.id:
            return None
        return TranscriptView(
            status=response.transcription_status, text=response.transcript_text
        )
