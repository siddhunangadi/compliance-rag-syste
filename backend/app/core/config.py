from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Compliance RAG System"
    app_env: str = "development"

    frontend_url: str = "http://localhost:8501"
    allowed_origins: list[str] = []

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    gemini_api_key: str
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimension: int = 768
    gemini_generation_model: str = "gemini-2.5-flash"
    gemini_chat_model: str = "gemini-2.5-flash"

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

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> list[str]:
        """Accept comma-separated origins or a JSON-style list."""
        if value is None or value == "":
            return []

        if isinstance(value, str):
            return [
                origin.strip().rstrip("/")
                for origin in value.split(",")
                if origin.strip()
            ]

        if isinstance(value, list):
            return [
                str(origin).strip().rstrip("/")
                for origin in value
                if str(origin).strip()
            ]

        raise ValueError("ALLOWED_ORIGINS must be a comma-separated string or list.")

    @property
    def cors_origins(self) -> list[str]:
        """Return configured CORS origins, falling back to FRONTEND_URL."""
        origins = self.allowed_origins or [self.frontend_url]

        return list(
            dict.fromkeys(
                origin.strip().rstrip("/")
                for origin in origins
                if origin.strip()
            )
        )

    def validate_production_settings(self) -> None:
        """Fail fast when required production configuration is missing."""
        if self.app_env.lower() != "production":
            return

        required_values = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_ANON_KEY": self.supabase_anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": self.supabase_service_role_key,
            "GEMINI_API_KEY": self.gemini_api_key,
            "PINECONE_API_KEY": self.pinecone_api_key,
            "PINECONE_INDEX_NAME": self.pinecone_index_name,
        }

        missing = [
            name
            for name, value in required_values.items()
            if not value or not value.strip()
        ]

        if missing:
            missing_values = ", ".join(missing)
            raise RuntimeError(
                "Missing required production environment variables: "
                f"{missing_values}"
            )

        if not self.cors_origins:
            raise RuntimeError(
                "Set ALLOWED_ORIGINS or FRONTEND_URL for production CORS."
            )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
