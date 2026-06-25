from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.services.supabase_client import (
    get_supabase_client,
    get_supabase_service_client,
)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
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
                "id, file_name, file_size_bytes, mime_type, "
                "status, page_count, created_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data


document_service = DocumentService()