from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import CurrentUser
from app.services.document_service import document_service
from app.services.pinecone_vector_service import PineconeVectorService


client = TestClient(app)


def fake_current_user() -> CurrentUser:
    return CurrentUser(
        id="test-user-123",
        email="test@example.com",
    )


def test_delete_document_removes_vectors_and_document_data(monkeypatch) -> None:
    document_id = "document-123"

    fake_document = {
        "id": document_id,
        "storage_path": "test-user-123/document-123/security-policy.txt",
    }

    deleted_vectors: dict = {}
    deleted_data: dict = {}

    def fake_get_document(*, document_id: str, user_id: str) -> dict | None:
        assert document_id == "document-123"
        assert user_id == "test-user-123"
        return fake_document

    def fake_delete_document_vectors(
        self: PineconeVectorService,
        *,
        document_id: str,
        user_id: str,
    ) -> None:
        deleted_vectors["document_id"] = document_id
        deleted_vectors["user_id"] = user_id

    def fake_delete_document_data(
        *,
        document_id: str,
        user_id: str,
        storage_path: str,
    ) -> None:
        deleted_data["document_id"] = document_id
        deleted_data["user_id"] = user_id
        deleted_data["storage_path"] = storage_path

    monkeypatch.setattr(
        document_service,
        "get_document",
        fake_get_document,
    )
    monkeypatch.setattr(
        PineconeVectorService,
        "delete_document_vectors",
        fake_delete_document_vectors,
    )
    monkeypatch.setattr(
        document_service,
        "delete_document_data",
        fake_delete_document_data,
    )

    app.dependency_overrides[get_current_user] = fake_current_user

    try:
        response = client.delete(
            f"/api/v1/documents/{document_id}",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""

    assert deleted_vectors == {
        "document_id": "document-123",
        "user_id": "test-user-123",
    }

    assert deleted_data == {
        "document_id": "document-123",
        "user_id": "test-user-123",
        "storage_path": "test-user-123/document-123/security-policy.txt",
    }


def test_delete_document_returns_404_when_not_owned_or_missing(monkeypatch) -> None:
    def fake_get_document(*, document_id: str, user_id: str) -> None:
        assert user_id == "test-user-123"
        return None

    monkeypatch.setattr(
        document_service,
        "get_document",
        fake_get_document,
    )

    app.dependency_overrides[get_current_user] = fake_current_user

    try:
        response = client.delete(
            "/api/v1/documents/missing-document",
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Document not found.",
    }