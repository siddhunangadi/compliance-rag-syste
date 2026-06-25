from __future__ import annotations

from pinecone import Pinecone

from app.core.config import get_settings


class PineconeVectorService:
    """Store and retrieve document chunk vectors in Pinecone."""

    def __init__(self) -> None:
        settings = get_settings()

        self.namespace = settings.pinecone_namespace
        self.client = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.client.Index(settings.pinecone_index_name)

    def upsert_document_chunks(
        self,
        *,
        document_id: str,
        user_id: str,
        file_name: str,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert one vector per stored document chunk."""
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk must have exactly one embedding.")

        vectors = []

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            vectors.append(
                {
                    "id": f"{document_id}:{chunk['chunk_index']}",
                    "values": embedding,
                    "metadata": {
                        "user_id": user_id,
                        "document_id": document_id,
                        "file_name": file_name,
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"],
                    },
                }
            )

        if vectors:
            self.index.upsert(
                vectors=vectors,
                namespace=self.namespace,
            )