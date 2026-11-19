"""In-memory sliding window rate limiter."""

from __future__ import annotations

import threading
import time
from collections import deque


class InMemorySlidingWindowLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._records: dict[str, deque[float]] = {}

    def is_allowed(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Check if request for key is allowed under sliding window.

        Returns (allowed, retry_after_seconds).
        If allowed, records the timestamp and returns (True, 0).
        If not allowed, returns (False, seconds_until_oldest_expires).
        """
        current_time = now if now is not None else time.time()
        cutoff = current_time - self.window_seconds

        with self._lock:
            q = self._records.setdefault(key, deque())

            # Remove timestamps outside window
            while q and q[0] <= cutoff:
                q.popleft()

            if len(q) < self.max_requests:
                q.append(current_time)
                return True, 0

            # Rate limit exceeded: calculate retry-after from oldest timestamp in window
            oldest = q[0]
            retry_after = max(1, int(oldest + self.window_seconds - current_time))
            return False, retry_after

    def reset(self, key: str | None = None) -> None:
        """Reset limiter records for key or all keys."""
        with self._lock:
            if key is None:
                self._records.clear()
            else:
                self._records.pop(key, None)
