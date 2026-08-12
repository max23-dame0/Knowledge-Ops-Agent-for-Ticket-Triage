"""In-memory sliding-window rate limiter for the HTTP service.

Limits requests per client (identified by IP or a caller-supplied key) to
RATE_LIMIT_PER_MINUTE (default 30). The window is a fixed 60-second bucket
with a per-key counter - simple, thread-safe, and good enough for a single
process deployment. A distributed store (Redis) is the upgrade path when
scaling horizontally.
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 60


def _limit_per_minute() -> int:
    raw = os.getenv("RATE_LIMIT_PER_MINUTE", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value > 0 else 30


class _SlidingWindowCounter:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int, window: int = _WINDOW_SECONDS) -> bool:
        now = time.monotonic()
        with self._lock:
            timestamps = [t for t in self._hits.get(key, []) if now - t < window]
            if len(timestamps) >= limit:
                self._hits[key] = timestamps
                return False
            timestamps.append(now)
            self._hits[key] = timestamps
            return True


_counter = _SlidingWindowCounter()


def rate_limit(request: Request) -> None:
    """FastAPI dependency: reject requests that exceed the per-client budget."""
    client_key = request.client.host if request.client else "unknown"
    if not _counter.allow(client_key, _limit_per_minute()):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )
