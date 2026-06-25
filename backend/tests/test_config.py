import pytest

from app.core.config import Settings


def test_cors_origins_parses_comma_separated_origins() -> None:
    settings = Settings(
        gemini_api_key="gemini-key",
        pinecone_api_key="pinecone-key",
        pinecone_index_name="compliance-index",
        allowed_origins=(
            "http://localhost:8501, https://app.example.com/, "
            "http://localhost:8501"
        ),
    )

    assert settings.cors_origins == [
        "http://localhost:8501",
        "https://app.example.com",
    ]


def test_cors_origins_falls_back_to_frontend_url() -> None:
    settings = Settings(
        gemini_api_key="gemini-key",
        pinecone_api_key="pinecone-key",
        pinecone_index_name="compliance-index",
        frontend_url="http://localhost:8501/",
    )

    assert settings.cors_origins == ["http://localhost:8501"]


def test_production_settings_reject_missing_required_values() -> None:
    settings = Settings(
        app_env="production",
        supabase_url="",
        supabase_anon_key="",
        supabase_service_role_key="",
        gemini_api_key="gemini-key",
        pinecone_api_key="pinecone-key",
        pinecone_index_name="compliance-index",
    )

    with pytest.raises(RuntimeError) as exc_info:
        settings.validate_production_settings()

    assert str(exc_info.value) == (
        "Missing required production environment variables: "
        "SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY"
    )


def test_production_settings_accepts_complete_configuration() -> None:
    settings = Settings(
        app_env="production",
        frontend_url="https://app.example.com",
        supabase_url="https://project.supabase.co",
        supabase_anon_key="anon-key",
        supabase_service_role_key="service-role-key",
        gemini_api_key="gemini-key",
        pinecone_api_key="pinecone-key",
        pinecone_index_name="compliance-index",
    )

    settings.validate_production_settings()
