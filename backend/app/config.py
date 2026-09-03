"""Runtime configuration; secrets are supplied only through environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by API and provider adapters."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    transcription_provider: str = "whisper_cpp"
    routerai_api_key: str | None = None
    routerai_base_url: str = "https://routerai.ru/api/v1"


settings = Settings()
