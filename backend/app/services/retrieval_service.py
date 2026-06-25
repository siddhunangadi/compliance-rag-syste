from app.services.gemini_embedding_service import GeminiEmbeddingService
from app.services.pinecone_vector_service import PineconeVectorService


class RetrievalService:
    """Retrieve relevant chunks from the authenticated user's documents."""

    def __init__(self) -> None:
        self.embedding_service = GeminiEmbeddingService()
        self.vector_service = PineconeVectorService()

    def search(
        self,
        *,
        user_id: str,
        query: str,
        top_k: int,
    ) -> list[dict]:
        """Return the most relevant chunks for one user query."""
        query_embedding = self.embedding_service.embed_query(query)

        return self.vector_service.query_user_chunks(
            user_id=user_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )


retrieval_service = RetrievalService()