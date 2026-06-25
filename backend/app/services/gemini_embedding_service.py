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

    def _embed_one(
        self,
        *,
        text: str,
        task_type: str,
    ) -> list[float]:
        """Embed one text using the normal Gemini embedding request path."""
        response = self.client.models.embed_content(
            model=self.model_name,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension,
            ),
        )

        return response.embeddings[0].values

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed document chunks without using Gemini batch embedding."""
        return [
            self._embed_one(
                text=text,
                task_type="RETRIEVAL_DOCUMENT",
            )
            for text in texts
        ]

    def embed_query(self, text: str) -> list[float]:
        """Embed one user question for semantic retrieval."""
        return self._embed_one(
            text=text,
            task_type="RETRIEVAL_QUERY",
        )