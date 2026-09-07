"""Audio-first orchestration for private runtime presenter assets."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.adapters.storage import PrivateObjectStorage
from app.domain.interview_runtime import PresenterAssetRequest
from app.models.interview import AvatarAssetStatus, QuestionAvatarAsset
from app.interview_config import invitation_input
from app.models.interview import InterviewInvitation


def presenter_digest(request: PresenterAssetRequest, tts_version: str) -> str:
    value = {
        **request.model_dump(mode="json"),
        "tts_version": tts_version,
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class PresenterAssetService:
    def __init__(
        self, sessions: sessionmaker, storage: PrivateObjectStorage, tts: object,
        avatar: object, *, tts_version: str = "xtts-v2",
    ) -> None:
        self.sessions = sessions
        self.storage = storage
        self.tts = tts
        self.avatar = avatar
        self.tts_version = tts_version

    def ensure(self, request: PresenterAssetRequest) -> QuestionAvatarAsset:
        digest = presenter_digest(request, self.tts_version)
        with self.sessions() as db:
            existing = db.scalar(select(QuestionAvatarAsset).where(
                QuestionAvatarAsset.invitation_id == request.invitation_id,
                QuestionAvatarAsset.question_id == request.question_id,
                QuestionAvatarAsset.content_hash == digest,
            ))
            if existing:
                return existing
            now = datetime.now(timezone.utc)
            asset = QuestionAvatarAsset(
                invitation_id=request.invitation_id, question_id=request.question_id,
                renderer="musetalk", renderer_version=request.renderer_version,
                status=AvatarAssetStatus.QUEUED, content_hash=digest,
                question_text_snapshot=request.question_text, voice_id=request.voice_id,
                tts_version=self.tts_version, portrait_version=request.portrait_version,
                attempt_count=0, created_at=now, updated_at=now,
            )
            db.add(asset); db.commit(); db.refresh(asset)
            return asset

    def process(self, asset_id: UUID, portrait: Path) -> None:
        processing_error: Exception | None = None
        with self.sessions() as db:
            asset = db.get(QuestionAvatarAsset, asset_id)
            if not asset or asset.status is AvatarAssetStatus.READY:
                return
            asset.attempt_count += 1
            asset.status = AvatarAssetStatus.AUDIO_PROCESSING
            asset.updated_at = datetime.now(timezone.utc); db.commit()
            try:
                with tempfile.TemporaryDirectory(prefix="presenter-") as directory:
                    root = Path(directory); audio = root / "question.wav"
                    self.tts.synthesize(asset.question_text_snapshot, speaker=asset.voice_id, output_path=audio)
                    audio_key = f"presenter/{asset.invitation_id}/{asset.content_hash}.wav"
                    self.storage.put_file(audio_key, audio, "audio/wav")
                    asset.audio_storage_key = audio_key
                    asset.status = AvatarAssetStatus.AUDIO_READY; db.commit()
                    asset.status = AvatarAssetStatus.AVATAR_PROCESSING; db.commit()
                    video = self.avatar.render(portrait, audio, output_path=root / "avatar.mp4", workspace=root / "musetalk")
                    video_key = f"presenter/{asset.invitation_id}/{asset.content_hash}.mp4"
                    self.storage.put_file(video_key, video, "video/mp4")
                    asset.video_storage_key = video_key
                    asset.status = AvatarAssetStatus.READY
                    asset.ready_at = datetime.now(timezone.utc)
                    asset.failure_stage = asset.failure_reason = None
            except Exception as error:
                processing_error = error
                asset.status = AvatarAssetStatus.FAILED
                asset.failure_stage = "avatar" if asset.audio_storage_key else "audio"
                asset.failure_reason = type(error).__name__[:120]
            asset.updated_at = datetime.now(timezone.utc); db.commit()
        if processing_error is not None:
            raise RuntimeError("presenter generation failed") from processing_error

    def mark_enqueued(self, asset_id: UUID) -> bool:
        """Atomically reserve a new asset so repeated prewarm calls stay idempotent."""
        with self.sessions() as db:
            result = db.execute(
                update(QuestionAvatarAsset)
                .where(
                    QuestionAvatarAsset.id == asset_id,
                    QuestionAvatarAsset.status == AvatarAssetStatus.QUEUED,
                )
                .values(status=AvatarAssetStatus.PROCESSING, updated_at=datetime.now(timezone.utc))
            )
            db.commit()
            return result.rowcount == 1


class CeleryPresenterDispatcher:
    """Create idempotent assets before publishing small queue messages."""

    def __init__(
        self, service: PresenterAssetService, *, voice_id: str,
        renderer_version: str, task_sender=None,
    ) -> None:
        self.service = service
        self.voice_id = voice_id
        self.renderer_version = renderer_version
        self.task_sender = task_sender

    def prewarm(self, invitation: InterviewInvitation) -> None:
        configured = invitation_input(
            invitation.question_config, invitation.follow_up_after_all_answers
        )
        for question in configured.questions:
            self.enqueue(invitation.id, question.id, question.text)

    def enqueue(self, invitation_id: UUID, question_id: UUID, text: str) -> None:
        asset = self.service.ensure(PresenterAssetRequest(
            invitation_id=invitation_id, question_id=question_id,
            question_text=text, voice_id=self.voice_id,
            portrait_version="interviewer-v1",
            renderer_version=self.renderer_version,
        ))
        if self.service.mark_enqueued(asset.id):
            if self.task_sender is None:
                from app.workers.presenter_tasks import render_presenter
                render_presenter.apply_async(args=[str(asset.id)])
            else:
                self.task_sender(str(asset.id))
