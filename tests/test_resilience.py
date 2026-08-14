"""Offline unit tests for the circuit breaker and response cache."""

from __future__ import annotations

import pytest

from src.utils.resilience import CircuitBreaker, CircuitOpenError, ResponseCache


class TestCircuitBreaker:
    def test_allows_requests_while_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
        assert cb.allow_request() is True

    def test_opens_after_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == "open"
        assert cb.allow_request() is False

    def test_success_resets_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.allow_request() is True

    def test_half_open_after_cooldown(self, monkeypatch) -> None:
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=1)

        class _FakeTime:
            _now = 100.0

            @staticmethod
            def monotonic() -> float:
                return _FakeTime._now

        monkeypatch.setattr("src.utils.resilience.time.monotonic", _FakeTime.monotonic)
        cb.record_failure()  # records opened_at = 100.0
        assert cb.state == "open"

        _FakeTime._now = 200.0  # cooldown elapsed
        assert cb.state == "half_open"
        assert cb.allow_request() is True

        # A failed trial in half-open re-opens the circuit immediately.
        cb.record_failure()
        assert cb.state == "open"

    def test_decorator_raises_when_open(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=30)
        cb.record_failure()

        @cb
        def work() -> str:
            return "done"

        with pytest.raises(CircuitOpenError):
            work()

    def test_decorator_counts_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=30)

        @cb
        def work() -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError):
            work()
        assert cb.state == "closed"  # threshold not yet hit
        with pytest.raises(ValueError):
            work()
        assert cb.state == "open"


class TestResponseCache:
    def test_roundtrip(self) -> None:
        cache = ResponseCache(maxsize=3)
        cache.put("a", 1)
        assert cache.get("a") == 1
        assert cache.get("missing") is None

    def test_lru_eviction(self) -> None:
        cache = ResponseCache(maxsize=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")  # make a most recently used
        cache.put("c", 3)  # evicts "b"
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_clear(self) -> None:
        cache = ResponseCache(maxsize=2)
        cache.put("a", 1)
        cache.clear()
        assert cache.get("a") is None
        assert len(cache) == 0
