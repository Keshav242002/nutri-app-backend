"""
Provider-agnostic LLM client.

Two public functions — all downstream code calls only these:
  chat_completion(messages, json_mode=False, stream=False) -> str | Iterator[str]
  structured_completion(messages, schema) -> dict

Both raise ExternalServiceError(code=LLM_FAILURE) on hard failure.
Transient errors (timeout, connection, 502/503) are retried up to 2 times.

JSON contract: we ALWAYS embed the schema in the prompt and instruct the model to
return strict JSON. We do NOT trust provider schema enforcement — it varies. Instead
we (a) ask for JSON in the prompt, (b) use json_object response_format where supported,
(c) parse defensively and strip markdown fences (common with free Gemini models).
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from typing import Any

from core.error_codes import LLM_FAILURE
from core.exceptions import ExternalServiceError

from .llm_config import Provider, ProviderConfig, get_provider_config

logger = logging.getLogger(__name__)

_TRANSIENT_RETRY_DELAY_S = 1.5
_MAX_TRANSIENT_RETRIES = 2

_PARSE_RETRY_SYSTEM_MSG = (
    "Return ONLY a valid JSON object. No markdown, no code fences, no reasoning, "
    "no explanation. Your entire response must start with { and end with }."
)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def chat_completion(
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    stream: bool = False,
) -> str | Iterator[str]:
    """Return assistant text or a token iterator if stream=True."""
    cfg = get_provider_config()
    if cfg.provider == Provider.GEMINI_NATIVE:
        return _gemini_native_completion(cfg, messages, json_mode=json_mode, stream=stream)
    return _openai_compatible_completion(cfg, messages, json_mode=json_mode, stream=stream)


def structured_completion(
    messages: list[dict[str, str]],
    schema: dict[str, Any],  # noqa: ARG001 — schema is embedded in prompt by caller
) -> dict[str, Any]:
    """Return a parsed JSON dict. Always asks for JSON; parses defensively.

    On parse failure retries once with a strengthened system instruction.
    Network retries (transient errors) are handled separately inside chat_completion.
    """
    cfg = get_provider_config()
    raw = chat_completion(messages, json_mode=True, stream=False)
    assert isinstance(raw, str)

    try:
        return _parse_json_strict(raw, cfg)
    except ExternalServiceError:
        logger.warning(
            "llm_parse_retry",
            extra={
                "event": "llm_parse_retry",
                "provider": cfg.provider.value,
                "raw_prefix": raw[:200],
            },
        )

    retry_messages = list(messages) + [{"role": "system", "content": _PARSE_RETRY_SYSTEM_MSG}]
    retry_raw = chat_completion(retry_messages, json_mode=True, stream=False)
    assert isinstance(retry_raw, str)

    try:
        return _parse_json_strict(retry_raw, cfg)
    except ExternalServiceError:
        logger.error(
            "llm_parse_retry_failed",
            extra={
                "event": "llm_parse_retry_failed",
                "provider": cfg.provider.value,
                "retry_raw_prefix": retry_raw[:200],
            },
        )
        raise


# --------------------------------------------------------------------------- #
# OpenAI-compatible path (openrouter, openai, gemini_openai)
# --------------------------------------------------------------------------- #


def _get_openai_client(cfg: ProviderConfig) -> Any:
    """Lazily build an OpenAI SDK client. Imported lazily so tests don't need the package."""
    from openai import OpenAI

    if not cfg.api_key:
        raise ExternalServiceError(
            code=LLM_FAILURE,
            message=f"No API key configured for provider '{cfg.provider.value}'.",
        )

    extra_headers: dict[str, str] = {}
    if cfg.provider == Provider.OPENROUTER:
        extra_headers = {"HTTP-Referer": "https://nutriplan.app", "X-Title": "NutriPlan"}

    return OpenAI(
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        timeout=cfg.timeout_seconds,
        default_headers=extra_headers or None,
    )


