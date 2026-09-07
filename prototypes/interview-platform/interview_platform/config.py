"""Runtime configuration kept outside domain and application code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    manager_key: str
    recruiter_key: str
    db_path: Path
    manager_id: str = "hiring-manager"
    host: str = "127.0.0.1"
    port: int = 8000
    max_context_bytes: int = 1_000_000
    max_context_chars: int = 50_000
    minimum_evidence_coverage: float = 0.5
    assessment_provider: str = "openai"
    assessment_model: str = "gpt-5-mini"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    def __post_init__(self) -> None:
        if len(self.manager_key) < 8:
            raise ValueError("manager key must contain at least 8 characters")
        if len(self.recruiter_key) < 8:
            raise ValueError("recruiter key must contain at least 8 characters")
        if self.manager_key == self.recruiter_key:
            raise ValueError("recruiter and manager keys must be different")
        if not self.manager_id.strip():
            raise ValueError("manager id is required")
        if not (1 <= self.port <= 65_535):
            raise ValueError("port must be between 1 and 65535")
        if self.max_context_bytes < 1 or self.max_context_chars < 1:
            raise ValueError("context limits must be positive")
        if not (0 <= self.minimum_evidence_coverage <= 1):
            raise ValueError("minimum evidence coverage must be between 0 and 1")
        if self.assessment_provider not in {"openai", "deterministic"}:
            raise ValueError("assessment provider must be openai or deterministic")
        if not self.assessment_model.strip():
            raise ValueError("assessment model is required")
        if not self.openai_base_url.startswith(("https://", "http://")):
            raise ValueError("OPENAI_BASE_URL must be an HTTP(S) URL")

    @classmethod
    def from_values(
        cls,
        *,
        manager_key: str | None,
        db_path: str | Path,
        host: str,
        port: int,
        recruiter_key: str | None = None,
        manager_id: str | None = None,
        assessment_provider: str | None = None,
        assessment_model: str | None = None,
    ) -> "Settings":
        resolved_manager_key = manager_key or os.environ.get("INTERVIEW_MANAGER_KEY", "")
        resolved_recruiter_key = recruiter_key or os.environ.get("INTERVIEW_RECRUITER_KEY", "")
        if not resolved_manager_key:
            raise ValueError("set INTERVIEW_MANAGER_KEY or pass --manager-key")
        if not resolved_recruiter_key:
            raise ValueError("set INTERVIEW_RECRUITER_KEY or pass --recruiter-key")
        return cls(
            manager_key=resolved_manager_key,
            recruiter_key=resolved_recruiter_key,
            db_path=Path(db_path),
            manager_id=manager_id or os.environ.get("INTERVIEW_MANAGER_ID", "hiring-manager"),
            host=host,
            port=port,
            assessment_provider=assessment_provider
            or os.environ.get("INTERVIEW_ASSESSMENT_PROVIDER", "openai"),
            assessment_model=assessment_model
            or os.environ.get("INTERVIEW_ASSESSMENT_MODEL", "gpt-5-mini"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_base_url=os.environ.get(
                "OPENAI_BASE_URL",
                "https://api.openai.com/v1",
            ),
        )
