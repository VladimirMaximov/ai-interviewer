"""Database and private-storage factories used by request-scoped workflows."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.adapters.storage import S3ObjectStorage
from app.config import settings
from app.services.candidate_workflow import SqlCandidateWorkflow
from app.services.audio_processing import WhisperAudioProcessor
from app.services.transcription_scheduler import TranscriptionScheduler
from app.adapters.whisper_cpp import WhisperCppProvider
from pathlib import Path

def workflow_factory() -> SqlCandidateWorkflow:
    import boto3
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False); session = sessions()
    client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key)
    storage = S3ObjectStorage(client, settings.s3_bucket)
    processor = WhisperAudioProcessor(WhisperCppProvider(Path(settings.whisper_cpp_binary), Path(settings.whisper_cpp_model)), settings.ffmpeg_binary)
    return SqlCandidateWorkflow(session, storage, TranscriptionScheduler(sessions, storage, processor))
