"""PostgreSQL-backed candidate workflow; object keys are always server-owned."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage import PrivateObjectStorage
from app.api.candidate import (
    CandidateQuestion,
    CodeAnswerRequest,
    ConfirmUploadRequest,
    ConfirmRecordingChunkRequest,
    FinishRecordingRequest,
    FollowUpQuestionView,
    InvitationView,
    MonitoringEvidenceGrant,
    MonitoringEvidenceGrantRequest,
    MonitoringEventRequest,
    MonitoringEventView,
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
from app.interview_config import InterviewInput, invitation_input
from app.models.hiring_context import CandidateResume, Vacancy
from app.models.interview import (
    AvatarAssetStatus,
    CandidateResponse,
    CodeAnswer,
    FollowUpStatus,
    InterviewFollowUpQuestion,
    InterviewInvitation,
    InterviewMonitoringEvent,
    QuestionAvatarAsset,
    InterviewRecording,
    InterviewRecordingChunk,
    InterviewTimelineEvent,
    InterviewSession,
    InvitationStatus,
    TranscriptionStatus,
)
from app.security.invitations import digest_invitation_secret


MAX_MONITORING_EVIDENCE_BYTES = 2_000_000


class SqlCandidateWorkflow:
    def __init__(
        self, session: Session, storage: PrivateObjectStorage, scheduler=None, voice_scheduler=None
    ) -> None:
        self.db, self.storage, self.scheduler = session, storage, scheduler
        self.voice_scheduler = voice_scheduler

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

    def _input(self, session: InterviewSession) -> InterviewInput:
        invitation = self.db.get(InterviewInvitation, session.invitation_id)
        if not invitation:
            raise ValueError("invitation is missing")
        return invitation_input(
            invitation.question_config, invitation.follow_up_after_all_answers
        )

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
        interview_input = self._input(session)
        return InvitationView(
            session_id=session.id,
            consented=session.consented_at is not None,
            vacancy_id=vacancy.id if vacancy else None,
            vacancy_title=vacancy.title if vacancy else None,
            resume_uploaded=resume is not None,
            questions=[
                CandidateQuestion(id=item.id, text=item.text, kind=item.kind, block_key=block.key, block_title=block.title, time_limit_seconds=item.time_limit_seconds)
                for block in interview_input.blocks for item in block.questions
            ],
        )

    def question_speech_text(self, secret: str, question_id: UUID) -> str | None:
        """Return only an authorised question text for local TTS synthesis."""
        session = self._session(secret)
        # Question text is already returned by the token-scoped invitation
        # preview. Allow preflight to warm local TTS while the candidate checks
        # devices; this does not expose any additional data.
        if not session:
            return None
        for block in self._input(session).blocks:
            for question in block.questions:
                if question.id == question_id:
                    return question.text
        return None

    def avatar_video_url(self, secret: str, question_id: UUID) -> str | None:
        session = self._session(secret)
        if not session:
            return None
        asset = self.db.scalar(select(QuestionAvatarAsset).where(
            QuestionAvatarAsset.invitation_id == session.invitation_id,
            QuestionAvatarAsset.question_id == question_id,
            QuestionAvatarAsset.status == AvatarAssetStatus.READY,
        ))
        if not asset or not asset.video_storage_key or not self.storage.object_exists(asset.video_storage_key):
            return None
        return self.storage.create_download_url(asset.video_storage_key)

    def _base_sequence_complete(
        self, session: InterviewSession, interview_input: InterviewInput
    ) -> bool:
        answered_question_ids = set(
            self.db.scalars(
                select(CandidateResponse.question_id).where(
                    CandidateResponse.session_id == session.id,
                )
            )
        )
        return all(
            question.id in answered_question_ids
            for question in interview_input.questions
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
        if self.voice_scheduler:
            self.voice_scheduler.schedule(response.id)
        return TranscriptView(status=response.transcription_status)

    def transcript(self, secret: str, response_id):
        session = self._session(secret)
        response = self.db.get(CandidateResponse, response_id) if session else None
        if not response or response.session_id != session.id:
            return None
        return TranscriptView(
            status=response.transcription_status, text=response.transcript_text
        )

    def create_monitoring_evidence_grant(
        self, secret: str, request: MonitoringEvidenceGrantRequest
    ) -> MonitoringEvidenceGrant | None:
        session = self._session(secret)
        response = self.db.get(CandidateResponse, request.response_id) if session else None
        if (not session or session.consented_at is None or not response
                or response.session_id != session.id
                or response.question_id != request.question_id):
            return None
        existing = self.db.get(InterviewMonitoringEvent, request.client_event_id)
        if existing and (existing.session_id != session.id
                         or existing.response_id != response.id
                         or existing.question_id != response.question_id
                         or existing.evidence_content_type != request.content_type):
            return None
        suffix = ".mp4" if request.content_type == "video/mp4" else ".webm"
        storage_key = self._monitoring_storage_key(session.id, request.client_event_id, suffix)
        return MonitoringEvidenceGrant(
            client_event_id=request.client_event_id,
            upload_url=self.storage.create_upload_url(storage_key, request.content_type),
        )

    def record_monitoring_event(
        self, secret: str, request: MonitoringEventRequest
    ) -> MonitoringEventView | None:
        session = self._session(secret)
        response = self.db.get(CandidateResponse, request.response_id) if session else None
        if (not session or session.consented_at is None or not response
                or response.session_id != session.id
                or response.question_id != request.question_id):
            return None
        existing = self.db.get(InterviewMonitoringEvent, request.client_event_id)
        if existing:
            matches = (
                existing.session_id == session.id
                and existing.response_id == response.id
                and existing.question_id == response.question_id
                and existing.kind == request.kind
                and existing.started_at_ms == request.started_at_ms
                and existing.ended_at_ms == request.ended_at_ms
                and existing.evidence_content_type == request.evidence_content_type
                and existing.evidence_checksum == request.evidence_checksum
            )
            return self._monitoring_event_view(existing) if matches else None
        evidence_storage_key = None
        if request.evidence_content_type:
            suffix = ".mp4" if request.evidence_content_type == "video/mp4" else ".webm"
            evidence_storage_key = self._monitoring_storage_key(session.id, request.client_event_id, suffix)
            try:
                if not self.storage.object_exists(evidence_storage_key):
                    return None
                evidence_size = self.storage.object_size(evidence_storage_key)
            except Exception:
                return None
            if evidence_size <= 0 or evidence_size > MAX_MONITORING_EVIDENCE_BYTES:
                return None
        event = InterviewMonitoringEvent(
            id=request.client_event_id,
            session_id=session.id,
            response_id=response.id,
            question_id=response.question_id,
            kind=request.kind,
            started_at_ms=request.started_at_ms,
            ended_at_ms=request.ended_at_ms,
            confidence=request.confidence,
            source="browser_face",
            detector_name=request.detector_name,
            detector_version=request.detector_version,
            evidence_storage_key=evidence_storage_key,
            evidence_content_type=request.evidence_content_type,
            evidence_checksum=request.evidence_checksum,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(event)
        self.db.commit()
        return self._monitoring_event_view(event)

    @staticmethod
    def _monitoring_storage_key(session_id, event_id, suffix: str) -> str:
        return f"monitoring/{session_id}/{event_id}{suffix}"

    @staticmethod
    def _monitoring_event_view(event: InterviewMonitoringEvent) -> MonitoringEventView:
        return MonitoringEventView(
            id=event.id,
            kind=event.kind,
            started_at_ms=event.started_at_ms,
            ended_at_ms=event.ended_at_ms,
            review_status=event.review_status,
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
        # The browser client currently has no safe resume protocol: it restarts
        # chunk sequence numbers at zero. Refuse a second start instead of
        # allowing a new page to overwrite an active recording's media.
        if recording:
            return None
        if not recording:
            recording = InterviewRecording(session_id=session.id, storage_key=f"recordings/{session.id}/{uuid4()}", content_type=request.content_type, started_at=datetime.now(timezone.utc))
            self.db.add(recording); self.db.commit(); self.db.refresh(recording)
        # Chunks receive their own short-lived upload grants. The recording key
        # is a private prefix, not a large object uploaded at the end.
        return RecordingGrant(recording_id=recording.id, storage_key=recording.storage_key, upload_url="", content_type=recording.content_type)

    def _schedule_completed_response_segments(
        self,
        session: InterviewSession,
        recording: InterviewRecording,
    ) -> None:
        """Start STT once an answer is wholly covered by uploaded chunks.

        The candidate never waits for this work: each response remains pending
        until the next 10-second media chunk closes and is confirmed.  A future
        clarification agent can therefore consume a transcript during the same
        interview rather than only after its final submission.
        """
        if not self.scheduler:
            return
        chunks = list(self.db.scalars(select(InterviewRecordingChunk).where(
            InterviewRecordingChunk.recording_id == recording.id,
        ).order_by(InterviewRecordingChunk.sequence)))
        if not chunks or any(chunk.uploaded_at is None for chunk in chunks):
            return
        if [chunk.sequence for chunk in chunks] != list(range(len(chunks))):
            return
        covered_until_ms = chunks[-1].end_offset_ms
        responses = list(self.db.scalars(select(CandidateResponse).where(
            CandidateResponse.session_id == session.id,
            CandidateResponse.start_offset_ms.is_not(None),
            CandidateResponse.end_offset_ms.is_not(None),
            CandidateResponse.end_offset_ms <= covered_until_ms,
            CandidateResponse.transcription_status == TranscriptionStatus.PENDING,
        )))
        if not responses:
            return
        for response in responses:
            response.transcription_status = TranscriptionStatus.PROCESSING
        self.db.commit()
        chunk_sources = [(chunk.storage_key, chunk.start_offset_ms, chunk.end_offset_ms) for chunk in chunks]
        for response in responses:
            self.scheduler.schedule_segment_chunks(
                response.id,
                chunk_sources,
                response.start_offset_ms,
                response.end_offset_ms,
            )

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
        recording.duration_ms = chunks[-1].end_offset_ms
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
        self._schedule_completed_response_segments(session, recording)
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
                timed_out=request.timed_out,
            )
            self.db.add(response)
        else:
            response.start_offset_ms = request.start_offset_ms
            response.end_offset_ms = request.end_offset_ms
            response.transcription_status = TranscriptionStatus.PENDING
            response.transcript_text = None
            response.timed_out = request.timed_out
        follow_up = self.db.get(InterviewFollowUpQuestion, request.question_id)
        if follow_up and follow_up.session_id == session.id:
            follow_up.status = FollowUpStatus.ANSWERED
            follow_up.answered_at = datetime.now(timezone.utc)
        self.db.commit()
        self._schedule_completed_response_segments(session, recording)
        self.db.refresh(response)
        return ResponseSegmentView(response_id=response.id, status=response.transcription_status)

    def save_code_answer(self, secret: str, request: CodeAnswerRequest) -> ResponseSegmentView | None:
        session = self._session(secret)
        if not session or session.consented_at is None or request.end_offset_ms <= request.start_offset_ms:
            return None
        recording = self.db.scalar(select(InterviewRecording).where(InterviewRecording.session_id == session.id))
        if not recording or recording.ended_at is not None:
            return None
        question = next((item for item in self._input(session).questions if item.id == request.question_id), None)
        if not question or question.kind.value != "coding":
            return None
        response = self.db.scalar(select(CandidateResponse).where(CandidateResponse.session_id == session.id, CandidateResponse.question_id == request.question_id))
        if not response:
            response = CandidateResponse(session_id=session.id, question_id=request.question_id, storage_key=None, content_type=recording.content_type, checksum="", transcription_status=TranscriptionStatus.PENDING, transcript_text=None, start_offset_ms=request.start_offset_ms, end_offset_ms=request.end_offset_ms, timed_out=request.timed_out)
            self.db.add(response); self.db.flush()
        else:
            response.start_offset_ms, response.end_offset_ms = request.start_offset_ms, request.end_offset_ms
            response.content_type = recording.content_type
            response.transcription_status = TranscriptionStatus.PENDING
            response.transcript_text = None
            response.timed_out = request.timed_out
        code_answer = self.db.scalar(select(CodeAnswer).where(CodeAnswer.response_id == response.id))
        if not code_answer:
            code_answer = CodeAnswer(response_id=response.id, language=request.language.strip(), source_code=request.source_code, start_offset_ms=request.start_offset_ms, end_offset_ms=request.end_offset_ms, saved_at=datetime.now(timezone.utc)); self.db.add(code_answer)
        else:
            code_answer.language, code_answer.source_code = request.language.strip(), request.source_code
            code_answer.start_offset_ms, code_answer.end_offset_ms, code_answer.saved_at = request.start_offset_ms, request.end_offset_ms, datetime.now(timezone.utc)
        self.db.commit()
        self._schedule_completed_response_segments(session, recording)
        self.db.refresh(response)
        return ResponseSegmentView(response_id=response.id, status=response.transcription_status)

    def follow_up_questions(self, secret: str) -> list[FollowUpQuestionView] | None:
        session = self._session(secret)
        if not session:
            return None
        interview_input = self._input(session)
        follow_ups = list(self.db.scalars(select(InterviewFollowUpQuestion).where(
            InterviewFollowUpQuestion.session_id == session.id,
            InterviewFollowUpQuestion.status.in_((FollowUpStatus.READY, FollowUpStatus.PRESENTED, FollowUpStatus.ANSWERED)),
        ).order_by(InterviewFollowUpQuestion.created_at)))
        for follow_up in follow_ups:
            if follow_up.status is FollowUpStatus.READY:
                follow_up.status = FollowUpStatus.PRESENTED
                follow_up.presented_at = datetime.now(timezone.utc)
        self.db.commit()
        return [FollowUpQuestionView(id=item.id, source_response_id=item.source_response_id, text=item.text, status=item.status) for item in follow_ups]

    def queue_follow_up(self, session_id, text: str, *, source_response_id=None, transcript_snapshot: str | None = None) -> InterviewFollowUpQuestion:
        """Internal integration point for a future clarification agent, not public API."""
        if not text.strip():
            raise ValueError("follow-up text is required")
        session = self.db.get(InterviewSession, session_id)
        if not session:
            raise ValueError("session is missing")
        interview_input = self._input(session)
        if source_response_id:
            source_response = self.db.get(CandidateResponse, source_response_id)
            if not source_response or source_response.session_id != session.id:
                raise ValueError("source response is missing")
            configured_question = next((item for item in interview_input.questions if item.id == source_response.question_id), None)
            if not configured_question or not configured_question.follow_up_after_answer:
                raise ValueError("follow-up is not enabled for this question")
        elif not interview_input.follow_up_after_all_answers:
            raise ValueError("final follow-up is not enabled for this interview")
        elif not self._base_sequence_complete(session, interview_input):
            raise ValueError("base sequence is not complete")
        existing = list(self.db.scalars(select(InterviewFollowUpQuestion).where(
            InterviewFollowUpQuestion.session_id == session_id,
            InterviewFollowUpQuestion.source_response_id == source_response_id,
        )))
        if source_response_id and len(existing) >= 2:
            raise ValueError("follow-up depth limit reached")
        if not source_response_id and existing:
            return existing[0]
        follow_up = InterviewFollowUpQuestion(
            session_id=session_id,
            source_response_id=source_response_id,
            text=text.strip(),
            status=FollowUpStatus.READY,
            transcript_snapshot=transcript_snapshot,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(follow_up); self.db.commit(); self.db.refresh(follow_up)
        return follow_up
