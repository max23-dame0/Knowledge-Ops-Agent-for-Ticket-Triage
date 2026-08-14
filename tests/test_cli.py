"""Offline tests for the unified CLI (acceptance runner + API smoke helpers)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Self
from unittest.mock import patch

from src.cli import (
    ACCEPTANCE_CASES,
    api_ask,
    api_health,
    run_acceptance,
)


def _fake_agent(question: str):
    """Fake run_agent returning a route derived from the question hash."""
    routes = ["kb", "kb", "kb", "ticket", "ticket", "ticket", "escalation", "escalation", "clarify", "clarify", "refuse", "refuse"]
    index = hash(question) % len(routes)
    return SimpleNamespace(route=routes[index])


def test_acceptance_cases_cover_five_routes() -> None:
    """The acceptance list spans kb/ticket/escalation/clarify/refuse."""
    routes = {case["expected_route"] for case in ACCEPTANCE_CASES}
    assert routes == {"kb", "ticket", "escalation", "clarify", "refuse"}
    assert len(ACCEPTANCE_CASES) == 12


def test_run_acceptance_matches_fake_agent_routes() -> None:
    """The runner compares predicted vs expected route per case."""
    results = run_acceptance(_fake_agent)
    assert len(results) == 12
    for result in results:
        assert set(result.keys()) == {"id", "question", "expected_route", "predicted_route", "status"}
        assert result["status"] in {"PASS", "FAIL"}


def test_run_acceptance_failure_is_reported() -> None:
    """A mismatching route yields FAIL with both routes recorded."""

    def wrong_agent(question: str):
        del question
        return SimpleNamespace(route="clarify")

    results = run_acceptance(wrong_agent)
    failed = [r for r in results if r["status"] == "FAIL"]
    assert failed
    assert failed[0]["predicted_route"] == "clarify"


class _FakeResponse:
    """Context-manager-compatible fake HTTP response."""

    def __init__(self, payload: dict, status: int) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _fake_urlopen(payload: dict, status: int = 200):
    """Build a fake urllib.urlopen returning a JSON payload."""

    def urlopen(request, timeout=None):
        del request, timeout
        return _FakeResponse(payload, status)

    return urlopen


def test_api_health_returns_payload() -> None:
    """api_health parses the /healthz JSON body."""
    payload = {"status": "ok", "version": "0.1.0", "kb_index_available": True, "ticket_records": 7}
    with patch("src.cli.urllib.request.urlopen", side_effect=_fake_urlopen(payload)):
        result = api_health("http://127.0.0.1:8000")
    assert result["status"] == "ok"
    assert result["ticket_records"] == 7


def test_api_ask_sends_auth_header_and_parses_answer() -> None:
    """api_ask sends X-API-Key and returns the normalized answer dict."""
    payload = {"request_id": "req-1", "answer": {"route": "kb", "conclusion": "c"}}
    captured: dict[str, str] = {}

    def urlopen(request, timeout=None):
        del timeout
        captured["key"] = request.headers.get("X-api-key")
        return _FakeResponse(payload, 200)

    with patch("src.cli.urllib.request.urlopen", side_effect=urlopen):
        result = api_ask("VPN 登录失败怎么办", "local-dev-key-001", "http://127.0.0.1:8000")

    assert captured["key"] == "local-dev-key-001"
    assert result["answer"]["route"] == "kb"


def test_api_ask_rejects_http_401_as_runtime_error() -> None:
    """A 401 response becomes a RuntimeError with the status in the message."""
    import urllib.error

    class _HttpErrorResponse:
        code = 401

        def read(self) -> bytes:
            return json.dumps({"detail": "Invalid or missing API key."}).encode("utf-8")

    def urlopen(request, timeout=None):
        del request, timeout
        raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, _HttpErrorResponse())

    with patch("src.cli.urllib.request.urlopen", side_effect=urlopen):
        try:
            api_ask("q", "wrong-key", "http://127.0.0.1:8000")
        except RuntimeError as exc:
            assert "401" in str(exc)
            return
    raise AssertionError("expected RuntimeError for 401 response")
