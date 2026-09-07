"""Database and provider factories used by request-scoped workflows."""

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.openai_manager_brief import OpenAIManagerBriefAgent
from app.adapters.openai_interview_agents import build_openai_interview_agents
from app.adapters.silero_tts import SileroTtsProvider
from app.adapters.xtts_http import XttsHttpProvider
from app.adapters.storage import S3ObjectStorage
from app.adapters.gigaam3 import GigaAm3Provider
from app.adapters.whisper_cpp import WhisperCppProvider
from app.config import settings
from app.services.candidate_workflow import SqlCandidateWorkflow
from app.services.hiring_context import HiringContextService
from app.services.manager_brief import ManagerBriefService
from app.services.multi_agent_harness import MultiAgentHarness
from app.services.transcription_scheduler import CeleryTranscriptionDispatcher
from app.services.voice_proctoring import VoiceProctoringScheduler
from app.adapters.xtts_runtime import XttsRuntime
from app.adapters.musetalk_runtime import MuseTalkRuntime
from app.services.presenter_assets import CeleryPresenterDispatcher, PresenterAssetService
from app.services.interview_results import InterviewResultsService


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
def transcription_provider_factory():
    """Build the configured local STT backend without changing worker code."""
    if settings.transcription_provider == "gigaam3":
        return GigaAm3Provider(settings.gigaam_model)
    return WhisperCppProvider(
        Path(settings.whisper_cpp_binary), Path(settings.whisper_cpp_model)
    )


def question_speech_provider_factory() -> SileroTtsProvider | XttsHttpProvider | None:
    """Return local question TTS, or let the browser use its own fallback."""
    if settings.question_speech_provider == "browser":
        return None
    if settings.question_speech_provider == "xtts":
        return XttsHttpProvider(settings.xtts_endpoint, settings.xtts_voice)
    return SileroTtsProvider(
        Path(settings.silero_helper), settings.silero_voice, settings.silero_python
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
    public_client = boto3.client(
        "s3", endpoint_url=settings.s3_public_endpoint_url or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    storage = S3ObjectStorage(client, settings.s3_bucket, public_client)
    from app.workers.celery_app import celery_app
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
        CeleryTranscriptionDispatcher(celery_app, settings.celery_cpu_queue),
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
    return HiringContextService(session, presenter_dispatcher_factory())


def interview_results_service_factory() -> InterviewResultsService:
    """Build a recruiter-scoped read model with private signed media URLs."""
    import boto3

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session = sessionmaker(engine, expire_on_commit=False)()
    client = boto3.client(
        "s3", endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    public_client = boto3.client(
        "s3", endpoint_url=settings.s3_public_endpoint_url or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    return InterviewResultsService(session, S3ObjectStorage(client, settings.s3_bucket, public_client))


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


@lru_cache(maxsize=1)
def presenter_asset_service_factory() -> PresenterAssetService:
    """Build the isolated GPU worker service; models load lazily and persist."""
    import boto3

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    sessions = sessionmaker(engine, expire_on_commit=False)
    client = boto3.client(
        "s3", endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    public_client = boto3.client(
        "s3", endpoint_url=settings.s3_public_endpoint_url or settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    return PresenterAssetService(
        sessions,
        S3ObjectStorage(client, settings.s3_bucket, public_client),
        XttsRuntime(),
        MuseTalkRuntime(Path(settings.presenter_musetalk_root)),
    )


def presenter_dispatcher_factory() -> CeleryPresenterDispatcher | None:
    if not settings.presenter_enabled:
        return None
    return CeleryPresenterDispatcher(
        presenter_asset_service_factory(),
        voice_id=settings.xtts_voice,
        renderer_version=settings.presenter_model_version,
    )