def _openai_compatible_completion(
    cfg: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    stream: bool,
) -> str | Iterator[str]:
    client = _get_openai_client(cfg)
    kwargs: dict[str, Any] = {"model": cfg.model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if stream:
        kwargs["stream"] = True

    last_exc: Exception | None = None
    for attempt in range(_MAX_TRANSIENT_RETRIES + 1):
        try:
            if stream:
                return _stream_openai(client, kwargs, cfg)
            completion = client.chat.completions.create(**kwargs)
            text = completion.choices[0].message.content or ""
            usage = getattr(completion, "usage", None)
            logger.info(
                "llm_completion",
                extra={
                    "event": "llm_completion",
                    "provider": cfg.provider.value,
                    "model": cfg.model,
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                },
            )
            return text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_transient(exc) and attempt < _MAX_TRANSIENT_RETRIES:
                time.sleep(_TRANSIENT_RETRY_DELAY_S)
                continue
            break

    logger.error(
        "llm_failure",
        extra={
            "event": "llm_failure",
            "provider": cfg.provider.value,
            "model": cfg.model,
            "error": str(last_exc),
        },
    )
    raise ExternalServiceError(
        code=LLM_FAILURE,
        message=f"LLM call failed ({cfg.provider.value}): {last_exc}",
    ) from last_exc


def _stream_openai(client: Any, kwargs: dict[str, Any], cfg: ProviderConfig) -> Iterator[str]:
    """Yield text chunks from an OpenAI-compatible streaming response."""
    try:
        for chunk in client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "llm_stream_failure",
            extra={
                "event": "llm_stream_failure",
                "provider": cfg.provider.value,
                "error": str(exc),
            },
        )
        raise ExternalServiceError(
            code=LLM_FAILURE, message=f"LLM stream failed ({cfg.provider.value}): {exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# Gemini native path (google-genai SDK)
# --------------------------------------------------------------------------- #


def _gemini_native_completion(
    cfg: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    json_mode: bool,
    stream: bool,
) -> str | Iterator[str]:
    """Adapt google-genai SDK to the same return contract."""
    from google import genai
    from google.genai import types as genai_types

    if not cfg.api_key:
        raise ExternalServiceError(
            code=LLM_FAILURE, message="No GEMINI_API_KEY configured for gemini_native."
        )

    client = genai.Client(api_key=cfg.api_key)
    system_text = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    convo_parts = [m["content"] for m in messages if m["role"] != "system"]
    contents = "\n\n".join(convo_parts)

    config = genai_types.GenerateContentConfig(
        system_instruction=system_text or None,
        response_mime_type="application/json" if json_mode else "text/plain",
    )

    try:
        if stream:
            return _stream_gemini(client, cfg, contents, config)
        resp = client.models.generate_content(model=cfg.model, contents=contents, config=config)
        logger.info(
            "llm_completion",
            extra={"event": "llm_completion", "provider": cfg.provider.value, "model": cfg.model},
        )
        return resp.text or ""
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "llm_failure",
            extra={"event": "llm_failure", "provider": cfg.provider.value, "error": str(exc)},
        )
        raise ExternalServiceError(
            code=LLM_FAILURE, message=f"Gemini native call failed: {exc}"
        ) from exc


def _stream_gemini(client: Any, cfg: ProviderConfig, contents: str, config: Any) -> Iterator[str]:
    try:
        for chunk in client.models.generate_content_stream(
            model=cfg.model, contents=contents, config=config
        ):
            if chunk.text:
                yield chunk.text
    except Exception as exc:  # noqa: BLE001
        raise ExternalServiceError(
            code=LLM_FAILURE, message=f"Gemini native stream failed: {exc}"
        ) from exc


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _is_transient(exc: Exception) -> bool:
    """Best-effort classification of retryable errors across SDKs."""
    name = type(exc).__name__.lower()
    markers = ("timeout", "connection", "ratelimit", "503", "502", "overloaded")
    return any(m in name or m in str(exc).lower() for m in markers)


def _parse_json_strict(raw: str, cfg: ProviderConfig) -> dict[str, Any]:
    """Parse model output as JSON. Strips markdown fences added by some models."""
    text = raw.strip()

    # Strip markdown fences: ```json ... ``` or ``` ... ```
    fence_re = re.compile(r"^```(?:json)?\s*\n?(.*?)```\s*$", re.DOTALL)
    m = fence_re.match(text)
    if m:
        text = m.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error(
            "llm_json_parse_failure",
            extra={
                "event": "llm_json_parse_failure",
                "provider": cfg.provider.value,
                "raw_prefix": raw[:500],
            },
        )
        raise ExternalServiceError(
            code=LLM_FAILURE,
            message=f"Model returned non-JSON output ({cfg.provider.value}).",
        ) from exc
    if not isinstance(parsed, dict):
        raise ExternalServiceError(
            code=LLM_FAILURE, message="Model returned JSON but not an object."
        )
    return parsed
