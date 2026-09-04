"""Runtime configuration; secrets are supplied only through environment variables."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by API and provider adapters."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    transcription_provider: str = "whisper_cpp"
    gigaam_model: str = "v3_e2e_rnnt"
    routerai_api_key: str | None = None
    routerai_base_url: str = "https://routerai.ru/api/v1"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    manager_brief_model: str = "gpt-5-mini"
    manager_brief_max_attempts: int = Field(default=3, ge=1, le=5)
    multi_agent_model: str = "gpt-5.4-mini"
    multi_agent_max_attempts: int = Field(default=3, ge=1, le=5)
    multi_agent_timeout_seconds: float = Field(default=90.0, ge=1, le=300)
    strong_pool_min_readiness: float = Field(default=0.25, ge=-1, le=1)
    strong_pool_min_coverage: float = Field(default=0.5, ge=0, le=1)
    alternative_vacancy_min_fit: float = Field(default=0.25, ge=-1, le=1)
    alternative_max_grade_distance: int = Field(default=1, ge=0, le=4)
    multi_agent_personalization_cap: int = Field(default=3, ge=0, le=8)
    manager_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MANAGER_KEY", "INTERVIEW_MANAGER_KEY"),
    )
    manager_id: str = Field(
        default="hiring-manager",
        validation_alias=AliasChoices("MANAGER_ID", "INTERVIEW_MANAGER_ID"),
    )
    recruiter_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RECRUITER_KEY", "INTERVIEW_RECRUITER_KEY"),
    )
    recruiter_id: str = Field(
        default="recruiter",
        validation_alias=AliasChoices("RECRUITER_ID", "INTERVIEW_RECRUITER_ID"),
    )
    whisper_cpp_binary: str = "whisper-cli"
    whisper_cpp_model: str = "backend/models/ggml-small.bin"
    ffmpeg_binary: str = "ffmpeg"
    silero_helper: str = "scripts/silero_tts.py"
    database_url: str = (
        "postgresql+psycopg://ai_interviewer:local_dev_only@localhost:5433/ai_interviewer"
    )
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "interview-audio"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"


settings = Settings()
