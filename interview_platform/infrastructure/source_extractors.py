"""Compatibility export for the context-source extraction adapter."""

from interview_platform.application.source_processing import (
    SUPPORTED_FILE_SUFFIXES,
    extract_text_source,
)


__all__ = ["SUPPORTED_FILE_SUFFIXES", "extract_text_source"]
