from __future__ import annotations

import logging
from typing import Any

from app.services.document_chunk_service import document_chunk_service
from app.services.document_content_service import DocumentContentService
from app.services.document_service import DOCUMENTS_BUCKET, document_service
from app.services.gemini_embedding_service import GeminiEmbeddingService
from app.services.ingestion_job_service import ingestion_job_service
from app.services.pinecone_vector_service import PineconeVectorService
from app.services.supabase_client import get_supabase_service_client
from app.services.text_chunking_service import TextChunkingService
from app.services.text_extraction_service import (
    TextExtractionService,
    UnreadableDocumentError,
    UnsupportedDocumentTypeError,
)

logger = logging.getLogger(__name__)


class IngestionWorkerService:
    """Process one queued document ingestion job."""

    def process_job(
        self,
        *,
        job_id: str,
        document_id: str,
        user_id: str,
        file_name: str | None = None,
        storage_path: str | None = None,
    ) -> dict[str, Any]:
        """Process one document through page-aware ingestion."""
        processing_stage = "document lookup"

        try:
            if file_name is None or storage_path is None:
                document = document_service.get_document(
                    document_id=document_id,
                    user_id=user_id,
                )

                if document is None:
                    raise ValueError("Document not found for ingestion recovery.")

                file_name = document["file_name"]
                storage_path = document["storage_path"]

            ingestion_job_service.mark_processing(
                job_id=job_id,
                user_id=user_id,
            )

            document_service.update_document_status(
                document_id=document_id,
                user_id=user_id,
                status="processing",
                error_message=None,
            )

            processing_stage = "file download"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            client = get_supabase_service_client()
            file_bytes = client.storage.from_(DOCUMENTS_BUCKET).download(storage_path)

            processing_stage = "text extraction"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            extraction_service = TextExtractionService()
            extracted_document = extraction_service.extract_document(
                file_name=file_name,
                file_bytes=file_bytes,
            )

            if not extracted_document.full_text:
                raise UnreadableDocumentError(
                    "No readable text was found in this document. "
                    "Please upload a text-based document."
                )

            processing_stage = "content storage"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            content_service = DocumentContentService()
            content_service.save_content(
                document_id=document_id,
                user_id=user_id,
                extracted_text=extracted_document.full_text,
            )

            processing_stage = "text chunking"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            chunking_service = TextChunkingService()
            chunks = chunking_service.chunk_pages(extracted_document.pages)

            if not chunks:
                raise UnreadableDocumentError(
                    "No readable text was found in this document. "
                    "Please upload a text-based document."
                )

            processing_stage = "chunk storage"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            saved_chunks = document_chunk_service.replace_chunks(
                document_id=document_id,
                user_id=user_id,
                chunks=chunks,
            )

            processing_stage = "embedding generation"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            embedding_service = GeminiEmbeddingService()
            embeddings = embedding_service.embed_documents(
                [chunk["content"] for chunk in saved_chunks]
            )

            processing_stage = "vector indexing"
            ingestion_job_service.update_processing_stage(
                job_id=job_id,
                user_id=user_id,
                processing_stage=processing_stage,
            )

            vector_service = PineconeVectorService()
            vector_service.upsert_document_chunks(
                document_id=document_id,
                user_id=user_id,
                file_name=file_name,
                chunks=saved_chunks,
                embeddings=embeddings,
            )

            document = document_service.update_document_status(
                document_id=document_id,
                user_id=user_id,
                status="processed",
                error_message=None,
                page_count=extracted_document.page_count,
            )

            ingestion_job_service.mark_completed(
                job_id=job_id,
                user_id=user_id,
            )

            logger.info(
                "Ingestion completed: job_id=%s document_id=%s user_id=%s",
                job_id,
                document_id,
                user_id,
            )

            return document

        except (UnsupportedDocumentTypeError, UnreadableDocumentError) as exc:
            logger.warning(
                "Document ingestion rejected: job_id=%s document_id=%s "
                "user_id=%s stage=%s error=%s",
                job_id,
                document_id,
                user_id,
                processing_stage,
                exc,
            )
            error_message = str(exc)

        except Exception:
            logger.exception(
                "Ingestion failed: job_id=%s document_id=%s user_id=%s stage=%s",
                job_id,
                document_id,
                user_id,
                processing_stage,
            )
            error_message = f"Processing failed during {processing_stage}."

        document = document_service.update_document_status(
            document_id=document_id,
            user_id=user_id,
            status="failed",
            error_message=error_message,
        )

        ingestion_job_service.mark_failed(
            job_id=job_id,
            user_id=user_id,
            error_message=error_message,
            processing_stage=processing_stage,
        )

        return document


ingestion_worker_service = IngestionWorkerService()
