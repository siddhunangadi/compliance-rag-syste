from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.gemini_embedding_service import GeminiEmbeddingService
from app.services.pinecone_vector_service import PineconeVectorService


class RetrievalService:
    """
    Converts a user query into an embedding and retrieves only that user's
    high-confidence, non-duplicate document chunks from Pinecone.
    """

    def __init__(self) -> None:
        settings = get_settings()

        self.min_retrieval_score = settings.min_retrieval_score
        self.embedding_service = GeminiEmbeddingService()
        self.vector_service = PineconeVectorService()

    def search(
        self,
        *,
        query: str,
        user_id: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve chunks for one user, then remove weak and duplicate evidence.

        We ask Pinecone for more than `top_k` because some results may be
        discarded after score filtering or duplicate suppression.
        """
        query_embedding = self.embedding_service.embed_query(query)

        candidate_limit = min(top_k * 3, 30)

        candidates = self.vector_service.query_user_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=candidate_limit,
        )

        strong_unique_results: list[dict[str, Any]] = []
        seen_chunk_ids: set[tuple[str, int]] = set()
        seen_contents: set[str] = set()

        for candidate in candidates:
            score = float(candidate["score"])

            if score < self.min_retrieval_score:
                continue

            document_id = str(candidate["document_id"])
            chunk_index = int(candidate["chunk_index"])
            chunk_id = (document_id, chunk_index)

            normalized_content = " ".join(
                str(candidate["content"]).lower().split()
            )

            if chunk_id in seen_chunk_ids:
                continue

            if normalized_content in seen_contents:
                continue

            seen_chunk_ids.add(chunk_id)
            seen_contents.add(normalized_content)
            strong_unique_results.append(candidate)

            if len(strong_unique_results) == top_k:
                break

        return strong_unique_results

    def retrieve(
        self,
        *,
        question: str,
        user_id: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Compatibility wrapper for code that uses the name `retrieve`."""
        return self.search(
            query=question,
            user_id=user_id,
            top_k=top_k,
        )


retrieval_service = RetrievalService()