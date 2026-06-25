from app.services.retrieval_service import RetrievalService


def build_service_without_init() -> RetrievalService:
    """
    Avoid constructing real Gemini and Pinecone clients in unit tests.
    """
    service = RetrievalService.__new__(RetrievalService)
    service.min_retrieval_score = 0.75
    return service


def test_search_discards_low_score_results_and_keeps_top_k(monkeypatch) -> None:
    service = build_service_without_init()

    class FakeEmbeddingService:
        def embed_query(self, query: str) -> list[float]:
            assert query == "What is the remote work policy?"
            return [0.1, 0.2, 0.3]

    class FakeVectorService:
        def query_user_chunks(
            self,
            *,
            user_id: str,
            query_embedding: list[float],
            top_k: int,
        ) -> list[dict]:
            assert user_id == "test-user-123"
            assert query_embedding == [0.1, 0.2, 0.3]
            assert top_k == 15

            return [
                {
                    "document_id": "doc-1",
                    "file_name": "Remote Work Policy.pdf",
                    "chunk_index": 0,
                    "content": "Employees may work remotely two days per week.",
                    "score": 0.91,
                },
                {
                    "document_id": "doc-2",
                    "file_name": "Laptop Policy.pdf",
                    "chunk_index": 1,
                    "content": "Employees must lock laptops when unattended.",
                    "score": 0.42,
                },
                {
                    "document_id": "doc-3",
                    "file_name": "Security Policy.pdf",
                    "chunk_index": 2,
                    "content": "VPN access is required for remote connections.",
                    "score": 0.82,
                },
            ]

    service.embedding_service = FakeEmbeddingService()
    service.vector_service = FakeVectorService()

    results = service.search(
        query="What is the remote work policy?",
        user_id="test-user-123",
        top_k=5,
    )

    assert len(results) == 2
    assert [result["score"] for result in results] == [0.91, 0.82]


def test_search_removes_duplicate_chunk_ids_and_duplicate_content() -> None:
    service = build_service_without_init()

    class FakeEmbeddingService:
        def embed_query(self, query: str) -> list[float]:
            return [0.1]

    class FakeVectorService:
        def query_user_chunks(
            self,
            *,
            user_id: str,
            query_embedding: list[float],
            top_k: int,
        ) -> list[dict]:
            return [
                {
                    "document_id": "doc-1",
                    "file_name": "Policy A.pdf",
                    "chunk_index": 0,
                    "content": "Employees must use MFA for remote access.",
                    "score": 0.95,
                },
                {
                    "document_id": "doc-1",
                    "file_name": "Policy A.pdf",
                    "chunk_index": 0,
                    "content": "Employees must use MFA for remote access.",
                    "score": 0.94,
                },
                {
                    "document_id": "doc-2",
                    "file_name": "Policy B.pdf",
                    "chunk_index": 3,
                    "content": "  Employees   must use MFA for remote access.  ",
                    "score": 0.90,
                },
                {
                    "document_id": "doc-3",
                    "file_name": "Policy C.pdf",
                    "chunk_index": 1,
                    "content": "Managers must approve exceptions to remote work.",
                    "score": 0.88,
                },
            ]

    service.embedding_service = FakeEmbeddingService()
    service.vector_service = FakeVectorService()

    results = service.search(
        query="What are the remote access requirements?",
        user_id="test-user-123",
        top_k=5,
    )

    assert len(results) == 2
    assert results[0]["document_id"] == "doc-1"
    assert results[1]["document_id"] == "doc-3"


def test_search_returns_empty_when_every_result_is_below_threshold() -> None:
    service = build_service_without_init()

    class FakeEmbeddingService:
        def embed_query(self, query: str) -> list[float]:
            return [0.1]

    class FakeVectorService:
        def query_user_chunks(
            self,
            *,
            user_id: str,
            query_embedding: list[float],
            top_k: int,
        ) -> list[dict]:
            return [
                {
                    "document_id": "doc-1",
                    "file_name": "Policy.pdf",
                    "chunk_index": 0,
                    "content": "Employees must wear ID badges.",
                    "score": 0.50,
                }
            ]

    service.embedding_service = FakeEmbeddingService()
    service.vector_service = FakeVectorService()

    results = service.search(
        query="What is the parental leave policy?",
        user_id="test-user-123",
        top_k=5,
    )

    assert results == []