"""Application-owned normalization for trusted manager context sources."""

from __future__ import annotations

import re
from pathlib import PurePath

from interview_platform.domain.errors import ValidationError
from interview_platform.domain.hiring import canonical_hash, new_id


SUPPORTED_FILE_SUFFIXES = {".txt", ".md", ".markdown"}


def extract_text_source(
    *,
    text: str | bytes,
    display_name: str,
    source_type: str,
    max_bytes: int = 1_000_000,
    max_chars: int = 50_000,
) -> tuple[str, str, tuple[dict, ...]]:
    """Decode and fragment input as data, without treating it as instructions."""

    if isinstance(text, bytes):
        if len(text) > max_bytes:
            raise ValidationError("context source is too large", details={"maximum": max_bytes})
        if source_type == "file":
            suffix = PurePath(display_name).suffix.lower()
            if suffix not in SUPPORTED_FILE_SUFFIXES:
                raise ValidationError(
                    "unsupported context file format",
                    details={"supported": sorted(SUPPORTED_FILE_SUFFIXES)},
                )
        try:
            decoded = text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("context file must be UTF-8") from exc
    elif isinstance(text, str):
        decoded = text
        if len(decoded.encode("utf-8")) > max_bytes:
            raise ValidationError("context source is too large", details={"maximum": max_bytes})
    else:
        raise ValidationError("context source must be text")

    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValidationError("context source is empty")
    if len(normalized) > max_chars:
        raise ValidationError("context source is too long", details={"maximum": max_chars})

    fragments: list[dict] = []
    cursor = 0
    chunks = [item.strip(" \t-*#") for item in re.split(r"\n+|(?<=[.!?])\s+", normalized)]
    for chunk in chunks:
        if not chunk:
            continue
        start = normalized.find(chunk, cursor)
        if start < 0:
            start = normalized.find(chunk)
        end = start + len(chunk)
        cursor = max(cursor, end)
        fragments.append(
            {
                "id": new_id(),
                "position": len(fragments) + 1,
                "text": chunk,
                "start_offset": start,
                "end_offset": end,
                "classification": "verified_manager_input",
            }
        )
    if not fragments:
        raise ValidationError("context source has no readable fragments")
    return normalized, canonical_hash(normalized), tuple(fragments[:100])
