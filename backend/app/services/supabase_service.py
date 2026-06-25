from supabase import Client

from app.services.supabase_client import get_supabase_client


class SupabaseService:
    """Service layer for Supabase operations."""

    def __init__(self, client: Client | None = None) -> None:
        self.client = client or get_supabase_client()

    def check_connection(self) -> bool:
        """Return True when the documents table can be queried."""
        response = self.client.table("documents").select("id").limit(1).execute()

        return response.data is not None