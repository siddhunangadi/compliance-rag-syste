from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Create and cache the Supabase client used by the application."""
    settings = get_settings()

    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured.")

    if not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY is not configured.")

    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )