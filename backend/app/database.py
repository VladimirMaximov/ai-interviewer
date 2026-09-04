"""Database and provider factories used by request-scoped workflows."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.openai_manager_brief import OpenAIManagerBriefAgent
from app.adapters.openai_interview_agents import build_openai_interview_agents
from app.adapters.storage import S3ObjectStorage
from app.adapters.whisper_cpp import WhisperCppProvider
from app.config import settings
from app.services.audio_processing import WhisperAudioProcessor
from app.services.candidate_workflow import SqlCandidateWorkflow
from app.services.hiring_context import HiringContextService
from app.services.manager_brief import ManagerBriefService
from app.services.multi_agent_harness import MultiAgentHarness
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


def multi_agent_harness_factory() -> MultiAgentHarness:
    """Build an isolated harness whose five semantic stages all use the LLM."""

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(engine, expire_on_commit=False)()
    agents = build_openai_interview_agents(
        api_key=settings.openai_api_key,
        model=settings.multi_agent_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.multi_agent_timeout_seconds,
    )
    return MultiAgentHarness(
        session,
        agents,
        max_attempts=settings.multi_agent_max_attempts,
        strong_pool_min_readiness=settings.strong_pool_min_readiness,
        strong_pool_min_coverage=settings.strong_pool_min_coverage,
        alternative_min_fit=settings.alternative_vacancy_min_fit,
        alternative_max_grade_distance=settings.alternative_max_grade_distance,
        personalization_cap=settings.multi_agent_personalization_cap,
    )
