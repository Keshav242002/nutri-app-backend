"""Upsert meal logs and trigger daily summary recomputation."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.tracker.models import (
    STATUS_ATE_CUSTOM,
    STATUS_ATE_PLANNED,
    STATUS_ATE_SUBSTITUTED,
    STATUS_PLANNED,
    STATUS_SKIPPED,
    MealLog,
)
from apps.tracker.services.nutrition_service import recompute_daily_summary
from core.audit import audit_log
from core.error_codes import VALIDATION_ERROR
from core.exceptions import AppValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)

# Statuses that involve eating a known recipe (so servings_eaten is meaningful)
_RECIPE_STATUSES = {STATUS_ATE_PLANNED, STATUS_ATE_SUBSTITUTED}

# Statuses where custom_* fields must be null
_NON_CUSTOM_STATUSES = {STATUS_PLANNED, STATUS_ATE_PLANNED, STATUS_ATE_SUBSTITUTED, STATUS_SKIPPED}

# Servings constraints (inclusive)
_SERVINGS_MIN = Decimal("0.25")
_SERVINGS_MAX = Decimal("6.00")
_SERVINGS_QUANTUM = Decimal("0.25")


def _validate_servings(servings: Decimal) -> None:
    """Enforce range [0.25, 6.00] and 0.25 multiples."""
    if servings < _SERVINGS_MIN or servings > _SERVINGS_MAX:
        raise AppValidationError(
            message=f"servings_eaten must be between {_SERVINGS_MIN} and {_SERVINGS_MAX}.",
            code=VALIDATION_ERROR,
        )
    # Must be a multiple of 0.25: remainder == 0 when divided by quantum
    remainder = servings % _SERVINGS_QUANTUM
    if remainder != Decimal("0"):
        raise AppValidationError(
            message="servings_eaten must be a multiple of 0.25 (e.g. 0.25, 0.50, 1.00, 1.75).",
            code=VALIDATION_ERROR,
        )


def _validate_custom_fields(status: str, kwargs: dict[str, Any]) -> None:
    """Enforce custom field presence/absence rules based on status."""
    custom_fields = [
        "custom_description",
        "custom_calories",
        "custom_protein_g",
        "custom_carbs_g",
        "custom_fat_g",
    ]

    if status == STATUS_ATE_CUSTOM:
        if not kwargs.get("custom_description"):
            raise AppValidationError(
                message="custom_description is required when status is ate_custom.",
                code=VALIDATION_ERROR,
            )
        if kwargs.get("custom_calories") is None:
            raise AppValidationError(
                message="custom_calories is required when status is ate_custom.",
                code=VALIDATION_ERROR,
            )
    elif status in _NON_CUSTOM_STATUSES:
        present = [f for f in custom_fields if kwargs.get(f) is not None]
        if present:
            raise AppValidationError(
                message=(
                    f"Custom fields ({', '.join(present)}) are only allowed "
                    "when status is ate_custom."
                ),
                code=VALIDATION_ERROR,
            )


def _validate_substituted(status: str, kwargs: dict[str, Any]) -> None:
    """ate_substituted requires actual_recipe or actual_recipe_id."""
    if status == STATUS_ATE_SUBSTITUTED:
        if not kwargs.get("actual_recipe") and not kwargs.get("actual_recipe_id"):
            raise AppValidationError(
                message="actual_recipe_id is required when status is ate_substituted.",
                code=VALIDATION_ERROR,
            )


def _auto_populate_planned_recipe(user: User, log_date: date, slot: str, meal_log: MealLog) -> None:
    """If planned_recipe is not set, look up the MealPlan for (user, log_date, slot)."""
    if meal_log.planned_recipe_id is not None:
        return
    try:
        from apps.mealplans.models import MealPlan

        plan = MealPlan.objects.get(user=user, plan_date=log_date)
        recipe = getattr(plan, slot, None)
        if recipe is not None:
            meal_log.planned_recipe = recipe
    except Exception:  # noqa: BLE001
        # No MealPlan for this date is fine — planned_recipe stays null
        pass


@audit_log("tracker.log")
def upsert_meal_log(
    user: User,
    log_date: date,
    slot: str,
    status: str,
    **kwargs: Any,
) -> MealLog:
    """
    Idempotent upsert of a MealLog by (user, log_date, slot).

    After persisting, triggers recompute_daily_summary synchronously.
    """
    # --- Validation ---
    _validate_custom_fields(status, kwargs)
    _validate_substituted(status, kwargs)

    # Resolve actual_recipe from actual_recipe_id if provided as integer
    actual_recipe_id = kwargs.pop("actual_recipe_id", None)

    servings_raw = kwargs.pop("servings_eaten", None)
    if status in _RECIPE_STATUSES:
        if servings_raw is None:
            servings = Decimal("1.00")
        else:
            servings = Decimal(str(servings_raw))
        _validate_servings(servings)
    else:
        # ate_custom → 1.00; planned/skipped → irrelevant (stored as 1.00)
        servings = Decimal("1.00")

    # Build or fetch existing MealLog
    try:
        meal_log = MealLog.objects.select_related("planned_recipe", "actual_recipe").get(
            user=user, log_date=log_date, slot=slot
        )
        created = False
    except MealLog.DoesNotExist:
        meal_log = MealLog(user=user, log_date=log_date, slot=slot)
        created = True

    meal_log.status = status
    meal_log.servings_eaten = servings

    # Apply recipe FKs
    if actual_recipe_id is not None:
        meal_log.actual_recipe_id = actual_recipe_id
    elif "actual_recipe" in kwargs:
        meal_log.actual_recipe = kwargs.pop("actual_recipe")

    # Apply remaining kwargs (custom fields, notes, planned_recipe)
    for field, value in kwargs.items():
        setattr(meal_log, field, value)

    # Clear custom fields when status is not ate_custom
    if status != STATUS_ATE_CUSTOM:
        meal_log.custom_description = None
        meal_log.custom_calories = None
        meal_log.custom_protein_g = None
        meal_log.custom_carbs_g = None
        meal_log.custom_fat_g = None

    # Auto-populate planned_recipe from the active MealPlan if not supplied
    _auto_populate_planned_recipe(user, log_date, slot, meal_log)

    try:
        meal_log.full_clean()
    except DjangoValidationError as exc:
        raise AppValidationError(
            message=str(exc.message_dict if hasattr(exc, "message_dict") else exc),
            code=VALIDATION_ERROR,
        ) from exc

    meal_log.save()

    event = "meal_log_created" if created else "meal_log_updated"
    log.info(
        "event=%s user_id=%s log_date=%s slot=%s status=%s",
        event,
        user.pk,
        log_date,
        slot,
        status,
    )

    recompute_daily_summary(user, log_date)
    return meal_log
