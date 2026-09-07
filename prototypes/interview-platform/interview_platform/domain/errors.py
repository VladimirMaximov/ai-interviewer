"""Public domain errors with stable codes for delivery adapters."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base error that is safe to map to a public response."""

    code = "domain_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(DomainError):
    code = "validation_error"


class NotFoundError(DomainError):
    code = "not_found"


class ConflictError(DomainError):
    code = "state_conflict"


class AssessmentProviderError(DomainError):
    """The configured assessment model could not be reached or used."""

    code = "assessment_provider_error"


class AssessmentOutputError(DomainError):
    """The assessment model returned output that failed local validation."""

    code = "assessment_output_error"
