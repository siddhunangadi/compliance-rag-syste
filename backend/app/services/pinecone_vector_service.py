from __future__ import annotations

from typing import Any

from pinecone import Pinecone

from app.core.config import get_settings


class PineconeVectorService:
    """Store and retrieve document chunk vectors in Pinecone."""

    def __init__(self) -> None:
        settings = get_settings()

        self.namespace = settings.pinecone_namespace
        self._client: Pinecone | None = None
        self._index: Any | None = None

    @property
    def client(self) -> Pinecone:
        """Create the Pinecone client only when vector work is requested."""
        if self._client is None:
            settings = get_settings()
            self._client = Pinecone(api_key=settings.pinecone_api_key)

        return self._client

    @property
    def index(self) -> Any:
        """Resolve the Pinecone index only when a vector operation needs it."""
        if self._index is None:
            settings = get_settings()
            self._index = self.client.Index(settings.pinecone_index_name)

        return self._index

    def upsert_document_chunks(
        self,
        *,
        document_id: str,
        user_id: str,
        file_name: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert one vector per stored page-aware document chunk."""
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding.")

        vectors: list[dict[str, Any]] = []

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            vectors.append(
                {
                    "id": f"{document_id}:{chunk['chunk_index']}",
                    "values": embedding,
                    "metadata": {
                        "user_id": user_id,
                        "document_id": document_id,
                        "file_name": file_name,
                        "chunk_index": int(chunk["chunk_index"]),
                        "page_number": int(chunk["page_number"]),
                        "content": chunk["content"],
                    },
                }
            )

        if vectors:
            self.index.upsert(
                vectors=vectors,
                namespace=self.namespace,
            )

    def delete_document_vectors(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> None:
        """Delete vectors belonging to one user-owned document."""
        self.index.delete(
            namespace=self.namespace,
            filter={
                "document_id": {"$eq": document_id},
                "user_id": {"$eq": user_id},
            },
        )

    def query_user_chunks(
        self,
        *,
        user_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Search only the authenticated user's document chunks."""
        response = self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=self.namespace,
            filter={
                "user_id": {"$eq": user_id},
            },
            include_metadata=True,
        )

        results: list[dict[str, Any]] = []

        for match in response.matches:
            metadata = match.metadata or {}

            results.append(
                {
                    "document_id": metadata["document_id"],
                    "file_name": metadata["file_name"],
                    "chunk_index": metadata["chunk_index"],
                    "page_number": metadata.get("page_number", 1),
                    "content": metadata["content"],
                    "score": float(match.score),
                }
            )

        return results


pinecone_vector_service = PineconeVectorService()
