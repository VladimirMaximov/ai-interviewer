"""PostgreSQL-backed candidate workflow; object keys are always server-owned."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage import PrivateObjectStorage
from app.api.candidate import (
    ConfirmUploadRequest,
    ConfirmRecordingChunkRequest,
    FinishRecordingRequest,
    InvitationView,
    RecordingChunkGrant,
    RecordingChunkGrantRequest,
    RecordingGrant,
    ResponseSegmentRequest,
    ResponseSegmentView,
    StartRecordingRequest,
    TimelineEventRequest,
    TranscriptView,
    UploadGrant,
    UploadGrantRequest,
)
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    CandidateResponse,
    InterviewInvitation,
    InterviewRecording,
    InterviewRecordingChunk,
    InterviewTimelineEvent,
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
        response = self.db.scalar(
            select(CandidateResponse).where(
                CandidateResponse.session_id == session.id,
                CandidateResponse.question_id == request.question_id,
            )
        )
        if response:
            response.storage_key = f"responses/{session.id}/{uuid4()}.webm"
            response.content_type = request.content_type
            response.checksum = ""
            response.transcription_status = TranscriptionStatus.PENDING
            response.transcript_text = None
        else:
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

    def record_timeline_event(self, secret: str, request: TimelineEventRequest) -> bool:
        session = self._session(secret)
        if not session:
            return False
        self.db.add(InterviewTimelineEvent(session_id=session.id, question_id=request.question_id, event_type=request.event_type, occurred_at=datetime.now(timezone.utc), recording_offset_ms=request.recording_offset_ms))
        self.db.commit()
        return True

    def start_recording(self, secret: str, request: StartRecordingRequest) -> RecordingGrant | None:
        session = self._session(secret)
        if not session or session.consented_at is None:
            return None
        recording = self.db.scalar(select(InterviewRecording).where(InterviewRecording.session_id == session.id))
        if recording and recording.ended_at is not None:
            return None
        if not recording:
            recording = InterviewRecording(session_id=session.id, storage_key=f"recordings/{session.id}/{uuid4()}", content_type=request.content_type, started_at=datetime.now(timezone.utc))
            self.db.add(recording); self.db.commit(); self.db.refresh(recording)
        # Chunks receive their own short-lived upload grants. The recording key
        # is a private prefix, not a large object uploaded at the end.
        return RecordingGrant(recording_id=recording.id, storage_key=recording.storage_key, upload_url="", content_type=recording.content_type)

    def finish_recording(self, secret: str, request: FinishRecordingRequest) -> bool:
        session = self._session(secret); recording = self.db.get(InterviewRecording, request.recording_id) if session else None
        if not recording or recording.session_id != session.id or recording.ended_at is not None:
            return False
        chunks = list(self.db.scalars(select(InterviewRecordingChunk).where(
            InterviewRecordingChunk.recording_id == recording.id,
        ).order_by(InterviewRecordingChunk.sequence)))
        if not chunks or any(chunk.uploaded_at is None for chunk in chunks) or [chunk.sequence for chunk in chunks] != list(range(len(chunks))):
            return False
        recording.checksum = request.checksum; recording.ended_at = datetime.now(timezone.utc)
        session.submitted_at = recording.ended_at
        responses = list(self.db.scalars(select(CandidateResponse).where(
            CandidateResponse.session_id == session.id,
            CandidateResponse.start_offset_ms.is_not(None),
            CandidateResponse.end_offset_ms.is_not(None),
            CandidateResponse.transcription_status == TranscriptionStatus.PENDING,
        )))
        for response in responses:
            response.transcription_status = TranscriptionStatus.PROCESSING
        self.db.commit()
        if self.scheduler:
            for response in responses:
                self.scheduler.schedule_segment_chunks(
                    response.id,
                    [(chunk.storage_key, chunk.start_offset_ms, chunk.end_offset_ms) for chunk in chunks],
                    response.start_offset_ms,
                    response.end_offset_ms,
                )
        return True

    def create_recording_chunk_grant(self, secret: str, request: RecordingChunkGrantRequest) -> RecordingChunkGrant | None:
        session = self._session(secret)
        recording = self.db.get(InterviewRecording, request.recording_id) if session else None
        if not recording or recording.session_id != session.id or recording.ended_at is not None:
            return None
        if request.content_type != recording.content_type or request.end_offset_ms <= request.start_offset_ms:
            return None
        chunk = self.db.scalar(select(InterviewRecordingChunk).where(
            InterviewRecordingChunk.recording_id == recording.id,
            InterviewRecordingChunk.sequence == request.sequence,
        ))
        if not chunk:
            extension = "mp4" if request.content_type == "video/mp4" else "webm"
            chunk = InterviewRecordingChunk(
                recording_id=recording.id,
                sequence=request.sequence,
                storage_key=f"{recording.storage_key}/chunks/{request.sequence:06d}.{extension}",
                content_type=request.content_type,
                start_offset_ms=request.start_offset_ms,
                end_offset_ms=request.end_offset_ms,
            )
            self.db.add(chunk); self.db.commit(); self.db.refresh(chunk)
        return RecordingChunkGrant(
            chunk_id=chunk.id,
            upload_url=self.storage.create_upload_url(chunk.storage_key, chunk.content_type),
            content_type=chunk.content_type,
        )

    def confirm_recording_chunk(self, secret: str, request: ConfirmRecordingChunkRequest) -> bool:
        session = self._session(secret)
        chunk = self.db.get(InterviewRecordingChunk, request.chunk_id) if session else None
        if not chunk or not self.storage.object_exists(chunk.storage_key):
            return False
        recording = self.db.get(InterviewRecording, chunk.recording_id)
        if not recording or recording.session_id != session.id or recording.ended_at is not None:
            return False
        chunk.checksum = request.checksum
        chunk.uploaded_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def save_response_segment(self, secret: str, request: ResponseSegmentRequest) -> ResponseSegmentView | None:
        session = self._session(secret)
        if not session or session.consented_at is None or request.end_offset_ms <= request.start_offset_ms:
            return None
        recording = self.db.scalar(select(InterviewRecording).where(InterviewRecording.session_id == session.id))
        if not recording or recording.ended_at is not None:
            return None
        response = self.db.scalar(select(CandidateResponse).where(
            CandidateResponse.session_id == session.id,
            CandidateResponse.question_id == request.question_id,
        ))
        if not response:
            response = CandidateResponse(
                session_id=session.id,
                question_id=request.question_id,
                storage_key=None,
                content_type=recording.content_type,
                checksum="",
                transcription_status=TranscriptionStatus.PENDING,
                start_offset_ms=request.start_offset_ms,
                end_offset_ms=request.end_offset_ms,
            )
            self.db.add(response)
        else:
            response.start_offset_ms = request.start_offset_ms
            response.end_offset_ms = request.end_offset_ms
            response.transcription_status = TranscriptionStatus.PENDING
            response.transcript_text = None
        self.db.commit(); self.db.refresh(response)
        return ResponseSegmentView(response_id=response.id, status=response.transcription_status)
