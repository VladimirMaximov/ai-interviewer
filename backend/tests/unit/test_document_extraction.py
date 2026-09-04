from io import BytesIO
import unittest
from zipfile import ZipFile

from app.application.document_extraction import extract_document_text
from app.domain.hiring_context import (
    DocumentExtractionError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)


class DocumentExtractionTests(unittest.TestCase):
    def test_utf8_text_is_normalized_and_filename_is_sanitized(self) -> None:
        text, filename, media_type = extract_document_text(
            data="Python\tPostgreSQL\r\n\r\n\r\nDocker".encode(),
            filename="../private/vacancy.txt",
            media_type="text/plain; charset=utf-8",
        )

        self.assertEqual(text, "Python PostgreSQL\n\nDocker")
        self.assertEqual(filename, "vacancy.txt")
        self.assertEqual(media_type, "text/plain")

    def test_docx_paragraphs_are_extracted_without_external_binary(self) -> None:
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <w:document
                  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:p><w:r><w:t>Python developer</w:t></w:r></w:p>
                    <w:p><w:r><w:t>FastAPI</w:t></w:r></w:p>
                  </w:body>
                </w:document>""",
            )

        text, _, media_type = extract_document_text(
            data=buffer.getvalue(),
            filename="resume.docx",
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )

        self.assertEqual(text, "Python developer\nFastAPI")
        self.assertIn("wordprocessingml.document", media_type)

    def test_invalid_and_oversized_inputs_are_rejected(self) -> None:
        with self.assertRaises(DocumentExtractionError):
            extract_document_text(
                data=b"", filename="resume.txt", media_type="text/plain"
            )
        with self.assertRaises(DocumentExtractionError):
            extract_document_text(
                data=b"not-a-docx",
                filename="resume.docx",
                media_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
            )
        with self.assertRaises(UnsupportedDocumentError):
            extract_document_text(
                data=b"binary",
                filename="resume.exe",
                media_type="application/octet-stream",
            )
        with self.assertRaises(DocumentTooLargeError):
            extract_document_text(
                data=b"longer than allowed",
                filename="resume.txt",
                media_type="text/plain",
                maximum_bytes=5,
            )


if __name__ == "__main__":
    unittest.main()
