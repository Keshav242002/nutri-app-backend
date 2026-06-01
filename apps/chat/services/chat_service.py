"""
Chat service — main orchestrator for all chat operations.

All LLM calls go through llm_client (never OpenAI or Gemini directly).
Rate limiting is counted at the ChatMessage level (role=user rows in last hour).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.chat.models import ChatMessage, ChatSession
from apps.recipes.models import Ingredient
from core.audit import audit_log
from core.error_codes import RATE_LIMITED
from core.exceptions import NotFoundError, RateLimitError

from .ai_recipe_validator import validate_and_persist_ai_recipe
from .llm_client import chat_completion, structured_completion
from .llm_config import get_provider_config
from .prompt_builder import build_ingredient_prompt, build_system_prompt

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

# Schema is embedded in the prompt by build_ingredient_prompt; not passed to the API.
_SCHEMA_PLACEHOLDER: dict[str, Any] = {}


def _get_chat_rate_limit() -> int:
    """Parse CHAT_RATE_LIMIT setting (e.g. '30/h') into an int count."""
    raw: str = getattr(settings, "CHAT_RATE_LIMIT", "30/h")
    return int(raw.split("/")[0])


def check_rate_limit(user: User) -> None:
    """Raise RateLimitError if user has sent ≥ CHAT_RATE_LIMIT messages in the last hour."""
    limit = _get_chat_rate_limit()
    one_hour_ago = timezone.now() - timedelta(hours=1)
    count = ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.Role.USER,
        created_at__gte=one_hour_ago,
    ).count()
    if count >= limit:
        logger.info(
            "chat_rate_limited",
            extra={"event": "chat_rate_limited", "user_id": user.pk, "count": count},
        )
        raise RateLimitError(
            code=RATE_LIMITED,
            message=f"Chat rate limit reached ({limit} messages/hour). Please try again later.",
        )


def create_session(user: User, title: str = "") -> ChatSession:
    """Create a new chat session for the user."""
    session = ChatSession(user=user, title=title)
    session.full_clean()
    session.save()
    logger.info(
        "chat_session_created",
        extra={"event": "chat_session_created", "user_id": user.pk, "session_id": session.pk},
    )
    return session


def list_sessions(user: User) -> QuerySet[ChatSession]:
    """Return all chat sessions for the user, newest first."""
    return ChatSession.objects.filter(user=user).order_by("-last_message_at")


def get_session_messages(session_id: int, user: User) -> QuerySet[ChatMessage]:
    """Return messages for a session, validating ownership. Raises NotFoundError if not owned."""
    try:
        session = ChatSession.objects.get(pk=session_id, user=user)
    except ChatSession.DoesNotExist as exc:
        raise NotFoundError(message="Chat session not found.") from exc
    return session.messages.order_by("created_at")


def _load_context(user: User) -> tuple[Any, Any]:
    """Load user profile and today's meal plan. Either may be None."""
    profile = None
    try:
        profile = user.profile
    except Exception:  # noqa: BLE001
        pass

    today_plan = None
    if profile is not None:
        try:
            from apps.mealplans.models import MealPlan

            today_plan = (
                MealPlan.objects.filter(user=user, plan_date=timezone.now().date())
                .select_related("breakfast", "lunch", "dinner")
                .first()
            )
        except Exception:  # noqa: BLE001
            pass

    return profile, today_plan


def _build_history(session: ChatSession, limit: int = 10) -> list[dict[str, str]]:
    """Return the last `limit` messages in OpenAI format for context."""
    recent = list(
        session.messages.filter(
            role__in=[ChatMessage.Role.USER, ChatMessage.Role.ASSISTANT]
        ).order_by("-created_at")[:limit]
    )
    return [{"role": m.role, "content": m.content} for m in reversed(recent)]


def _update_session_timestamp(session: ChatSession) -> None:
    ChatSession.objects.filter(pk=session.pk).update(last_message_at=timezone.now())


@audit_log("chat.message")
def send_message_chat(
    session: ChatSession,
    content: str,
    user: User,
) -> ChatMessage:
    """Free-chat mode: build context → call LLM → save both messages → return assistant message."""
    check_rate_limit(user)

    profile, today_plan = _load_context(user)

    messages: list[dict[str, str]] = []
    if profile is not None:
        messages.append({"role": "system", "content": build_system_prompt(profile, today_plan)})
    messages.extend(_build_history(session))
    messages.append({"role": "user", "content": content})

    # Save user message first
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=content,
    )

    cfg = get_provider_config()
    response_text = chat_completion(messages)
    assert isinstance(response_text, str)

    assistant_msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=response_text,
        metadata={"provider": cfg.provider.value, "model": cfg.model},
    )

    _update_session_timestamp(session)

    logger.info(
        "chat_message_sent",
        extra={
            "event": "chat_message_sent",
            "user_id": user.pk,
            "session_id": session.pk,
            "mode": "chat",
        },
    )
    return assistant_msg


