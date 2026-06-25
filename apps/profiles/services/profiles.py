"""
Profile service layer — upsert_profile, get_profile, update_profile.

All writes call model.full_clean() before model.save() per CLAUDE.md §7.
Disclaimer gate, Jain rule, dislikes normalisation, and budget derivation
all live here — NOT in the serializer or model.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.accounts.models import User
from apps.profiles.models import (
    ALLERGY_VOCAB,
    SECONDARY_CUISINE_VOCAB,
    DietaryProfile,
)
from core.audit import audit_log
from core.error_codes import PROFILE_NOT_FOUND, VALIDATION_ERROR
from core.exceptions import AppValidationError, NotFoundError

logger = logging.getLogger(__name__)

# Fallback timezone for users without a profile. Mirrors the default of
# DietaryProfile.timezone — keep the two in sync.
DEFAULT_USER_TIMEZONE = "Asia/Kolkata"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_jain_rule(data: dict[str, Any]) -> None:
    """If diet_pattern is jain, force no_onion_garlic=True regardless of client input."""
    if data.get("diet_pattern") == "jain":
        data["no_onion_garlic"] = True


def _normalise_dislikes(data: dict[str, Any]) -> None:
    """Lowercase, strip, deduplicate dislikes; drop empty strings; enforce max 30."""
    raw: list[str] = data.get("dislikes", [])
    cleaned: list[str] = list(dict.fromkeys(item.lower().strip() for item in raw if item.strip()))
    if len(cleaned) > 30:
        raise AppValidationError(
            message="dislikes may contain at most 30 items.",
            code=VALIDATION_ERROR,
        )
    data["dislikes"] = cleaned


def _validate_secondary_cuisines(data: dict[str, Any]) -> None:
    """Validate each entry in secondary_cuisine_preferences against controlled vocab."""
    prefs: list[str] = data.get("secondary_cuisine_preferences", [])
    invalid = [p for p in prefs if p not in SECONDARY_CUISINE_VOCAB]
    if invalid:
        raise AppValidationError(
            message=f"Invalid secondary_cuisine_preferences: {invalid}. "
            f"Allowed values: {SECONDARY_CUISINE_VOCAB}",
            code=VALIDATION_ERROR,
        )


def _validate_allergies(data: dict[str, Any]) -> None:
    """Validate each entry in allergies against controlled vocab."""
    allergies: list[str] = data.get("allergies", [])
    invalid = [a for a in allergies if a not in ALLERGY_VOCAB]
    if invalid:
        raise AppValidationError(
            message=f"Invalid allergies: {invalid}. Allowed values: {ALLERGY_VOCAB}",
            code=VALIDATION_ERROR,
        )


def _check_disclaimer(data: dict[str, Any]) -> None:
    """
    Pop disclaimer_acknowledged from data (it is never stored).
    Raise AppValidationError if it is not True.
    """
    acknowledged = data.pop("disclaimer_acknowledged", None)
    if acknowledged is not True:
        raise AppValidationError(
            message="Disclaimer must be acknowledged to submit a profile.",
            code=VALIDATION_ERROR,
        )


def _derive_budget(data: dict[str, Any], require_budget: bool = True) -> None:
    """
    Enforce budget derivation rules (service layer, not model):
      - At least one of daily/weekly is required (when require_budget=True)
      - Only daily given → weekly = daily * 7
      - Only weekly given → daily = weekly / 7
      - Both given → weekly must equal daily * 7 within ±5%

    For partial updates (require_budget=False): if NEITHER budget key is present
    in data at all, skip derivation entirely (the existing stored values are authoritative).
    """
    has_daily_key = "daily_food_budget_inr" in data
    has_weekly_key = "weekly_food_budget_inr" in data

    if not has_daily_key and not has_weekly_key:
        if require_budget:
            raise AppValidationError(
                message=(
                    "At least one of daily_food_budget_inr or weekly_food_budget_inr is required."
                ),
                code=VALIDATION_ERROR,
            )
        return  # partial update — leave stored values alone
    daily = data.get("daily_food_budget_inr")
    weekly = data.get("weekly_food_budget_inr")

    # Normalise to Decimal for arithmetic; None stays None
    if daily is not None:
        daily = Decimal(str(daily))
    if weekly is not None:
        weekly = Decimal(str(weekly))

    if daily is None and weekly is None:
        raise AppValidationError(
            message="At least one of daily_food_budget_inr or weekly_food_budget_inr is required.",
            code=VALIDATION_ERROR,
        )

    if daily is not None and weekly is None:
        weekly = daily * 7
    elif weekly is not None and daily is None:
        daily = (weekly / 7).quantize(Decimal("0.01"))
    else:
        # Both provided — check consistency within ±5%
        assert daily is not None and weekly is not None
        expected_weekly = daily * 7
        tolerance = expected_weekly * Decimal("0.05")
        if abs(weekly - expected_weekly) > tolerance:
            raise AppValidationError(
                message=(
                    "weekly_food_budget_inr must equal daily_food_budget_inr × 7 "
                    "within ±5%. "
                    f"Got daily={daily}, weekly={weekly}, expected weekly≈{expected_weekly}."
                ),
                code=VALIDATION_ERROR,
            )

    data["daily_food_budget_inr"] = daily
    data["weekly_food_budget_inr"] = weekly


def _apply_normalisation(
    data: dict[str, Any],
    require_disclaimer: bool = True,
    require_budget: bool = True,
) -> None:
    """Apply all pre-save normalisation rules in the correct order."""
    if require_disclaimer:
        _check_disclaimer(data)  # pops disclaimer_acknowledged
    else:
        data.pop("disclaimer_acknowledged", None)  # silently discard if present
    _apply_jain_rule(data)
    _normalise_dislikes(data)
    _validate_secondary_cuisines(data)
    _validate_allergies(data)
    _derive_budget(data, require_budget=require_budget)


def _assign_fields(profile: DietaryProfile, data: dict[str, Any]) -> None:
    """Assign all keys from data onto profile (used for both create and update)."""
    for key, value in data.items():
        setattr(profile, key, value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@audit_log("profile.create")
def upsert_profile(user: User, data: dict[str, Any]) -> tuple[DietaryProfile, bool]:
    """
    Idempotent — creates or updates the user's DietaryProfile.

    Returns (profile, created) where created is True on first-time creation.

    Steps:
      1. Apply normalisation (Jain rule, dislikes, disclaimer, budget derivation)
      2. get_or_create profile record
      3. Assign fields
      4. full_clean() — fires model validators
      5. save() — triggers compute_targets() via save() override
    """
    _apply_normalisation(data)

    try:
        profile = DietaryProfile.objects.get(user=user)
        created = False
    except DietaryProfile.DoesNotExist:
        profile = DietaryProfile(user=user)
        created = True

    _assign_fields(profile, data)

    try:
        profile.full_clean()
    except DjangoValidationError as exc:
        logger.error(
            "profile_validation_failed",
            extra={
                "event": "profile_validation_failed",
                "user_id": user.pk,
                "error_code": VALIDATION_ERROR,
            },
        )
        raise AppValidationError(
            message=str(exc),
            code=VALIDATION_ERROR,
        ) from exc

    profile.save()

    event = "profile_created" if created else "profile_updated"
    logger.info(event, extra={"event": event, "user_id": user.pk})

    return profile, created


def get_profile(user: User) -> DietaryProfile:
    """
    Return the user's DietaryProfile or raise NotFoundError(PROFILE_NOT_FOUND).
    No logging — trivial pass-through per §7.
    """
    try:
        return DietaryProfile.objects.get(user=user)
    except DietaryProfile.DoesNotExist:
        raise NotFoundError(
            message="Profile not found.",
            code=PROFILE_NOT_FOUND,
        ) from None


def get_user_local_today(user: User) -> date:
    """
    Return the current calendar date in the user's configured timezone.

    "Today" must be computed in the user's timezone, not the server's UTC,
    so endpoints like the today meal plan agree with the client (which sends
    its local date to the nutrition/tracker endpoints). Raises
    NotFoundError(PROFILE_NOT_FOUND) if the user has no profile.
    """
    profile = get_profile(user)
    return datetime.now(tz=ZoneInfo(profile.timezone)).date()


def get_user_local_today_or_default(user: User) -> date:
    """
    Like [get_user_local_today] but for callers that must not 404 when the
    user has no profile (e.g. the week-list endpoint, which returns an empty
    list rather than requiring onboarding). Falls back to the default user
    timezone so "today" is still local rather than server-UTC.
    """
    try:
        tz_name = get_profile(user).timezone
    except NotFoundError:
        tz_name = DEFAULT_USER_TIMEZONE
    return datetime.now(tz=ZoneInfo(tz_name)).date()


@audit_log("profile.update")
def update_profile(user: User, data: dict[str, Any]) -> DietaryProfile:
    """
    Partial update — only fields present in data are changed.
    Re-applies all normalisation rules and recomputes targets on save.

    # TODO(M2): invalidate today's MealPlan cache here when M4 is built
    """
    profile = get_profile(user)
    old_target_calories = profile.target_calories

    _apply_normalisation(data, require_disclaimer=False, require_budget=False)
    _assign_fields(profile, data)

    try:
        profile.full_clean()
    except DjangoValidationError as exc:
        logger.error(
            "profile_validation_failed",
            extra={
                "event": "profile_validation_failed",
                "user_id": user.pk,
                "error_code": VALIDATION_ERROR,
            },
        )
        raise AppValidationError(
            message=str(exc),
            code=VALIDATION_ERROR,
        ) from exc

    profile.save()

    logger.info("profile_updated", extra={"event": "profile_updated", "user_id": user.pk})

    _maybe_notify_goal_updated(user, old_target_calories, profile.target_calories)

    return profile


def _maybe_notify_goal_updated(
    user: User, old_target_calories: int | None, new_target_calories: int | None
) -> None:
    """Notify when the calorie target changed. Soft dependency — never breaks the update."""
    if new_target_calories is None or new_target_calories == old_target_calories:
        return
    try:
        from apps.notifications.models import CATEGORY_GOAL_UPDATED
        from apps.notifications.services.notification_service import dispatch

        dispatch(
            user,
            CATEGORY_GOAL_UPDATED,
            dedup_key=f"goal-updated:{user.pk}:{new_target_calories}",
            context={"target_calories": new_target_calories},
        )
    except Exception as exc:  # noqa: BLE001 — intentional soft dependency
        logger.warning(
            "goal_updated_notify_failed",
            extra={"event": "goal_updated_notify_failed", "user_id": user.pk, "error": str(exc)},
        )
