"""Resilience helpers: circuit breaker and bounded response cache.

Purpose:
- CircuitBreaker: fail fast when the LLM endpoint is unhealthy, and
  automatically probe recovery (half-open) after a cool-down window.
- ResponseCache: bounded LRU cache keyed by normalized input, so repeated
  questions do not burn tokens on identical answers.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any


class CircuitBreaker:
    """Simple circuit breaker with closed / open / half-open states.

    The circuit opens after `failure_threshold` consecutive failures and
    stays open for `cooldown_seconds`. In the half-open state a single
    trial call decides whether to close or re-open.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.RLock()
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        with self._lock:
            if (
                self._state == self.OPEN
                and self._opened_at is not None
                and time.monotonic() - self._opened_at >= self.cooldown_seconds
            ):
                return self.HALF_OPEN
            return self._state

    def allow_request(self) -> bool:
        """Return True when a request may proceed to the endpoint."""
        return self.state in {self.CLOSED, self.HALF_OPEN}

    def record_success(self) -> None:
        """Reset failure state after a successful call."""
        with self._lock:
            self._consecutive_failures = 0
            self._state = self.CLOSED
            self._opened_at = None

    def record_failure(self) -> None:
        """Count a failure and open the circuit when the threshold is hit."""
        with self._lock:
            self._consecutive_failures += 1
            if self._state == self.HALF_OPEN:
                # A failed trial re-opens the circuit immediately.
                self._state = self.OPEN
                self._opened_at = time.monotonic()
                return
            if self._consecutive_failures >= self.failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.monotonic()

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator form: wrap a callable with circuit protection."""

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.allow_request():
                raise CircuitOpenError(
                    f"Circuit breaker is open (state={self.state}); failing fast."
                )
            try:
                result = func(*args, **kwargs)
            except Exception:
                self.record_failure()
                raise
            self.record_success()
            return result

        return wrapper


class CircuitOpenError(RuntimeError):
    """Raised when the circuit breaker rejects a request."""


class ResponseCache:
    """Bounded thread-safe LRU cache for agent responses."""

    def __init__(self, maxsize: int = 128) -> None:
        self.maxsize = maxsize
        self._lock = threading.RLock()
        self._store: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Any | None:
        """Return the cached value for key, or None when absent."""
        with self._lock:
            if key not in self._store:
                return None
            self._store.move_to_end(key)
            return self._store[key]

    def put(self, key: str, value: Any) -> None:
        """Store value under key, evicting the least recently used entry."""
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
