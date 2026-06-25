from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    """Response returned after a document upload or retry is queued."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    error_message: str | None = None
    page_count: int | None = None
    created_at: datetime


class DocumentListItem(BaseModel):
    """Document summary shown in the user's document list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    file_size_bytes: int
    mime_type: str
    status: str
    error_message: str | None = None
    page_count: int | None = None
    created_at: datetime


class IngestionStatusResponse(BaseModel):
    """Latest ingestion job state for one user-owned document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: str
    attempt_count: int = Field(ge=0)
    processing_stage: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime