import threading
import time
from collections import defaultdict, deque


class RateLimitExceededError(Exception):
    """Raised when a caller exceeds an endpoint rate limit."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Rate limit exceeded.")


class InMemoryRateLimitService:
    """
    Thread-safe sliding-window rate limiter.

    This is suitable for a single API process. Replace with Redis before
    horizontal scaling to multiple API instances.
    """

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        now = time.monotonic()

        with self._lock:
            request_times = self._requests[key]
            cutoff = now - window_seconds

            while request_times and request_times[0] <= cutoff:
                request_times.popleft()

            if len(request_times) >= limit:
                retry_after_seconds = max(
                    1,
                    int(window_seconds - (now - request_times[0])) + 1,
                )
                raise RateLimitExceededError(retry_after_seconds)

            request_times.append(now)

    def reset(self) -> None:
        """Clear all counters. Intended for tests only."""
        with self._lock:
            self._requests.clear()


rate_limit_service = InMemoryRateLimitService()
