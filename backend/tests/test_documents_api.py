from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import CurrentUser
from app.services.document_service import document_service

client = TestClient(app)


def override_get_current_user() -> CurrentUser:
    return CurrentUser(
        id="test-user",
        email="test@example.com",
    )


def test_upload_requires_authentication() -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 401


def test_upload_document_returns_created_response(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "upload_document",
        lambda user_id, uploaded_file, file_content: {
            "id": "00000000-0000-0000-0000-000000000001",
            "file_name": "policy.txt",
            "storage_path": "test-user/example/policy.txt",
            "file_size_bytes": 12,
            "mime_type": "text/plain",
            "status": "uploaded",
            "created_at": "2026-06-25T00:00:00+00:00",
        },
    )

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("policy.txt", b"hello policy", "text/plain")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["file_name"] == "policy.txt"
    assert response.json()["status"] == "uploaded"


def test_list_documents_returns_current_users_documents(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        document_service,
        "list_documents",
        lambda user_id: [
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "file_name": "policy.txt",
                "file_size_bytes": 12,
                "mime_type": "text/plain",
                "status": "uploaded",
                "page_count": None,
                "created_at": "2026-06-25T00:00:00+00:00",
            }
        ],
    )

    response = client.get("/api/v1/documents")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["file_name"] == "policy.txt"