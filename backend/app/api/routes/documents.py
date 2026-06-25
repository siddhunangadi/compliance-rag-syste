from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_current_user
from app.models.auth import CurrentUser
from app.models.document import DocumentListItem, DocumentUploadResponse
from app.services.document_service import document_service
from app.services.document_content_service import DocumentContentService
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
    """Upload one supported document for the authenticated user."""
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

    except Exception as exc:
        
        document_service.update_document_status(
            document_id=document["id"],
            user_id=current_user.id,
            status="failed",
            error_message=f"Document text extraction failed: {str(exc)}",
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