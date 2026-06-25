from app.services.text_chunking_service import TextChunkingService


def test_chunk_pages_preserves_page_numbers_and_global_chunk_order() -> None:
    service = TextChunkingService(chunk_size=20, chunk_overlap=5)

    chunks = service.chunk_pages(
        [
            {
                "page_number": 1,
                "text": "First page has compliance requirements.",
            },
            {
                "page_number": 2,
                "text": "Second page has retention requirements.",
            },
        ]
    )

    assert chunks
    assert [chunk["chunk_index"] for chunk in chunks] == list(range(len(chunks)))
    assert chunks[0]["page_number"] == 1
    assert any(chunk["page_number"] == 2 for chunk in chunks)
    assert all("content" in chunk for chunk in chunks)
