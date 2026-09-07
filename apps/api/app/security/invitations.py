"""Store invitation secrets only as SHA-256 digests."""

import hashlib
import secrets


def create_invitation_secret() -> str:
    return secrets.token_urlsafe(32)


def digest_invitation_secret(secret: str) -> str:
    if not secret:
        raise ValueError("invitation secret is required")
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()
