from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


class UnsupportedDocumentTypeError(ValueError):
    """Raised when a file type is not supported for text extraction."""


class TextExtractionService:
    """Extract readable text from supported uploaded documents."""

    SUPPORTED_EXTENSIONS = {".txt", ".pdf"}

    def extract_text(self, file_name: str, file_bytes: bytes) -> str:
        """Extract text from an uploaded TXT or PDF file."""
        extension = Path(file_name).suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                f"Text extraction is not supported for '{extension}' files yet."
            )

        if extension == ".txt":
            return self._extract_txt(file_bytes)

        if extension == ".pdf":
            return self._extract_pdf(file_bytes)

        raise UnsupportedDocumentTypeError(
            f"Text extraction is not supported for '{extension}' files yet."
        )

    @staticmethod
    def _extract_txt(file_bytes: bytes) -> str:
        """Extract text from a UTF-8 text file."""
        return file_bytes.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        """Extract text from a PDF file."""
        reader = PdfReader(BytesIO(file_bytes))

        extracted_pages: list[str] = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            cleaned_page_text = page_text.strip()

            if cleaned_page_text:
                extracted_pages.append(cleaned_page_text)

        return "\n\n".join(extracted_pages).strip()