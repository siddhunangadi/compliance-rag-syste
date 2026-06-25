from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.services.supabase_client import get_supabase_service_client

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024
DOCUMENTS_BUCKET = "documents"


class DocumentService:
    """Manage document storage and metadata."""

    def upload_document(
        self,
        user_id: str,
        uploaded_file: UploadFile,
        file_content: bytes,
    ) -> dict:
        """Upload a validated document and save its metadata."""
        file_name = uploaded_file.filename or "unnamed-file"
        extension = Path(file_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unsupported file type. Allowed types: "
                    "PDF, DOCX, TXT, CSV, XLSX."
                ),
            )

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty.",
            )

        if len(file_content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File is too large. Maximum allowed size is 20 MB.",
            )

        document_id = uuid4()
        storage_path = f"{user_id}/{document_id}/{file_name}"

        client = get_supabase_service_client()

        try:
            client.storage.from_(DOCUMENTS_BUCKET).upload(
                path=storage_path,
                file=file_content,
                file_options={
                    "content-type": uploaded_file.content_type
                    or "application/octet-stream",
                    "upsert": "false",
                },
            )

            response = (
                client.table("documents")
                .insert(
                    {
                        "id": str(document_id),
                        "user_id": user_id,
                        "file_name": file_name,
                        "storage_path": storage_path,
                        "file_size_bytes": len(file_content),
                        "mime_type": uploaded_file.content_type
                        or "application/octet-stream",
                        "status": "uploaded",
                        "error_message": None,
                    }
                )
                .execute()
            )

            return response.data[0]

        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to upload document. Please try again.",
            ) from exc

    def list_documents(self, user_id: str) -> list[dict]:
        """Return documents belonging to one user."""
        client = get_supabase_service_client()

        response = (
            client.table("documents")
            .select(
                "id, file_name, file_size_bytes, mime_type, status, "
                "error_message, page_count, created_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    def get_document(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> dict | None:
        """Return one document only if it belongs to the current user."""
        client = get_supabase_service_client()

        response = (
            client.table("documents")
            .select(
                "id, file_name, storage_path, status, error_message"
            )
            .eq("id", document_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        return response.data

    def delete_document_data(
        self,
        *,
        document_id: str,
        user_id: str,
        storage_path: str,
    ) -> None:
        """Delete document rows and stored file after vector cleanup."""
        client = get_supabase_service_client()

        try:
            (
                client.table("document_chunks")
                .delete()
                .eq("document_id", document_id)
                .eq("user_id", user_id)
                .execute()
            )

            (
                client.table("document_contents")
                .delete()
                .eq("document_id", document_id)
                .eq("user_id", user_id)
                .execute()
            )

            (
                client.table("documents")
                .delete()
                .eq("id", document_id)
                .eq("user_id", user_id)
                .execute()
            )

            client.storage.from_(DOCUMENTS_BUCKET).remove([storage_path])

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to delete document completely. Please try again.",
            ) from exc

    def update_document_status(
        self,
        *,
        document_id: str,
        user_id: str,
        status: str,
        error_message: str | None = None,
        page_count: int | None = None,
    ) -> dict:
        """Update processing information for one user-owned document."""
        client = get_supabase_service_client()

        payload: dict[str, str | int | None] = {
            "status": status,
            "error_message": error_message,
        }

        if page_count is not None:
            payload["page_count"] = page_count

        result = (
            client.table("documents")
            .update(payload)
            .eq("id", document_id)
            .eq("user_id", user_id)
            .execute()
        )

        return result.data[0]


document_service = DocumentService()