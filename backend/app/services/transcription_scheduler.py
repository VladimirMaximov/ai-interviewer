"""Request-safe background transcription with a fresh database session per job."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from app.adapters.storage import PrivateObjectStorage
from app.models.interview import CandidateResponse, TranscriptionStatus

class TranscriptionScheduler:
    def __init__(self, sessions: sessionmaker, storage: PrivateObjectStorage, processor) -> None:
        self.sessions, self.storage, self.processor = sessions, storage, processor
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr")
    def schedule(self, response_id, key: str) -> None:
        self.executor.submit(self._run, response_id, key)
    def _run(self, response_id, key: str) -> None:
        import tempfile
        try:
            with tempfile.TemporaryDirectory(prefix="ai-interviewer-job-") as directory:
                source = Path(directory) / "response.webm"; self.storage.download_to(key, source)
                transcript = self.processor.transcribe(source)
            status, text = TranscriptionStatus.COMPLETED, transcript
        except Exception:
            status, text = TranscriptionStatus.FAILED, None
        with self.sessions() as db:
            response = db.get(CandidateResponse, response_id)
            if response: response.transcription_status, response.transcript_text = status, text; db.commit()
