"""Offline tests for LLM endpoint configuration helpers in src/utils/config.py."""

from __future__ import annotations

import importlib
import os

import pytest

import src.utils.config as config


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch):
    """Remove every LLM-related env var so tests start from a clean slate."""
    for name in (
        "LLM_API_KEY",
        "LLM_MODEL_ID",
        "LLM_BASE_URL",
        "LLM_ALT_API_KEY",
        "LLM_ALT_MODEL_ID",
        "LLM_ALT_MODEL_ID_PRO",
        "LLM_ALT_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    # Disable .env loading so the developer's local .env cannot leak in.
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    # Reload so module-level state cannot leak between tests.
    importlib.reload(config)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    return monkeypatch


def test_get_openai_settings_from_env(clean_env: pytest.MonkeyPatch) -> None:
    """Primary settings come from LLM_* env vars, base URL optional."""
    clean_env.setenv("LLM_API_KEY", "sk-primary")
    clean_env.setenv("LLM_MODEL_ID", "primary-model")
    clean_env.setenv("LLM_BASE_URL", "https://primary.example/v1")

    settings = config.get_openai_settings()

    assert settings.api_key == "sk-primary"
    assert settings.model == "primary-model"
    assert settings.base_url == "https://primary.example/v1"


def test_get_openai_settings_base_url_optional(clean_env: pytest.MonkeyPatch) -> None:
    """An empty LLM_BASE_URL resolves to None."""
    clean_env.setenv("LLM_API_KEY", "sk-primary")
    clean_env.setenv("LLM_MODEL_ID", "primary-model")

    settings = config.get_openai_settings()

    assert settings.base_url is None


def test_get_openai_settings_missing_key_raises(clean_env: pytest.MonkeyPatch) -> None:
    """A missing LLM_API_KEY raises a clear configuration error."""
    clean_env.setenv("LLM_MODEL_ID", "primary-model")

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        config.get_openai_settings()


def test_get_alt_openai_settings_returns_none_by_default(clean_env: pytest.MonkeyPatch) -> None:
    """Without LLM_ALT_* env vars the alternate endpoint is unconfigured."""
    assert config.get_alt_openai_settings() is None


def test_get_alt_openai_settings_complete_config(clean_env: pytest.MonkeyPatch) -> None:
    """All three LLM_ALT_* pieces produce the alternate settings."""
    clean_env.setenv("LLM_ALT_BASE_URL", "https://alt.example/v1")
    clean_env.setenv("LLM_ALT_API_KEY", "sk-alt")
    clean_env.setenv("LLM_ALT_MODEL_ID", "alt-model")

    settings = config.get_alt_openai_settings()

    assert settings is not None
    assert settings.api_key == "sk-alt"
    assert settings.model == "alt-model"
    assert settings.base_url == "https://alt.example/v1"


def test_get_alt_openai_settings_partial_config_returns_none(
    clean_env: pytest.MonkeyPatch,
) -> None:
    """Any missing alternate piece resolves to None without touching primary."""
    clean_env.setenv("LLM_API_KEY", "sk-primary")
    clean_env.setenv("LLM_MODEL_ID", "primary-model")
    clean_env.setenv("LLM_ALT_BASE_URL", "https://alt.example/v1")
    clean_env.setenv("LLM_ALT_API_KEY", "sk-alt")
    # LLM_ALT_MODEL_ID intentionally unset.

    assert config.get_alt_openai_settings() is None
    assert config.get_openai_settings().api_key == "sk-primary"


def test_get_alt_pro_model_id(clean_env: pytest.MonkeyPatch) -> None:
    """LLM_ALT_MODEL_ID_PRO is read independently and defaults to None."""
    assert config.get_alt_pro_model_id() is None

    clean_env.setenv("LLM_ALT_MODEL_ID_PRO", "alt-pro-model")
    assert config.get_alt_pro_model_id() == "alt-pro-model"


def test_get_openai_client_respects_base_url(clean_env: pytest.MonkeyPatch) -> None:
    """The OpenAI client is built with the configured base URL and API key."""
    clean_env.setenv("LLM_API_KEY", "sk-primary")
    clean_env.setenv("LLM_MODEL_ID", "primary-model")
    clean_env.setenv("LLM_BASE_URL", "https://primary.example/v1")

    client = config.get_openai_client()

    assert str(client.base_url) == "https://primary.example/v1/"
    assert client.api_key == "sk-primary"


def test_env_var_names_are_module_constants() -> None:
    """Env var names are centralized as module-level constants."""
    assert config.ENV_API_KEY == "LLM_API_KEY"
    assert config.ENV_ALT_BASE_URL == "LLM_ALT_BASE_URL"
    assert config.ENV_ALT_MODEL_ID_PRO == "LLM_ALT_MODEL_ID_PRO"
