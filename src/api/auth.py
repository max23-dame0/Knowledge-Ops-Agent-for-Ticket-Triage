"""API key authentication for the HTTP service (fail-closed).

Keys are configured via the API_AUTH_KEYS environment variable as a
comma-separated list. When no keys are configured the service refuses all
requests: an exposed AI endpoint without auth is a cost and abuse risk.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status

HEADER_NAME = "X-API-Key"


def _configured_keys() -> list[str]:
    raw = os.getenv("API_AUTH_KEYS", "").strip()
    if not raw:
        return []
    return [key.strip() for key in raw.split(",") if key.strip()]


def require_api_key(x_api_key: str | None = Header(default=None, alias=HEADER_NAME)) -> None:
    """FastAPI dependency: reject requests without a valid API key."""
    keys = _configured_keys()
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server authentication is not configured (API_AUTH_KEYS missing).",
        )
    if not x_api_key or not any(hmac.compare_digest(x_api_key, key) for key in keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
