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
from .prompt_builder import (
    build_freeform_recipe_prompt,
    build_ingredient_prompt,
    build_system_prompt,
)

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


def _load_context(user: User) -> tuple[Any, Any, Any, list[Any]]:
    """Load user profile, today's meal plan, today's nutrition summary, and recent history.

    "Today" is resolved in the user's local timezone (not server UTC) via
    [get_user_local_today_or_default], matching the home/week endpoints. Recent history is
    the last 7 local days (``[today - 6, today]``) of DailyNutritionSummary rows that have at
    least one meal eaten, oldest first. Profile/plan/summary may be None; recent may be empty.
    """
    from apps.profiles.services.profiles import get_user_local_today_or_default

    profile = None
    try:
        profile = user.profile
    except Exception:  # noqa: BLE001
        pass

    today_plan = None
    today_summary = None
    recent_summaries: list[Any] = []
    if profile is not None:
        today = get_user_local_today_or_default(user)
        try:
            from apps.mealplans.models import MealPlan

            today_plan = (
                MealPlan.objects.filter(user=user, plan_date=today)
                .select_related("breakfast", "lunch", "dinner")
                .first()
            )
        except Exception:  # noqa: BLE001
            pass

        try:
            from apps.tracker.models import DailyNutritionSummary

            today_summary = DailyNutritionSummary.objects.filter(
                user=user, summary_date=today
            ).first()
        except Exception:  # noqa: BLE001
            pass

        try:
            from apps.tracker.models import DailyNutritionSummary

            recent_summaries = list(
                DailyNutritionSummary.objects.filter(
                    user=user,
                    summary_date__gte=today - timedelta(days=6),
                    summary_date__lte=today,
                    meals_eaten__gt=0,
                ).order_by("summary_date")
            )
        except Exception:  # noqa: BLE001
            pass

    return profile, today_plan, today_summary, recent_summaries


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

    profile, today_plan, today_summary, recent_summaries = _load_context(user)

    messages: list[dict[str, str]] = []
    if profile is not None:
        messages.append(
            {
                "role": "system",
                "content": build_system_prompt(
                    profile, today_plan, today_summary, recent_summaries
                ),
            }
        )
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

    profile, today_plan, today_summary, recent_summaries = _load_context(user)

    messages: list[dict[str, str]] = []
    if profile is not None:
        messages.append(
            {
                "role": "system",
                "content": build_system_prompt(
                    profile, today_plan, today_summary, recent_summaries
                ),
            }
        )
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


def _all_ingredients_known(ingredients: list[str], available_names: list[str]) -> bool:
    """Loose check: does every user-typed ingredient match an active DB ingredient?

    Users type casual terms ('rice', 'paneer'); DB names are specific ('Basmati rice
    (raw)'). A user ingredient is "known" if it is a substring of some active ingredient
    name, or a sufficiently-specific ingredient name is a substring of the user term.
    This is intentionally looser than the validator's resolver — it only decides which
    generation path to take (grounded vs free-form), not what gets persisted.
    """
    lowered = [n.lower() for n in available_names]
    for raw in ingredients:
        term = raw.strip().lower()
        if not term:
            continue
        matched = any(term in name or (len(name) >= 4 and name in term) for name in lowered)
        if not matched:
            return False
    return True


def _freeform_summary(recipe_json: dict[str, Any]) -> dict[str, Any]:
    """Build a display-only recipe card from a free-form (non-persisted) recipe payload.

    Carries the dish inline (ingredients + steps) since there is no DB row to link to.
    `loggable: False` signals the client not to offer logging — the user logs via the
    home-page "log something else" path if they actually cook it.
    """
    raw_ings = recipe_json.get("ingredients", []) or []
    inline_ings = [
        {
            "ingredient_name": (i.get("ingredient_name") or "").strip(),
            "quantity_grams": i.get("quantity_grams"),
        }
        for i in raw_ings
        if isinstance(i, dict)
    ]
    return {
        "name": (recipe_json.get("name") or "").strip(),
        "description": (recipe_json.get("description") or "").strip()[:140],
        "meal_type": (recipe_json.get("meal_type") or "").strip(),
        "servings": recipe_json.get("servings"),
        "ingredients": inline_ings,
        "steps": [s for s in (recipe_json.get("steps") or []) if isinstance(s, str)],
        "loggable": False,
        "source": "ai_freeform",
    }


def send_message_ingredient(
    session: ChatSession,
    content: str,
    ingredients: list[str],
    user: User,
) -> ChatMessage:
    """Ingredient mode: two-tier generation → save message with metadata.recipes.

    If every provided ingredient matches the curated DB (loose match), take the
    *grounded* path: generate against the approved ingredient list, validate, persist a
    Recipe, and return a loggable card with id/slug/nutrition. If ANY ingredient is
    unknown, take the *free-form* path: generate freely, do NOT persist, and return a
    display-only card (inline ingredients/steps, no nutrition, ``loggable: False``).
    """
    check_rate_limit(user)

    profile, _, _, _ = _load_context(user)

    available_names = list(Ingredient.objects.filter(is_active=True).values_list("name", flat=True))
    grounded = _all_ingredients_known(ingredients, available_names)

    if grounded:
        messages = build_ingredient_prompt(
            ingredients=ingredients,
            profile=profile,
            available_ingredient_names=available_names,
            count=1,
        )
    else:
        messages = build_freeform_recipe_prompt(
            ingredients=ingredients,
            profile=profile,
            count=1,
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
            "grounded": grounded,
            "recipe_count": len(recipes_data),
            "ingredient_names": [
                ing.get("ingredient_name", "?")
                for r in recipes_data
                for ing in r.get("ingredients", [])
            ],
        },
    )

    recipe_summaries: list[dict[str, Any]] = []
    if grounded:
        for recipe_json in recipes_data:
            try:
                recipe = validate_and_persist_ai_recipe(recipe_json, user)
                recipe_summaries.append(
                    {
                        "id": recipe.pk,
                        "name": recipe.name,
                        "slug": recipe.slug,  # for opening recipe detail on the client
                        # Recipe has no description column; carry the LLM-supplied
                        # one-liner through from the payload (truncated, "" when absent).
                        "description": (recipe_json.get("description") or "").strip()[:140],
                        "meal_type": recipe.meal_type,
                        "calories_per_serving": recipe.cached_calories_per_serving,
                        "servings": recipe.servings,
                        "loggable": True,
                        "source": "grounded",
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
    else:
        # Free-form path: display-only, never persisted.
        recipe_summaries = [_freeform_summary(r) for r in recipes_data if r.get("name")]

    if recipe_summaries and grounded:
        response_text = (
            f"Here are {len(recipe_summaries)} recipe(s) I generated from your ingredients."
        )
    elif recipe_summaries:
        response_text = (
            "Here's a recipe idea using your ingredients. Some aren't in our library yet, "
            "so I couldn't calculate nutrition — but here's how to make it."
        )
    else:
        response_text = (
            "I couldn't generate valid recipes from those ingredients. Please try different ones."
        )

    assistant_msg = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=response_text,
        metadata={
            "provider": cfg.provider.value,
            "model": cfg.model,
            "recipes": recipe_summaries,
            "validated": grounded and len(recipe_summaries) > 0,
            "freeform": not grounded,
        },
    )

    _update_session_timestamp(session)

    logger.info(
        "ingredient_mode_completed",
        extra={
            "event": "ingredient_mode_completed",
            "user_id": user.pk,
            "session_id": session.pk,
            "grounded": grounded,
            "recipes_generated": len(recipe_summaries),
        },
    )
    return assistant_msg
