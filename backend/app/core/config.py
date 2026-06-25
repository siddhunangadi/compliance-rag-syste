from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Compliance RAG System"
    app_env: str = "development"
    frontend_url: str = "http://localhost:8501"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    gemini_api_key: str
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimension: int = 768
    gemini_generation_model: str = "gemini-2.5-flash"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"

    pinecone_api_key: str
    pinecone_index_name: str
    pinecone_namespace: str = "documents"

    min_retrieval_score: float = 0.70

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()