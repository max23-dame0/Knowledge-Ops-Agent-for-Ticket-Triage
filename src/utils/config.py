"""Minimal configuration loading helpers for OpenAI-compatible model access."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

# Environment variable names for LLM endpoint configuration.
ENV_API_KEY = "LLM_API_KEY"
ENV_MODEL_ID = "LLM_MODEL_ID"
ENV_BASE_URL = "LLM_BASE_URL"
ENV_ALT_API_KEY = "LLM_ALT_API_KEY"
ENV_ALT_MODEL_ID = "LLM_ALT_MODEL_ID"
ENV_ALT_MODEL_ID_PRO = "LLM_ALT_MODEL_ID_PRO"
ENV_ALT_BASE_URL = "LLM_ALT_BASE_URL"

DEFAULT_MODEL_ID = "gpt-4.1-mini"


@dataclass(frozen=True)
class OpenAISettings:
    """Connection settings for an OpenAI-compatible model endpoint."""

    api_key: str
    model: str
    base_url: str | None = None


def get_openai_api_key() -> str:
    """Load and return the API key for an OpenAI-compatible endpoint."""
    load_dotenv()
    api_key = os.getenv(ENV_API_KEY, "").strip()
    if not api_key:
        raise ValueError(
            f"缺少 {ENV_API_KEY}。请在环境变量或本地 .env 文件中配置。"
        )
    return api_key


def _resolve_setting(value: str | None, env_name: str, message: str) -> str:
    """Return a non-empty env var value or raise a clear configuration error."""
    resolved = (value or "").strip()
    if not resolved:
        raise ValueError(f"{message}（环境变量：{env_name}）")
    return resolved


def get_openai_settings() -> OpenAISettings:
    """Load API key, model id, and optional base URL from environment variables."""
    load_dotenv()
    api_key = _resolve_setting(
        os.getenv(ENV_API_KEY), ENV_API_KEY,
        f"缺少 {ENV_API_KEY}。请在环境变量或本地 .env 文件中配置。",
    )
    model = _resolve_setting(
        os.getenv(ENV_MODEL_ID, DEFAULT_MODEL_ID), ENV_MODEL_ID,
        f"缺少 {ENV_MODEL_ID}。请在环境变量或本地 .env 文件中配置。",
    )
    base_url = os.getenv(ENV_BASE_URL, "").strip() or None
    return OpenAISettings(api_key=api_key, model=model, base_url=base_url)


def get_alt_openai_settings() -> OpenAISettings | None:
    """Load the optional alternate endpoint settings, or None when unconfigured.

    The alternate endpoint is an optional OpenAI-compatible candidate configured
    via LLM_ALT_BASE_URL / LLM_ALT_API_KEY / LLM_ALT_MODEL_ID (and
    LLM_ALT_MODEL_ID_PRO). Any missing piece resolves to None; the primary
    endpoint stays untouched.
    """
    load_dotenv()
    base_url = os.getenv(ENV_ALT_BASE_URL, "").strip()
    api_key = os.getenv(ENV_ALT_API_KEY, "").strip()
    model = os.getenv(ENV_ALT_MODEL_ID, "").strip()
    if not (base_url and api_key and model):
        return None
    return OpenAISettings(api_key=api_key, model=model, base_url=base_url)


def get_alt_pro_model_id() -> str | None:
    """Return the alternate endpoint's pro model id, or None when unconfigured."""
    load_dotenv()
    return os.getenv(ENV_ALT_MODEL_ID_PRO, "").strip() or None


def get_openai_client() -> OpenAI:
    """Build a minimal OpenAI client using the configured OpenAI-compatible endpoint."""
    settings = get_openai_settings()
    if settings.base_url:
        return OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    return OpenAI(api_key=settings.api_key)
