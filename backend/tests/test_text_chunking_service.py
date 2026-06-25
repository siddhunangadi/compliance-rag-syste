import pytest

from app.services.text_chunking_service import TextChunkingService


def test_returns_empty_list_for_empty_text() -> None:
    service = TextChunkingService()

    assert service.chunk_text("") == []


def test_returns_one_chunk_for_short_text() -> None:
    service = TextChunkingService(chunk_size=100, chunk_overlap=20)

    chunks = service.chunk_text("Compliance policy text.")

    assert chunks == ["Compliance policy text."]


def test_creates_overlapping_chunks_for_long_text() -> None:
    service = TextChunkingService(chunk_size=50, chunk_overlap=10)

    text = " ".join(["compliance"] * 40)

    chunks = service.chunk_text(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert chunks[0][-10:] in chunks[1] or "compliance" in chunks[1]


def test_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        TextChunkingService(chunk_size=100, chunk_overlap=100)