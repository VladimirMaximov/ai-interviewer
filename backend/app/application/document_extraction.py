"""Bounded text extraction for uploaded vacancy and resume documents."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
import re
import unicodedata
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from app.domain.hiring_context import (
    DocumentExtractionError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)


MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 100_000

PLAIN_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
}
PDF_TYPES = {"application/pdf"}
DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
}


def _normalized_media_type(value: str) -> str:
    return value.partition(";")[0].strip().lower()


def _safe_filename(value: str) -> str:
    filename = PurePath(value.replace("\\", "/")).name.strip()
    if (
        not filename
        or len(filename) > 255
        or any(ord(character) < 32 for character in filename)
    ):
        raise DocumentExtractionError("document filename is invalid")
    return filename


def _extract_docx(data: bytes) -> str:
    try:
        with ZipFile(BytesIO(data)) as archive:
            document_xml = archive.read("word/document.xml")
    except (BadZipFile, KeyError, OSError) as error:
        raise DocumentExtractionError("DOCX document is malformed") from error
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError as error:
        raise DocumentExtractionError("DOCX XML is malformed") from error
    paragraphs: list[str] = []
    for paragraph in root.iter(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
    ):
        value = "".join(
            node.text or ""
            for node in paragraph.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            )
        )
        if value.strip():
            paragraphs.append(value)
    return "\n".join(paragraphs)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - packaging failure guard
        raise DocumentExtractionError(
            "PDF extraction dependency is not installed"
        ) from error
    try:
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as error:
        raise DocumentExtractionError(
            "PDF document is malformed or unreadable"
        ) from error


def _normalize_text(value: str, maximum_characters: int) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\x00", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[\t\f\v ]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    if not normalized:
        raise DocumentExtractionError("document contains no extractable text")
    if len(normalized) > maximum_characters:
        raise DocumentTooLargeError(
            f"extracted text exceeds {maximum_characters} characters"
        )
    return normalized


def extract_document_text(
    *,
    data: bytes,
    filename: str,
    media_type: str,
    maximum_bytes: int = MAX_DOCUMENT_BYTES,
    maximum_characters: int = MAX_EXTRACTED_CHARACTERS,
) -> tuple[str, str, str]:
    """Return normalized text, safe filename, and normalized media type."""
    if not data:
        raise DocumentExtractionError("document is empty")
    if len(data) > maximum_bytes:
        raise DocumentTooLargeError(f"document exceeds {maximum_bytes} bytes")

    safe_filename = _safe_filename(filename)
    normalized_type = _normalized_media_type(media_type)
    suffix = PurePath(safe_filename).suffix.lower()
    if normalized_type in PLAIN_TEXT_TYPES or suffix in {".txt", ".md"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DocumentExtractionError("text document must use UTF-8") from error
    elif normalized_type in DOCX_TYPES or suffix == ".docx":
        text = _extract_docx(data)
        normalized_type = next(iter(DOCX_TYPES))
    elif normalized_type in PDF_TYPES or suffix == ".pdf":
        text = _extract_pdf(data)
        normalized_type = "application/pdf"
    else:
        raise UnsupportedDocumentError(
            "supported document types are UTF-8 text, Markdown, DOCX, and PDF"
        )
    return (
        _normalize_text(text, maximum_characters),
        safe_filename,
        normalized_type,
    )
