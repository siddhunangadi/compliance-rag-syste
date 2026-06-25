from app.services.supabase_client import get_supabase_service_client


class DocumentChunkService:
    """Persist retrieval chunks for processed documents."""

    def replace_chunks(
        self,
        *,
        document_id: str,
        user_id: str,
        chunks: list[str],
    ) -> list[dict]:
        """Replace all chunks for one document atomically enough for ingestion."""
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
                "chunk_index": index,
                "content": chunk,
                "character_count": len(chunk),
                "metadata": {
                    "chunk_strategy": "character_overlap",
                },
            }
            for index, chunk in enumerate(chunks)
        ]

        response = client.table("document_chunks").insert(rows).execute()
        return response.data


document_chunk_service = DocumentChunkService()