from fastapi import HTTPException, status

from app.services.rate_limit_service import (
    RateLimitExceededError,
    rate_limit_service,
)


def enforce_user_rate_limit(
    *,
    user_id: str,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Apply one per-user limit and return a consistent API error."""
    try:
        rate_limit_service.check(
            key=f"{action}:{user_id}",
            limit=limit,
            window_seconds=window_seconds,
        )
    except RateLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many requests. Please try again in "
                f"{exc.retry_after_seconds} seconds."
            ),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
