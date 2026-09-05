"""Database and provider factories used by request-scoped workflows."""

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
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
from app.services.voice_proctoring import VoiceProctoringScheduler


_voice_executor = ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="voice-proctoring"
)


@lru_cache(maxsize=1)
def _voice_analyzer():
    """Reuse heavyweight model instances and serialize access in one process."""

    from app.adapters.pyannote_voice import PyannoteVoiceAnalyzer

    return PyannoteVoiceAnalyzer(
        huggingface_token=settings.huggingface_token,
        diarization_model=settings.proctoring_diarization_model,
        embedding_model=settings.proctoring_embedding_model,
        embedding_cache=settings.proctoring_embedding_cache,
        minimum_reference_speech_seconds=(
            settings.proctoring_minimum_reference_seconds
        ),
        reference_similarity_threshold=(
            settings.proctoring_reference_similarity
        ),
        speaker_similarity_threshold=settings.proctoring_speaker_similarity,
    )


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
    voice_scheduler = None
    if settings.proctoring_provider == "pyannote":
        voice_scheduler = VoiceProctoringScheduler(
            sessions,
            storage,
            _voice_analyzer(),
            executor=_voice_executor,
        )
    return SqlCandidateWorkflow(
        session,
        storage,
        TranscriptionScheduler(sessions, storage, processor),
        voice_scheduler,
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
    """Build an isolated harness whose six semantic stages all use the LLM."""

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(engine, expire_on_commit=False)()
    agents = build_openai_interview_agents(
        api_key=settings.openai_api_key,
        model=settings.multi_agent_model,
        base_url=settings.openai_base_url,
        timeout_seconds=settings.multi_agent_timeout_seconds,
        api_mode=settings.multi_agent_api_mode,
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
        follow_up_confidence_threshold=settings.follow_up_confidence_threshold,
        follow_up_max_per_session=settings.follow_up_max_per_session,
    )
