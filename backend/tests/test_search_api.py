from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import CurrentUser
from app.services.retrieval_service import retrieval_service

client = TestClient(app)

TEST_USER_ID = "00000000-0000-0000-0000-000000000123"


def override_get_current_user() -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        email="test@example.com",
    )


def test_search_requires_authentication() -> None:
    response = client.post(
        "/api/v1/search",
        json={
            "query": "Who can access customer data?",
            "top_k": 5,
        },
    )

    assert response.status_code == 401


def test_search_returns_retrieved_chunks(monkeypatch) -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    monkeypatch.setattr(
        retrieval_service,
        "search",
        lambda user_id, query, top_k: [
            {
                "document_id": "00000000-0000-0000-0000-000000000001",
                "file_name": "vector-test-policy.txt",
                "chunk_index": 0,
                "content": (
                    "Only authorized employees may access customer data."
                ),
                "score": 0.92,
            }
        ],
    )

    response = client.post(
        "/api/v1/search",
        json={
            "query": "Who can access customer data?",
            "top_k": 5,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["query"] == "Who can access customer data?"
    assert len(body["results"]) == 1
    assert body["results"][0]["file_name"] == "vector-test-policy.txt"
    assert body["results"][0]["chunk_index"] == 0
    assert body["results"][0]["score"] == 0.92


def test_search_rejects_short_query() -> None:
    app.dependency_overrides[get_current_user] = override_get_current_user

    response = client.post(
        "/api/v1/search",
        json={
            "query": "hi",
            "top_k": 5,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 422