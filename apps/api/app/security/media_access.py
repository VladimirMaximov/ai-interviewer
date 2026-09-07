"""Short-lived access signatures for browser-native interview media requests."""

from __future__ import annotations

import hashlib
import hmac
import time
from uuid import UUID


def create_media_signature(
    vacancy_id: UUID,
    session_id: UUID,
    sequence: int,
    secret: str,
    *,
    expires_at: int | None = None,
) -> tuple[int, str]:
    current_window = int(time.time()) // 14_400
    expires = expires_at or (current_window + 2) * 14_400
    payload = f"{vacancy_id}:{session_id}:{sequence}:{expires}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return expires, signature


def verify_media_signature(
    vacancy_id: UUID,
    session_id: UUID,
    sequence: int,
    expires_at: int,
    signature: str,
    secret: str,
) -> bool:
    if expires_at < int(time.time()):
        return False
    _, expected = create_media_signature(
        vacancy_id,
        session_id,
        sequence,
        secret,
        expires_at=expires_at,
    )
    return hmac.compare_digest(signature, expected)
