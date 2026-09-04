"""Credential checks for the two manager delivery styles."""

from __future__ import annotations

import base64
import binascii
import hmac


def manager_api_authorized(environ: dict, expected_key: str) -> bool:
    return role_api_authorized(environ, expected_key, header="HTTP_X_MANAGER_KEY")


def recruiter_api_authorized(environ: dict, expected_key: str) -> bool:
    return role_api_authorized(environ, expected_key, header="HTTP_X_RECRUITER_KEY")


def role_api_authorized(environ: dict, expected_key: str, *, header: str) -> bool:
    provided = str(environ.get(header, ""))
    return bool(provided) and hmac.compare_digest(provided, expected_key)


def manager_basic_authorized(environ: dict, expected_key: str) -> bool:
    return role_basic_authorized(environ, "manager", expected_key)


def recruiter_basic_authorized(environ: dict, expected_key: str) -> bool:
    return role_basic_authorized(environ, "recruiter", expected_key)


def role_basic_authorized(environ: dict, username_expected: str, key_expected: str) -> bool:
    header = str(environ.get("HTTP_AUTHORIZATION", ""))
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    username, separator, password = decoded.partition(":")
    return bool(separator) and hmac.compare_digest(username, username_expected) and hmac.compare_digest(
        password,
        key_expected,
    )


def same_origin(environ: dict) -> bool:
    """Require browser writes to originate from this host."""

    origin = str(environ.get("HTTP_ORIGIN", ""))
    host = str(environ.get("HTTP_HOST", ""))
    scheme = str(environ.get("wsgi.url_scheme", "http"))
    return bool(origin and host) and hmac.compare_digest(origin, f"{scheme}://{host}")
