from __future__ import annotations

import re
from typing import Any


class TextChunkingService:
    """Split extracted document text into overlapping retrieval chunks."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list[str]:
        """Return clean, overlapping chunks from extracted text."""
        normalized_text = self._normalize_text(text)

        if not normalized_text:
            return []

        if len(normalized_text) <= self.chunk_size:
            return [normalized_text]

        chunks: list[str] = []
        start = 0
        text_length = len(normalized_text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            if end < text_length:
                boundary = normalized_text.rfind("\n", start, end)

                if boundary == -1 or boundary <= start + (self.chunk_size // 2):
                    boundary = normalized_text.rfind(" ", start, end)

                if boundary != -1 and boundary > start:
                    end = boundary

            chunk = normalized_text[start:end].strip()

            if chunk:
                chunks.append(chunk)

            if end >= text_length:
                break

            start = max(end - self.chunk_overlap, start + 1)

        return chunks

    def chunk_pages(
        self,
        pages: list[dict[str, int | str]],
    ) -> list[dict[str, Any]]:
        """
        Chunk each extracted page independently.

        A chunk never crosses a PDF page boundary, so its page citation remains
        precise. Chunk indexes are assigned globally in document order.
        """
        page_chunks: list[dict[str, Any]] = []
        chunk_index = 0

        for page in pages:
            page_number = int(page["page_number"])
            page_text = str(page["text"])

            for content in self.chunk_text(page_text):
                page_chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "content": content,
                        "page_number": page_number,
                    }
                )
                chunk_index += 1

        return page_chunks

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize whitespace while preserving paragraph breaks."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
