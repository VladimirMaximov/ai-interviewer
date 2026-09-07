"""Shared primitives for vacancy-aware, evidence-first hiring workflows."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

from .errors import ValidationError


class ActorRole(StrEnum):
    RECRUITER = "recruiter"
    TECHNICAL_EXPERT = "technical_expert"
    HIRING_MANAGER = "hiring_manager"
    SYSTEM = "system"


FORBIDDEN_CRITERION_TERMS = (
    "accent",
    "age",
    "appearance",
    "attractive",
    "confidence of voice",
    "emotion",
    "gender",
    "nationality",
    "race",
    "sex",
    "акцент",
    "внешност",
    "возраст",
    "голос",
    "национальност",
    "пол ",
    "раса",
    "эмоци",
    "уверенно звуч",
)


def required_text(value: str, name: str, maximum: int = 4_000) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string", details={"field": name})
    result = value.strip()
    if not result:
        raise ValidationError(f"{name} is required", details={"field": name})
    if len(result) > maximum:
        raise ValidationError(
            f"{name} is too long",
            details={"field": name, "maximum": maximum},
        )
    return result


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return to_primitive(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_primitive(item) for item in value]
    return value


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalized_code(text: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return candidate or f"criterion_{canonical_hash(text)[:10]}"


def forbidden_criterion_terms(text: str) -> list[str]:
    lowered = f" {text.casefold()} "
    return sorted({term for term in FORBIDDEN_CRITERION_TERMS if term in lowered})


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    actor_id: str
    actor_role: ActorRole
    action: str
    entity_type: str
    entity_id: str
    metadata: dict[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        required_text(self.actor_id, "actor_id", 120)
        required_text(self.action, "action", 120)
        required_text(self.entity_type, "entity_type", 120)

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)
