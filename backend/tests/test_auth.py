from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models.auth import CurrentUser


client = TestClient(app)


def test_auth_me_returns_401_without_token() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


def test_auth_me_returns_current_user_with_valid_token() -> None:
    def fake_get_current_user() -> CurrentUser:
        return CurrentUser(
            id="test-user-id",
            email="test@example.com",
        )

    app.dependency_overrides[get_current_user] = fake_get_current_user

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "test-user-id",
        "email": "test@example.com",
    }

def test_auth_me_returns_401_for_invalid_token(monkeypatch) -> None:
    def fake_get_supabase_client():
        class FakeAuth:
            def get_user(self, token: str):
                raise Exception("Token is invalid")

        class FakeClient:
            auth = FakeAuth()

        return FakeClient()

    monkeypatch.setattr(
        "app.api.dependencies.get_supabase_client",
        fake_get_supabase_client,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid or expired authentication token."
    }