from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import CurrentUser
from app.services.document_service import document_service
from app.services.ingestion_job_service import (
    RetryNotAllowedError,
    ingestion_job_service,
)

client = TestClient(app)

TEST_USER_ID = "00000000-0000-0000-0000-000000000123"
TEST_DOCUMENT_ID = "00000000-0000-0000-0000-000000000001"
TEST_JOB_ID = "00000000-0000-0000-0000-000000000999"


def override_get_current_user() -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        email="test@example.com",
    )


def uploaded_document() -> dict:
    return {
        "id": TEST_DOCUMENT_ID,
        "file_name": "policy.txt",
        "storage_path": f"{TEST_USER_ID}/example/policy.txt",
        "file_size_bytes": 12,
        "mime_type": "text/plain",
        "status": "uploaded",
        "error_message": None,
        "page_count": None,
        "created_at": "2026-06-25T00:00:00+00:00",
    }


def failed_document() -> dict:
    document = uploaded_document()
    document["status"] = "failed"
    document["error_message"] = "Processing failed during text extraction."
    return document


def processed_document() -> dict:
    document = uploaded_document()
    document["status"] = "processed"
    return document


def ingestion_job(
    *,
    status: str = "processing",
    processing_stage: str = "embedding generation",
) -> dict:
    timestamp = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc).isoformat()

    return {
        "id": TEST_JOB_ID,
        "document_id": TEST_DOCUMENT_ID,
        "user_id": TEST_USER_ID,
        "status": status,
        "attempt_count": 1,
        "processing_stage": processing_stage,
        "error_message": None,
        "started_at": timestamp,
        "completed_at": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_upload_requires_authentication() -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 401


def test_upload_document_returns_created_response_and_queues_job(
    monkeypatch,
) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    queued_jobs: list[dict] = []

    monkeypatch.setattr(
        document_service,
        "upload_document",
        lambda user_id, uploaded_file, file_content: uploaded_document(),
    )

    def fake_create_job(*, document_id: str, user_id: str) -> dict:
        job = ingestion_job(status="queued", processing_stage="queued")
        queued_jobs.append(
            {
                "document_id": document_id,
                "user_id": user_id,
            }
        )
        return job

    monkeypatch.setattr(
        ingestion_job_service,
        "create_job",
        fake_create_job,
    )

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"hello policy", "text/plain")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["file_name"] == "policy.txt"
    assert response.json()["status"] == "uploaded"
    assert queued_jobs == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
        }
    ]


def test_upload_returns_server_error_when_job_cannot_be_created(
    monkeypatch,
) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    status_updates: list[dict] = []

    monkeypatch.setattr(
        document_service,
        "upload_document",
        lambda user_id, uploaded_file, file_content: uploaded_document(),
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "create_job",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    monkeypatch.setattr(
        document_service,
        "update_document_status",
        lambda **kwargs: status_updates.append(kwargs) or failed_document(),
    )

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"hello policy", "text/plain")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Document upload succeeded, but processing could not be queued."
    )
    assert status_updates == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
            "status": "failed",
            "error_message": (
                "Document upload succeeded, but processing could not be queued."
            ),
        }
    ]


def test_retry_failed_document_queues_new_ingestion_job(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "fastapi.background.BackgroundTasks.add_task",
        lambda self, func, *args, **kwargs: None,
    )
    app.dependency_overrides[get_current_user] = override_get_current_user

    queued_retries: list[dict] = []
    status_updates: list[dict] = []

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: failed_document(),
    )

    def fake_create_retry_job(*, document_id: str, user_id: str) -> dict:
        queued_retries.append(
            {
                "document_id": document_id,
                "user_id": user_id,
            }
        )
        return ingestion_job(status="queued", processing_stage="queued")

    monkeypatch.setattr(
        ingestion_job_service,
        "create_retry_job",
        fake_create_retry_job,
    )

    monkeypatch.setattr(
        document_service,
        "update_document_status",
        lambda **kwargs: status_updates.append(kwargs) or uploaded_document(),
    )

    response = client.post(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/retry",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "uploaded"
    assert queued_retries == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
        }
    ]
    assert status_updates == [
        {
            "document_id": TEST_DOCUMENT_ID,
            "user_id": TEST_USER_ID,
            "status": "uploaded",
            "error_message": None,
        }
    ]


def test_retry_rejects_document_that_is_not_failed(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: processed_document(),
    )

    response = client.post(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/retry",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Only failed documents can be retried."


def test_retry_returns_not_found_for_another_users_document(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: None,
    )

    response = client.post(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/retry",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_retry_returns_conflict_when_retry_policy_rejects(
    monkeypatch,
) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: failed_document(),
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "create_retry_job",
        lambda **kwargs: (_ for _ in ()).throw(
            RetryNotAllowedError("Retry limit reached. Upload a corrected document.")
        ),
    )

    response = client.post(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/retry",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Retry limit reached. Upload a corrected document."
    )


def test_get_ingestion_status_returns_latest_job(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: uploaded_document(),
    )

    monkeypatch.setattr(
        ingestion_job_service,
        "get_latest_job_for_document",
        lambda document_id, user_id: ingestion_job(),
    )

    response = client.get(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/ingestion-status",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["id"] == TEST_JOB_ID
    assert payload["document_id"] == TEST_DOCUMENT_ID
    assert payload["status"] == "processing"
    assert payload["processing_stage"] == "embedding generation"
    assert payload["attempt_count"] == 1


def test_get_ingestion_status_returns_not_found_for_unknown_document(
    monkeypatch,
) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "get_document",
        lambda document_id, user_id: None,
    )

    response = client.get(
        f"/api/v1/documents/{TEST_DOCUMENT_ID}/ingestion-status",
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."
