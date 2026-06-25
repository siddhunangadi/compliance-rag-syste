from app.services.document_content_service import DocumentContentService
from app.services.document_service import document_service
from app.services.gemini_embedding_service import GeminiEmbeddingService
from app.services.ingestion_job_service import ingestion_job_service
from app.services.ingestion_worker_service import IngestionWorkerService
from app.services.pinecone_vector_service import PineconeVectorService
from app.services.text_chunking_service import TextChunkingService
from app.services.text_extraction_service import TextExtractionService

TEST_JOB_ID = "00000000-0000-0000-0000-000000000101"
TEST_DOCUMENT_ID = "00000000-0000-0000-0000-000000000102"
TEST_USER_ID = "00000000-0000-0000-0000-000000000103"


class FakeStorageBucket:
    def download(self, storage_path: str) -> bytes:
        assert storage_path == (
            f"{TEST_USER_ID}/{TEST_DOCUMENT_ID}/recovered-policy.txt"
        )
        return b"Recovered policy text."


class FakeStorage:
    def from_(self, bucket_name: str) -> FakeStorageBucket:
        assert bucket_name == "documents"
        return FakeStorageBucket()


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.storage = FakeStorage()


def recovered_document() -> dict:
    return {
        "id": TEST_DOCUMENT_ID,
        "user_id": TEST_USER_ID,
        "file_name": "recovered-policy.txt",
        "storage_path": (
            f"{TEST_USER_ID}/{TEST_DOCUMENT_ID}/recovered-policy.txt"
        ),
        "file_size_bytes": 22,
        "mime_type": "text/plain",
        "status": "uploaded",
        "error_message": None,
        "page_count": None,
        "created_at": "2026-06-25T00:00:00+00:00",
    }


def processed_document() -> dict:
    document = recovered_document()
    document["status"] = "processed"
    return document


def test_recovery_loads_document_metadata_and_processes_job(monkeypatch) -> None:
    worker = IngestionWorkerService()

    fake_client = FakeSupabaseClient()
    status_updates: list[dict] = []
    processing_calls: list[dict] = []
    stage_updates: list[dict] = []
    completed_calls: list[dict] = []
    saved_content_calls: list[dict] = []
    indexed_calls: list[dict] = []

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: recovered_document(),
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "mark_processing",
        lambda job_id, user_id: processing_calls.append(
            {
                "job_id": job_id,
                "user_id": user_id,
            }
        ),
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "update_processing_stage",
        lambda job_id, user_id, processing_stage: stage_updates.append(
            {
                "job_id": job_id,
                "user_id": user_id,
                "processing_stage": processing_stage,
            }
        ),
    )

    def fake_update_document_status(**kwargs) -> dict:
        status_updates.append(kwargs)

        if kwargs["status"] == "processed":
            return processed_document()

        return recovered_document()

    monkeypatch.setattr(
        document_service,
        "update_document_status",
        fake_update_document_status,
    )

    monkeypatch.setattr(
        "app.services.ingestion_worker_service.get_supabase_service_client",
        lambda: fake_client,
    )

    monkeypatch.setattr(
        TextExtractionService,
        "extract_text",
        lambda self, file_name, file_bytes: "Recovered policy text.",
    )

    def fake_save_content(
        self,
        *,
        document_id: str,
        user_id: str,
        extracted_text: str,
    ) -> dict:
        saved_content_calls.append(
            {
                "document_id": document_id,
                "user_id": user_id,
                "extracted_text": extracted_text,
            }
        )
        return {
            "document_id": document_id,
            "user_id": user_id,
            "content": extracted_text,
        }

    monkeypatch.setattr(
        DocumentContentService,
        "save_content",
        fake_save_content,
    )

    monkeypatch.setattr(
        TextChunkingService,
        "chunk_text",
        lambda self, text: ["Recovered policy text."],
    )

    monkeypatch.setattr(
        "app.services.ingestion_worker_service.document_chunk_service.replace_chunks",
        lambda document_id, user_id, chunks: [
            {
                "document_id": document_id,
                "user_id": user_id,
                "chunk_index": chunks[0]["chunk_index"],
                "content": chunks[0]["content"],
                "character_count": len(chunks[0]["content"]),
                "page_number": chunks[0]["page_number"],
                "metadata": {
                    "chunk_strategy": "page_aware_character_overlap",
                    "page_number": chunks[0]["page_number"],
                },
            }
        ],
    )

    monkeypatch.setattr(
        GeminiEmbeddingService,
        "embed_documents",
        lambda self, texts: [[0.1] * 768 for _ in texts],
    )

    def fake_upsert_document_chunks(self, **kwargs) -> None:
        indexed_calls.append(kwargs)

    monkeypatch.setattr(
        PineconeVectorService,
        "upsert_document_chunks",
        fake_upsert_document_chunks,
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "mark_completed",
        lambda job_id, user_id: completed_calls.append(
            {
                "job_id": job_id,
                "user_id": user_id,
            }
        ),
    )

    result = worker.process_job(
        job_id=TEST_JOB_ID,
        document_id=TEST_DOCUMENT_ID,
        user_id=TEST_USER_ID,
    )

    assert result["status"] == "processed"

    assert processing_calls == [
        {
            "job_id": TEST_JOB_ID,
            "user_id": TEST_USER_ID,
        }
    ]

    assert [item["processing_stage"] for item in stage_updates] == [
        "file download",
        "text extraction",
        "content storage",
        "text chunking",
        "chunk storage",
        "embedding generation",
        "vector indexing",
    ]

    assert status_updates == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
            "status": "processing",
            "error_message": None,
        },
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
            "status": "processed",
            "error_message": None,
            "page_count": 1,
        },
    ]

    assert saved_content_calls == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
            "extracted_text": "Recovered policy text.",
        }
    ]

    assert indexed_calls[0]["document_id"] == TEST_DOCUMENT_ID
    assert indexed_calls[0]["user_id"] == TEST_USER_ID
    assert indexed_calls[0]["file_name"] == "recovered-policy.txt"
    indexed_chunk = indexed_calls[0]["chunks"][0]
    assert indexed_chunk["chunk_index"] == 0
    assert indexed_chunk["content"] == "Recovered policy text."
    assert indexed_chunk["page_number"] == 1
    assert indexed_calls[0]["embeddings"] == [[0.1] * 768]

    assert completed_calls == [
        {
            "job_id": TEST_JOB_ID,
            "user_id": TEST_USER_ID,
        }
    ]