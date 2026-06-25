from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.document_service import DocumentService


def make_upload_file(
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},
    )


def test_upload_rejects_unsupported_extension() -> None:
    service = DocumentService()
    uploaded_file = make_upload_file("malware.exe", b"not allowed")

    with pytest.raises(HTTPException) as exc_info:
        service.upload_document(
            user_id="test-user",
            uploaded_file=uploaded_file,
            file_content=b"not allowed",
        )

    assert exc_info.value.status_code == 400
    assert "Unsupported file type" in exc_info.value.detail


def test_upload_rejects_empty_file() -> None:
    service = DocumentService()
    uploaded_file = make_upload_file("empty.pdf", b"", "application/pdf")

    with pytest.raises(HTTPException) as exc_info:
        service.upload_document(
            user_id="test-user",
            uploaded_file=uploaded_file,
            file_content=b"",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "The uploaded file is empty."


def test_upload_rejects_file_larger_than_limit() -> None:
    service = DocumentService()
    uploaded_file = make_upload_file("large.pdf", b"x", "application/pdf")
    large_content = b"x" * (20 * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as exc_info:
        service.upload_document(
            user_id="test-user",
            uploaded_file=uploaded_file,
            file_content=large_content,
        )

    assert exc_info.value.status_code == 413
    assert "Maximum allowed size is 20 MB" in exc_info.value.detail


@patch("app.services.document_service.get_supabase_service_client")
def test_upload_stores_file_and_metadata(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "file_name": "policy.txt",
            "storage_path": "test-user/example/policy.txt",
            "file_size_bytes": 12,
            "mime_type": "text/plain",
            "status": "uploaded",
            "created_at": "2026-06-25T00:00:00+00:00",
        }
    ]

    service = DocumentService()
    uploaded_file = make_upload_file(
        "policy.txt",
        b"hello policy",
        "text/plain",
    )

    result = service.upload_document(
        user_id="test-user",
        uploaded_file=uploaded_file,
        file_content=b"hello policy",
    )

    assert result["file_name"] == "policy.txt"
    assert result["status"] == "uploaded"

    mock_client.storage.from_.assert_called_once_with("documents")
    mock_client.table.assert_called_once_with("documents")