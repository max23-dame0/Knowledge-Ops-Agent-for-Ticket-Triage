"""Offline tests for the FastAPI service facade (auth, rate limit, health)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


@pytest.fixture()
def auth_env(monkeypatch) -> None:
    monkeypatch.setenv("API_AUTH_KEYS", "test-key-1,test-key-2")


class TestHealthz:
    def test_healthz_ok(self) -> None:
        response = client.get("/healthz")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "kb_index_available" in body
        assert "ticket_records" in body

    def test_healthz_returns_request_id_header(self) -> None:
        response = client.get("/healthz")
        assert response.headers.get("X-Request-Id")


class TestAuth:
    def test_ask_rejected_without_key_and_no_config(self, monkeypatch) -> None:
        # No API_AUTH_KEYS configured -> fail closed with 503 (auth is
        # mandatory for an exposed AI endpoint, so missing config must not
        # accidentally open access).
        monkeypatch.delenv("API_AUTH_KEYS", raising=False)
        response = client.post("/agent/ask", json={"question": "VPN 登录失败怎么办"})
        assert response.status_code == 503

    def test_ask_rejected_when_key_missing(self, auth_env) -> None:
        response = client.post("/agent/ask", json={"question": "VPN 登录失败怎么办"})
        assert response.status_code == 401

    def test_ask_rejected_with_wrong_key(self, auth_env) -> None:
        response = client.post(
            "/agent/ask",
            json={"question": "VPN 登录失败怎么办"},
            headers={"X-API-Key": "wrong"},
        )
        assert response.status_code == 401

    def test_ask_accepted_with_valid_key(self, auth_env) -> None:
        with patch("src.api.app.run_agent") as mock_run:
            mock_run.return_value = type(
                "Answer",
                (),
                {"model_dump": lambda self: {"route": "kb", "conclusion": "ok"}},
            )()
            response = client.post(
                "/agent/ask",
                json={"question": "VPN 登录失败怎么办"},
                headers={"X-API-Key": "test-key-1"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["answer"]["route"] == "kb"
        assert body["request_id"]

    def test_fail_closed_when_no_keys_configured(self, monkeypatch) -> None:
        monkeypatch.delenv("API_AUTH_KEYS", raising=False)
        response = client.post(
            "/agent/ask",
            json={"question": "hi"},
            headers={"X-API-Key": "anything"},
        )
        assert response.status_code == 503


class TestRateLimit:
    def test_rate_limit_429(self, auth_env, monkeypatch) -> None:
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        from src.api import ratelimit

        ratelimit._counter = ratelimit._SlidingWindowCounter()  # fresh counter

        with patch("src.api.app.run_agent") as mock_run:
            mock_run.return_value = type(
                "Answer",
                (),
                {"model_dump": lambda self: {"route": "kb", "conclusion": "ok"}},
            )()
            ok1 = client.post("/agent/ask", json={"question": "q1"}, headers={"X-API-Key": "test-key-1"})
            ok2 = client.post("/agent/ask", json={"question": "q2"}, headers={"X-API-Key": "test-key-1"})
            blocked = client.post("/agent/ask", json={"question": "q3"}, headers={"X-API-Key": "test-key-1"})

        assert ok1.status_code == 200
        assert ok2.status_code == 200
        assert blocked.status_code == 429


class TestAskValidation:
    def test_empty_question_rejected(self, auth_env) -> None:
        response = client.post(
            "/agent/ask",
            json={"question": ""},
            headers={"X-API-Key": "test-key-1"},
        )
        assert response.status_code == 422
