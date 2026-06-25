from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Response returned after a document is uploaded."""

    id: UUID
    file_name: str
    storage_path: str
    file_size_bytes: int
    mime_type: str
    status: str
    created_at: datetime


class DocumentListItem(BaseModel):
    """A document visible in the user's dashboard."""

    id: UUID
    file_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    page_count: int | None = None
    created_at: datetime