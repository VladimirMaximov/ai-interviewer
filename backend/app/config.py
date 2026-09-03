"""Runtime configuration; secrets are supplied only through environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by API and provider adapters."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    transcription_provider: str = "whisper_cpp"
    gigaam_model: str = "v3_e2e_rnnt"
    routerai_api_key: str | None = None
    routerai_base_url: str = "https://routerai.ru/api/v1"
    whisper_cpp_binary: str = "whisper-cli"
    whisper_cpp_model: str = "backend/models/ggml-small.bin"
    ffmpeg_binary: str = "ffmpeg"
    silero_helper: str = "scripts/silero_tts.py"
    database_url: str = "postgresql+psycopg://ai_interviewer:local_dev_only@localhost:5433/ai_interviewer"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "interview-audio"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"


settings = Settings()
