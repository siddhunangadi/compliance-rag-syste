from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class UnsupportedDocumentTypeError(ValueError):
    """Raised when a file type is not supported for text extraction."""


class UnreadableDocumentError(ValueError):
    """Raised when a supported document cannot be safely read."""


@dataclass(frozen=True)
class ExtractedDocument:
    """Normalized extracted document content with page-level text."""

    full_text: str
    pages: list[dict[str, int | str]]

    @property
    def page_count(self) -> int:
        return len(self.pages)


class TextExtractionService:
    """Extract readable text and page metadata from supported documents."""

    SUPPORTED_EXTENSIONS = {".txt", ".pdf"}

    def extract_document(
        self,
        file_name: str,
        file_bytes: bytes,
    ) -> ExtractedDocument:
        """Extract text while preserving physical PDF page boundaries."""
        extension = Path(file_name).suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise UnsupportedDocumentTypeError(
                f"Text extraction is not supported for '{extension}' files yet."
            )

        if extension == ".txt":
            text = self._extract_txt(file_bytes)

            return ExtractedDocument(
                full_text=text,
                pages=[{"page_number": 1, "text": text}] if text else [],
            )

        if extension == ".pdf":
            return self._extract_pdf_document(file_bytes)

        raise UnsupportedDocumentTypeError(
            f"Text extraction is not supported for '{extension}' files yet."
        )

    def extract_text(self, file_name: str, file_bytes: bytes) -> str:
        """Backward-compatible text-only extraction API."""
        return self.extract_document(
            file_name=file_name,
            file_bytes=file_bytes,
        ).full_text

    @staticmethod
    def _extract_txt(file_bytes: bytes) -> str:
        """Extract text from a UTF-8 text file."""
        return file_bytes.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _extract_pdf_document(file_bytes: bytes) -> ExtractedDocument:
        """Extract PDF text while retaining each readable physical page."""
        try:
            reader = PdfReader(BytesIO(file_bytes))
        except (PdfReadError, OSError, ValueError, EOFError) as exc:
            raise UnreadableDocumentError(
                "This PDF could not be read. Please upload a valid, non-corrupted PDF."
            ) from exc

        pages: list[dict[str, int | str]] = []

        try:
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                cleaned_page_text = page_text.strip()

                if cleaned_page_text:
                    pages.append(
                        {
                            "page_number": page_number,
                            "text": cleaned_page_text,
                        }
                    )
        except (PdfReadError, OSError, ValueError, EOFError) as exc:
            raise UnreadableDocumentError(
                "This PDF could not be read. Please upload a valid, non-corrupted PDF."
            ) from exc

        full_text = "\n\n".join(
            str(page["text"])
            for page in pages
        ).strip()

        return ExtractedDocument(
            full_text=full_text,
            pages=pages,
        )
