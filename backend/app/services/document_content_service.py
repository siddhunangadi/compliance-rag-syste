from __future__ import annotations

from app.services.supabase_client import get_supabase_service_client


class DocumentContentService:
    """Store and retrieve extracted document text."""

    def save_content(
        self,
        *,
        document_id: str,
        user_id: str,
        extracted_text: str,
    ) -> dict:
        """Create or replace extracted content for one document."""
        client = get_supabase_service_client()

        payload = {
            "document_id": document_id,
            "user_id": user_id,
            "extracted_text": extracted_text,
            "character_count": len(extracted_text),
        }

        result = (
            client.table("document_contents")
            .upsert(payload, on_conflict="document_id")
            .execute()
        )

        return result.data[0]

    def get_content(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> dict | None:
        """Return extracted content only if it belongs to the current user."""
        client = get_supabase_service_client()

        result = (
            client.table("document_contents")
            .select("*")
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        return result.data


document_content_service = DocumentContentService()
