from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.supabase_client import get_supabase_service_client

STALE_PROCESSING_AFTER_MINUTES = 10
MAX_RETRY_JOBS_PER_DOCUMENT = 3
RETRY_COOLDOWN_SECONDS = 30

JOB_SELECT_COLUMNS = (
    "id, document_id, user_id, status, attempt_count, error_message, "
    "processing_stage, started_at, completed_at, created_at, updated_at"
)


class RetryNotAllowedError(Exception):
    """Raised when a document retry violates ingestion retry policy."""


class IngestionJobService:
    """Create and manage document ingestion jobs."""

    def create_job(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Create one queued ingestion job for a document."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .insert(
                {
                    "document_id": document_id,
                    "user_id": user_id,
                    "status": "queued",
                    "attempt_count": 0,
                    "error_message": None,
                    "processing_stage": "queued",
                    "started_at": None,
                    "completed_at": None,
                }
            )
            .execute()
        )

        return response.data[0]

    def get_job(
        self,
        *,
        job_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Return one job only when it belongs to the current user."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .select(JOB_SELECT_COLUMNS)
            .eq("id", job_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        return response.data

    def get_latest_job_for_document(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Return the newest ingestion job for one user-owned document."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .select(JOB_SELECT_COLUMNS)
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )

        return response.data

    def get_jobs_for_document(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return all ingestion jobs for one user-owned document."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .select(JOB_SELECT_COLUMNS)
            .eq("document_id", document_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data

    def create_retry_job(
        self,
        *,
        document_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Create a retry job only when retry policy permits it.

        Policy:
        - At most 3 retry jobs after the original ingestion job.
        - No retry while a queued or processing job already exists.
        - A retry must wait 30 seconds after the latest job was created.
        """
        jobs = self.get_jobs_for_document(
            document_id=document_id,
            user_id=user_id,
        )

        active_job = next(
            (
                job
                for job in jobs
                if job["status"] in {"queued", "processing"}
            ),
            None,
        )

        if active_job is not None:
            raise RetryNotAllowedError(
                "This document already has an active ingestion job."
            )

        retry_job_count = max(len(jobs) - 1, 0)

        if retry_job_count >= MAX_RETRY_JOBS_PER_DOCUMENT:
            raise RetryNotAllowedError(
                "Retry limit reached. Upload a corrected document."
            )

        if jobs:
            latest_job = jobs[0]
            created_at = self._parse_timestamp(latest_job["created_at"])
            retry_available_at = created_at + timedelta(
                seconds=RETRY_COOLDOWN_SECONDS
            )

            if datetime.now(timezone.utc) < retry_available_at:
                remaining_seconds = max(
                    1,
                    int(
                        (
                            retry_available_at
                            - datetime.now(timezone.utc)
                        ).total_seconds()
                    ),
                )

                raise RetryNotAllowedError(
                    "Please wait "
                    f"{remaining_seconds} second(s) before retrying."
                )

        return self.create_job(
            document_id=document_id,
            user_id=user_id,
        )

    def mark_processing(
        self,
        *,
        job_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Mark a queued job as processing and increment its attempt count."""
        client = get_supabase_service_client()

        existing_job = self.get_job(
            job_id=job_id,
            user_id=user_id,
        )

        if existing_job is None:
            raise ValueError("Ingestion job not found.")

        response = (
            client.table("ingestion_jobs")
            .update(
                {
                    "status": "processing",
                    "attempt_count": existing_job["attempt_count"] + 1,
                    "error_message": None,
                    "processing_stage": "starting",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "completed_at": None,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )

        return response.data[0]

    def update_processing_stage(
        self,
        *,
        job_id: str,
        user_id: str,
        processing_stage: str,
    ) -> dict[str, Any]:
        """Persist the current ingestion stage for a processing job."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .update(
                {
                    "processing_stage": processing_stage,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .eq("status", "processing")
            .execute()
        )

        if not response.data:
            raise ValueError("Could not update ingestion processing stage.")

        return response.data[0]

    def mark_completed(
        self,
        *,
        job_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Mark an ingestion job as completed."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .update(
                {
                    "status": "completed",
                    "error_message": None,
                    "processing_stage": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )

        return response.data[0]

    def mark_failed(
        self,
        *,
        job_id: str,
        user_id: str,
        error_message: str,
        processing_stage: str,
    ) -> dict[str, Any]:
        """Mark an ingestion job as failed with a safe error message."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .update(
                {
                    "status": "failed",
                    "error_message": error_message,
                    "processing_stage": processing_stage,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )

        return response.data[0]

    def get_recoverable_jobs(self) -> list[dict[str, Any]]:
        """Return queued and stale-processing jobs after a server restart."""
        client = get_supabase_service_client()

        stale_before = (
            datetime.now(timezone.utc)
            - timedelta(minutes=STALE_PROCESSING_AFTER_MINUTES)
        ).isoformat()

        queued_response = (
            client.table("ingestion_jobs")
            .select(JOB_SELECT_COLUMNS)
            .eq("status", "queued")
            .execute()
        )

        stale_processing_response = (
            client.table("ingestion_jobs")
            .select(JOB_SELECT_COLUMNS)
            .eq("status", "processing")
            .lt("started_at", stale_before)
            .execute()
        )

        return [
            *queued_response.data,
            *stale_processing_response.data,
        ]

    def requeue_job_for_recovery(
        self,
        *,
        job_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Move an interrupted job back to queued so startup can process it."""
        client = get_supabase_service_client()

        response = (
            client.table("ingestion_jobs")
            .update(
                {
                    "status": "queued",
                    "error_message": None,
                    "processing_stage": "queued",
                    "started_at": None,
                    "completed_at": None,
                }
            )
            .eq("id", job_id)
            .eq("user_id", user_id)
            .execute()
        )

        return response.data[0]

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Parse Supabase ISO timestamps as timezone-aware datetimes."""
        normalized_value = value.replace("Z", "+00:00")
        parsed_value = datetime.fromisoformat(normalized_value)

        if parsed_value.tzinfo is None:
            return parsed_value.replace(tzinfo=timezone.utc)

        return parsed_value.astimezone(timezone.utc)


ingestion_job_service = IngestionJobService()