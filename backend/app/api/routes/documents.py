import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from postgrest.exceptions import APIError

from app.api.dependencies import get_current_user
from app.models.auth import CurrentUser
from app.models.document import (
    DocumentListItem,
    DocumentUploadResponse,
    IngestionStatusResponse,
)
from app.services.document_service import document_service
from app.services.ingestion_job_service import (
    RetryNotAllowedError,
    ingestion_job_service,
)
from app.services.ingestion_worker_service import ingestion_worker_service
from app.services.pinecone_vector_service import PineconeVectorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


def process_document_ingestion(
    *,
    job_id: str,
    document_id: str,
    user_id: str,
    file_name: str,
    storage_path: str,
) -> None:
    """Run document ingestion after the HTTP response has been returned."""
    try:
        ingestion_worker_service.process_job(
            job_id=job_id,
            document_id=document_id,
            user_id=user_id,
            file_name=file_name,
            storage_path=storage_path,
        )
    except Exception:
        logger.exception(
            "Unhandled background ingestion error: job_id=%s document_id=%s user_id=%s",
            job_id,
            document_id,
            user_id,
        )


def queue_document_ingestion(
    *,
    background_tasks: BackgroundTasks,
    document: dict,
    user_id: str,
    is_retry: bool = False,
) -> None:
    """Create an ingestion job and schedule its background worker."""
    if is_retry:
        job = ingestion_job_service.create_retry_job(
            document_id=document["id"],
            user_id=user_id,
        )
    else:
        job = ingestion_job_service.create_job(
            document_id=document["id"],
            user_id=user_id,
        )

    background_tasks.add_task(
        process_document_ingestion,
        job_id=job["id"],
        document_id=document["id"],
        user_id=user_id,
        file_name=document["file_name"],
        storage_path=document["storage_path"],
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a compliance document",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Upload one document and queue ingestion."""
    file_content = await file.read()

    document = document_service.upload_document(
        user_id=current_user.id,
        uploaded_file=file,
        file_content=file_content,
    )

    try:
        queue_document_ingestion(
            background_tasks=background_tasks,
            document=document,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.exception(
            "Could not queue ingestion job: document_id=%s user_id=%s",
            document["id"],
            current_user.id,
        )

        document_service.update_document_status(
            document_id=document["id"],
            user_id=current_user.id,
            status="failed",
            error_message="Document upload succeeded, but processing could not be queued.",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload succeeded, but processing could not be queued.",
        ) from exc

    return DocumentUploadResponse(**document)


@router.post(
    "/{document_id}/retry",
    response_model=DocumentUploadResponse,
    summary="Retry failed document ingestion",
)
def retry_document_ingestion(
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Queue a policy-checked retry for one failed user-owned document."""
    document = document_service.get_document(
        document_id=document_id,
        user_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.get("status") != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed documents can be retried.",
        )

    try:
        queue_document_ingestion(
            background_tasks=background_tasks,
            document=document,
            user_id=current_user.id,
            is_retry=True,
        )

    except RetryNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except APIError as exc:
        if exc.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This document already has an active ingestion job.",
            ) from exc

        logger.exception(
            "Could not queue retry ingestion job: document_id=%s user_id=%s",
            document_id,
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document retry could not be queued.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "Could not queue retry ingestion job: document_id=%s user_id=%s",
            document_id,
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document retry could not be queued.",
        ) from exc

    document = document_service.update_document_status(
        document_id=document_id,
        user_id=current_user.id,
        status="uploaded",
        error_message=None,
    )

    return DocumentUploadResponse(**document)


@router.get(
    "/{document_id}/ingestion-status",
    response_model=IngestionStatusResponse,
    summary="Get latest ingestion status",
)
def get_ingestion_status(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> IngestionStatusResponse:
    """Return the newest ingestion job for one user-owned document."""
    document = document_service.get_document(
        document_id=document_id,
        user_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    job = ingestion_job_service.get_latest_job_for_document(
        document_id=document_id,
        user_id=current_user.id,
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ingestion job found for this document.",
        )

    return IngestionStatusResponse(**job)


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


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my compliance documents",
)
def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete one user-owned document and all of its derived data."""
    document = document_service.get_document(
        document_id=document_id,
        user_id=current_user.id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    vector_service = PineconeVectorService()

    vector_service.delete_document_vectors(
        document_id=document_id,
        user_id=current_user.id,
    )

    document_service.delete_document_data(
        document_id=document_id,
        user_id=current_user.id,
        storage_path=document["storage_path"],
    )