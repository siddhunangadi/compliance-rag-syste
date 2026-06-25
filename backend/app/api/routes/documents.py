from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_current_user
from app.models.auth import CurrentUser
from app.models.document import DocumentListItem, DocumentUploadResponse
from app.services.document_chunk_service import document_chunk_service
from app.services.document_content_service import DocumentContentService
from app.services.document_service import document_service
from app.services.text_chunking_service import TextChunkingService
from app.services.text_extraction_service import (
    TextExtractionService,
    UnsupportedDocumentTypeError,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a compliance document",
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Upload, extract, chunk, and store one supported document."""
    file_content = await file.read()

    document = document_service.upload_document(
        user_id=current_user.id,
        uploaded_file=file,
        file_content=file_content,
    )

    document_service.update_document_status(
        document_id=document["id"],
        user_id=current_user.id,
        status="processing",
    )

    extraction_service = TextExtractionService()
    content_service = DocumentContentService()
    chunking_service = TextChunkingService()

    try:
        extracted_text = extraction_service.extract_text(
            file_name=file.filename or "uploaded_document",
            file_bytes=file_content,
        )

        content_service.save_content(
            document_id=document["id"],
            user_id=current_user.id,
            extracted_text=extracted_text,
        )

        chunks = chunking_service.chunk_text(extracted_text)

        document_chunk_service.replace_chunks(
            document_id=document["id"],
            user_id=current_user.id,
            chunks=chunks,
        )

        document = document_service.update_document_status(
            document_id=document["id"],
            user_id=current_user.id,
            status="processed",
        )

    except UnsupportedDocumentTypeError as exc:
        document = document_service.update_document_status(
            document_id=document["id"],
            user_id=current_user.id,
            status="uploaded",
            error_message=str(exc),
        )

    except Exception:
        document = document_service.update_document_status(
            document_id=document["id"],
            user_id=current_user.id,
            status="failed",
            error_message="Document text extraction failed.",
        )

    return DocumentUploadResponse(**document)


@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List my documents",
)
def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DocumentListItem]:
    """List documents owned by the authenticated user."""
    documents = document_service.list_documents(current_user.id)
    return [DocumentListItem(**document) for document in documents]