"""Deterministic states for a consent-first interview session."""

from enum import StrEnum


class SessionStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EXPIRED = "expired"
    REVOKED = "revoked"


def begin_session(status: SessionStatus, consented: bool) -> SessionStatus:
    """Start only a consented, active session."""
    if status is not SessionStatus.NOT_STARTED or not consented:
        raise ValueError("session cannot begin")
    return SessionStatus.IN_PROGRESS


def submit_session(status: SessionStatus, required_answers_complete: bool) -> SessionStatus:
    """Submit only a complete in-progress interview."""
    if status is not SessionStatus.IN_PROGRESS or not required_answers_complete:
        raise ValueError("session cannot be submitted")
    return SessionStatus.SUBMITTED
