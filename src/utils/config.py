"""Minimal configuration loading helpers for OpenAI-compatible model access."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI


@dataclass(frozen=True)
class OpenAISettings:
    """Connection settings for an OpenAI-compatible model endpoint."""

    api_key: str
    model: str
    base_url: str | None = None



def get_openai_api_key() -> str:
    """Load and return the API key for an OpenAI-compatible endpoint."""
    load_dotenv()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "缺少 LLM_API_KEY。请在环境变量或本地 .env 文件中配置。"
        )
    return api_key



def get_openai_settings() -> OpenAISettings:
    """Load API key, model id, and optional base URL from environment variables."""
    load_dotenv()
    api_key = get_openai_api_key()
    model = os.getenv("LLM_MODEL_ID", "gpt-4.1-mini").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None

    if not model:
        raise ValueError(
            "缺少 LLM_MODEL_ID。请在环境变量或本地 .env 文件中配置。"
        )

    return OpenAISettings(api_key=api_key, model=model, base_url=base_url)



def get_openai_client() -> OpenAI:
    """Build a minimal OpenAI client using the configured OpenAI-compatible endpoint."""
    settings = get_openai_settings()
    if settings.base_url:
        return OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    return OpenAI(api_key=settings.api_key)
