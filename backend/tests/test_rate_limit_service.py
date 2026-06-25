import pytest

from app.services.rate_limit_service import (
    InMemoryRateLimitService,
    RateLimitExceededError,
)


def test_allows_requests_up_to_the_limit(monkeypatch) -> None:
    service = InMemoryRateLimitService()
    monkeypatch.setattr(
        "app.services.rate_limit_service.time.monotonic",
        lambda: 100.0,
    )

    for _ in range(3):
        service.check(
            key="rag_ask:user-1",
            limit=3,
            window_seconds=60,
        )


def test_rejects_request_over_the_limit(monkeypatch) -> None:
    service = InMemoryRateLimitService()
    monkeypatch.setattr(
        "app.services.rate_limit_service.time.monotonic",
        lambda: 100.0,
    )

    for _ in range(2):
        service.check(
            key="rag_ask:user-1",
            limit=2,
            window_seconds=60,
        )

    with pytest.raises(RateLimitExceededError) as exc_info:
        service.check(
            key="rag_ask:user-1",
            limit=2,
            window_seconds=60,
        )

    assert exc_info.value.retry_after_seconds == 61


def test_allows_request_after_window_expires(monkeypatch) -> None:
    service = InMemoryRateLimitService()
    current_time = [100.0]

    monkeypatch.setattr(
        "app.services.rate_limit_service.time.monotonic",
        lambda: current_time[0],
    )

    service.check(
        key="document_upload:user-1",
        limit=1,
        window_seconds=60,
    )

    current_time[0] = 160.1

    service.check(
        key="document_upload:user-1",
        limit=1,
        window_seconds=60,
    )


def test_keeps_limits_separate_per_user_and_action(monkeypatch) -> None:
    service = InMemoryRateLimitService()
    monkeypatch.setattr(
        "app.services.rate_limit_service.time.monotonic",
        lambda: 100.0,
    )

    service.check(
        key="rag_ask:user-1",
        limit=1,
        window_seconds=60,
    )

    service.check(
        key="rag_ask:user-2",
        limit=1,
        window_seconds=60,
    )

    service.check(
        key="document_upload:user-1",
        limit=1,
        window_seconds=60,
    )
