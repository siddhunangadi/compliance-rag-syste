from typing import Any

from app.services.supabase_client import get_supabase_service_client


class DocumentChunkService:
    """Persist retrieval chunks for processed documents."""

    def replace_chunks(
        self,
        *,
        document_id: str,
        user_id: str,
        chunks: list[dict[str, Any]],
    ) -> list[dict]:
        """Replace all page-aware chunks for one document."""
        client = get_supabase_service_client()

        (
            client.table("document_chunks")
            .delete()
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .execute()
        )

        if not chunks:
            return []

        rows = [
            {
                "document_id": document_id,
                "user_id": user_id,
                "chunk_index": int(chunk["chunk_index"]),
                "content": str(chunk["content"]),
                "character_count": len(str(chunk["content"])),
                "page_number": int(chunk["page_number"]),
                "metadata": {
                    "chunk_strategy": "page_aware_character_overlap",
                    "page_number": int(chunk["page_number"]),
                },
            }
            for chunk in chunks
        ]

        response = client.table("document_chunks").insert(rows).execute()
        return response.data


document_chunk_service = DocumentChunkService()
