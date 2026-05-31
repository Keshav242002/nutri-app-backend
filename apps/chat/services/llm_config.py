"""
LLM provider configuration — single source of truth for which AI backend is active.

Switch providers by changing the AI_PROVIDER env var. Nothing else in the codebase
needs to change.

Supported providers:
  openrouter      — OpenAI-compatible gateway (default; has free models)
  openai          — OpenAI native (paid)
  gemini_openai   — Google Gemini via its OpenAI-compatible endpoint (free tier)
  gemini_native   — Google Gemini via the native google-genai SDK (free tier)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from django.conf import settings


class Provider(str, Enum):  # noqa: UP042
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    GEMINI_OPENAI = "gemini_openai"
    GEMINI_NATIVE = "gemini_native"


@dataclass(frozen=True)
class ProviderConfig:
    """Resolved configuration for the active provider."""

    provider: Provider
    api_key: str
    model: str
    base_url: str | None  # None for native SDKs that manage their own URL
    timeout_seconds: int
    # When False, we use json_object mode (valid JSON, no schema enforcement).
    supports_strict_schema: bool


_PROVIDER_DEFAULTS: dict[Provider, dict[str, Any]] = {
    Provider.OPENROUTER: {
        "base_url": "https://openrouter.ai/api/v1",
        "model_env": "OPENROUTER_MODEL",
        "model_default": "openrouter/free",
        "key_env": "OPENROUTER_API_KEY",
        "supports_strict_schema": False,
    },
    Provider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "model_env": "OPENAI_MODEL",
        "model_default": "gpt-4o",
        "key_env": "OPENAI_API_KEY",
        "supports_strict_schema": True,
    },
    Provider.GEMINI_OPENAI: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_env": "GEMINI_MODEL",
        "model_default": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
        "supports_strict_schema": False,
    },
    Provider.GEMINI_NATIVE: {
        "base_url": None,
        "model_env": "GEMINI_MODEL",
        "model_default": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
        "supports_strict_schema": True,
    },
}


def get_provider_config() -> ProviderConfig:
    """Resolve the active provider config from settings. Called lazily at request time."""
    raw = getattr(settings, "AI_PROVIDER", "openrouter").strip().lower()
    try:
        provider = Provider(raw)
    except ValueError as exc:
        valid = ", ".join(p.value for p in Provider)
        raise ValueError(f"Invalid AI_PROVIDER '{raw}'. Must be one of: {valid}") from exc

    defaults = _PROVIDER_DEFAULTS[provider]
    api_key = getattr(settings, defaults["key_env"], "") or ""
    model = getattr(settings, defaults["model_env"], "") or defaults["model_default"]
    timeout = int(getattr(settings, "LLM_TIMEOUT_SECONDS", 30))

    return ProviderConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=defaults["base_url"],
        timeout_seconds=timeout,
        supports_strict_schema=defaults["supports_strict_schema"],
    )
