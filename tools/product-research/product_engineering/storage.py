"""Checkpoint storage for resumable long-running research jobs."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any


def slugify(value: str, *, fallback: str = "item") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:72] or fallback


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_text_atomic(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(data)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class StageStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str | Path) -> Path:
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Checkpoint path escapes the run directory")
        return candidate

    def load(self, relative: str | Path) -> Any:
        with self.path(relative).open("r", encoding="utf-8") as stream:
            return json.load(stream)

    def save(self, relative: str | Path, data: Any) -> Path:
        path = self.path(relative)
        write_json_atomic(path, data)
        return path

    def save_text(self, relative: str | Path, data: str) -> Path:
        path = self.path(relative)
        write_text_atomic(path, data)
        return path

    def cached(self, relative: str | Path, producer: Callable[[], Any]) -> Any:
        path = self.path(relative)
        if path.exists():
            return self.load(relative)
        data = producer()
        self.save(relative, data)
        return data
