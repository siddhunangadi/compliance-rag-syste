from __future__ import annotations

from google import genai
from google.genai import types

from app.core.config import get_settings


class GeminiEmbeddingService:
    """Create Gemini embeddings for document chunks and user queries."""

    def __init__(self) -> None:
        settings = get_settings()

        self.model_name = settings.gemini_embedding_model
        self.dimension = settings.gemini_embedding_dimension
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document chunks for semantic retrieval."""
        if not texts:
            return []

        response = self.client.models.embed_content(
            model=self.model_name,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=self.dimension,
            ),
        )

        return [embedding.values for embedding in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        """Embed a user question for semantic search."""
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self.dimension,
            ),
        )

        return response.embeddings[0].values