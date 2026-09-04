"""Database and provider factories used by request-scoped workflows."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.openai_manager_brief import OpenAIManagerBriefAgent
from app.adapters.storage import S3ObjectStorage
from app.adapters.whisper_cpp import WhisperCppProvider
from app.config import settings
from app.services.audio_processing import WhisperAudioProcessor
from app.services.candidate_workflow import SqlCandidateWorkflow
from app.services.hiring_context import HiringContextService
from app.services.manager_brief import ManagerBriefService
from app.services.transcription_scheduler import TranscriptionScheduler


def workflow_factory() -> SqlCandidateWorkflow:
    import boto3

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False)
    session = sessions()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    storage = S3ObjectStorage(client, settings.s3_bucket)
    processor = WhisperAudioProcessor(
        WhisperCppProvider(
            Path(settings.whisper_cpp_binary), Path(settings.whisper_cpp_model)
        ),
        settings.ffmpeg_binary,
    )
    return SqlCandidateWorkflow(
        session,
        storage,
        TranscriptionScheduler(sessions, storage, processor),
    )


def manager_brief_service_factory() -> ManagerBriefService:
    """Build a manager workflow without sharing a SQLAlchemy session across requests."""
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(engine, expire_on_commit=False)()
    agent = OpenAIManagerBriefAgent(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.manager_brief_model,
    )
    return ManagerBriefService(
        session,
        agent,
        max_attempts=settings.manager_brief_max_attempts,
    )


def hiring_context_service_factory() -> HiringContextService:
    """Build a request-scoped vacancy/resume context service."""
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(engine, expire_on_commit=False)()
    return HiringContextService(session)