def send_message_chat_stream(
    session: ChatSession,
    content: str,
    user: User,
) -> Iterator[str]:
    """Streaming chat mode. Yields SSE text chunks; saves full response after stream completes."""
    check_rate_limit(user)

    profile, today_plan = _load_context(user)

    messages: list[dict[str, str]] = []
    if profile is not None:
        messages.append({"role": "system", "content": build_system_prompt(profile, today_plan)})
    messages.extend(_build_history(session))
    messages.append({"role": "user", "content": content})

    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=content,
    )

    cfg = get_provider_config()
    stream = chat_completion(messages, stream=True)
    assert not isinstance(stream, str)

    full_response: list[str] = []
    for chunk in stream:
        full_response.append(chunk)
        yield chunk

    assembled = "".join(full_response)
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=assembled,
        metadata={"provider": cfg.provider.value, "model": cfg.model},
    )
    _update_session_timestamp(session)


def send_message_ingredient(
    session: ChatSession,
    content: str,
    ingredients: list[str],
    user: User,
) -> ChatMessage:
    """Ingredient mode: generate recipes → validate → save message with metadata.recipes."""
    check_rate_limit(user)

    profile, _ = _load_context(user)

    available_names = list(Ingredient.objects.filter(is_active=True).values_list("name", flat=True))

    messages = build_ingredient_prompt(
        ingredients=ingredients,
        profile=profile,
        available_ingredient_names=available_names,
        count=3,
    )

    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=content,
    )

    cfg = get_provider_config()
    raw_json = structured_completion(messages, schema=_SCHEMA_PLACEHOLDER)
    recipes_data: list[dict[str, Any]] = raw_json.get("recipes", [])

    logger.info(
        "ai_ingredient_raw_response",
        extra={
            "event": "ai_ingredient_raw_response",
            "recipe_count": len(recipes_data),
            "ingredient_names": [
                ing.get("ingredient_name", "?")
                for r in recipes_data
                for ing in r.get("ingredients", [])
            ],
        },
    )

    validated_recipe_ids: list[int] = []
    recipe_summaries: list[dict[str, Any]] = []
    for recipe_json in recipes_data:
        try:
            recipe = validate_and_persist_ai_recipe(recipe_json, user)
            validated_recipe_ids.append(recipe.pk)
            recipe_summaries.append(
                {
                    "id": recipe.pk,
                    "name": recipe.name,
                    "meal_type": recipe.meal_type,
                    "calories_per_serving": recipe.cached_calories_per_serving,
                    "servings": recipe.servings,
                }
            )
        except Exception as exc:  # noqa: BLE001
            recipe_name = recipe_json.get("name", "unknown")
            exc_type = type(exc).__name__
            exc_msg = str(exc)
            msg_dict = getattr(exc, "message_dict", None)
            logger.warning(
                "ai_recipe_validation_failed [recipe=%s] [%s: %s] [message_dict=%s]",
                recipe_name,
                exc_type,
                exc_msg,
                msg_dict,
                exc_info=True,
                extra={
                    "event": "ai_recipe_validation_failed",
                    "recipe_name": recipe_name,
                    "exc_type": exc_type,
                    "error": exc_msg,
                    "message_dict": msg_dict,
                },
            )

    response_text = (
        f"Here are {len(recipe_summaries)} recipe(s) I generated from your ingredients."
        if recipe_summaries
        else "I couldn't generate valid recipes from those ingredients. Please try different ones."
    )

    assistant_msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=response_text,
        metadata={
            "provider": cfg.provider.value,
            "model": cfg.model,
            "recipes": recipe_summaries,
            "validated": len(recipe_summaries) > 0,
        },
    )

    _update_session_timestamp(session)

    logger.info(
        "ingredient_mode_completed",
        extra={
            "event": "ingredient_mode_completed",
            "user_id": user.pk,
            "session_id": session.pk,
            "recipes_generated": len(recipe_summaries),
        },
    )
    return assistant_msg
