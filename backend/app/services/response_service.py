"""Confirm private uploads and orchestrate asynchronous transcription."""

from __future__ import annotations

import tempfile
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.adapters.storage import PrivateObjectStorage
from app.models.interview import TranscriptionStatus


class ResponseStore(Protocol):
    """Persistence operations required by transcription orchestration."""

    def set_transcription_processing(self, response_id: UUID) -> None: ...
    def set_transcription_completed(self, response_id: UUID, transcript: str) -> None: ...
    def set_transcription_failed(self, response_id: UUID) -> None: ...


class AudioTranscriber(Protocol):
    def transcribe(self, source_path: Path, *, language: str = "ru") -> str: ...


class UploadNotFoundError(ValueError):
    """Raised when an upload confirmation references no private object."""


class ResponseService:
    """Run transcription outside the request while retaining an auditable state."""

    def __init__(self, storage: PrivateObjectStorage, store: ResponseStore, transcriber: AudioTranscriber,
                 executor: Executor | None = None) -> None:
        self._storage = storage
        self._store = store
        self._transcriber = transcriber
        self._executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr")

    def confirm_upload(self, response_id: UUID, storage_key: str) -> Future[None]:
        """Validate an uploaded private object and schedule its transcription."""
        if not self._storage.object_exists(storage_key):
            raise UploadNotFoundError("Uploaded audio is unavailable")
        self._store.set_transcription_processing(response_id)
        return self._executor.submit(self._transcribe, response_id, storage_key)

    def _transcribe(self, response_id: UUID, storage_key: str) -> None:
        suffix = Path(storage_key).suffix if Path(storage_key).suffix in {".webm", ".wav", ".ogg", ".mp4"} else ".webm"
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-upload-") as directory:
                source_path = Path(directory) / f"response{suffix}"
                self._storage.download_to(storage_key, source_path)
                transcript = self._transcriber.transcribe(source_path, language="ru")
            self._store.set_transcription_completed(response_id, transcript)
        except Exception:
            # A failure must preserve the original object while withholding text.
            self._store.set_transcription_failed(response_id)
