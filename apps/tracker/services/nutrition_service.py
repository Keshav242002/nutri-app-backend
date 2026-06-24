"""Recompute DailyNutritionSummary from all MealLog rows for a (user, date)."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.tracker.models import (
    EATING_STATUSES,
    STATUS_ATE_CUSTOM,
    STATUS_ATE_PLANNED,
    STATUS_ATE_SUBSTITUTED,
    STATUS_SKIPPED,
    DailyNutritionSummary,
    MealLog,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)

_MICRO_KEYS = [
    "iron_mg",
    "calcium_mg",
    "vit_c_mg",
    "potassium_mg",
    "sodium_mg",
    "magnesium_mg",
    "zinc_mg",
    "vit_a_iu",
    "folate_ug",
    "vit_b12_ug",
]


def _recipe_nutrition_for_log(meal_log: MealLog) -> dict[str, Any]:
    """Extract per-serving cached_nutrition from the appropriate recipe FK for this log."""
    if meal_log.status == STATUS_ATE_PLANNED:
        recipe = meal_log.planned_recipe
    elif meal_log.status == STATUS_ATE_SUBSTITUTED:
        recipe = meal_log.actual_recipe
    else:
        return {}

    if recipe is None or recipe.cached_nutrition is None:
        return {}
    return recipe.cached_nutrition  # type: ignore[no-any-return]


def recompute_daily_summary(user: User, log_date: date) -> DailyNutritionSummary:
    """
    Walk all MealLog rows for (user, log_date), sum nutrition contributions,
    and upsert a DailyNutritionSummary. Idempotent.
    """
    logs = list(
        MealLog.objects.filter(user=user, log_date=log_date).select_related(
            "planned_recipe", "actual_recipe"
        )
    )

    total_calories: int = 0
    total_protein: Decimal = Decimal("0")
    total_carbs: Decimal = Decimal("0")
    total_fat: Decimal = Decimal("0")
    total_fiber: Decimal = Decimal("0")
    micro_totals: dict[str, float] = {k: 0.0 for k in _MICRO_KEYS}

    meals_eaten: int = 0
    meals_skipped: int = 0

    for meal_log in logs:
        if meal_log.status == STATUS_ATE_CUSTOM:
            meals_eaten += 1
            total_calories += meal_log.custom_calories or 0
            total_protein += Decimal(str(meal_log.custom_protein_g or 0))
            total_carbs += Decimal(str(meal_log.custom_carbs_g or 0))
            total_fat += Decimal(str(meal_log.custom_fat_g or 0))
            # custom logs have no fiber or micronutrient data
            continue

        if meal_log.status == STATUS_SKIPPED:
            meals_skipped += 1
            continue

        if meal_log.status in EATING_STATUSES:
            # ate_planned or ate_substituted
            nutrition = _recipe_nutrition_for_log(meal_log)
            if not nutrition:
                meals_eaten += 1
                continue

            servings = float(meal_log.servings_eaten)
            total_calories += round((nutrition.get("calories") or 0) * servings)
            total_protein += Decimal(str(round((nutrition.get("protein_g") or 0) * servings, 2)))
            total_carbs += Decimal(str(round((nutrition.get("carbs_g") or 0) * servings, 2)))
            total_fat += Decimal(str(round((nutrition.get("fat_g") or 0) * servings, 2)))
            total_fiber += Decimal(str(round((nutrition.get("fiber_g") or 0) * servings, 2)))

            micros: dict[str, Any] = nutrition.get("micronutrients") or {}
            for key in _MICRO_KEYS:
                micro_totals[key] += (micros.get(key) or 0) * servings

            meals_eaten += 1
        # status=planned → zero contribution, not counted

    merged_micros = {k: round(v, 2) for k, v in micro_totals.items()}

    summary, _ = DailyNutritionSummary.objects.update_or_create(
        user=user,
        summary_date=log_date,
        defaults={
            "calories": total_calories,
            "protein_g": total_protein,
            "carbs_g": total_carbs,
            "fat_g": total_fat,
            "fiber_g": total_fiber,
            "micronutrients": merged_micros,
            "meals_eaten": meals_eaten,
            "meals_skipped": meals_skipped,
        },
    )

    log.info(
        "event=daily_summary_recomputed user_id=%s date=%s calories=%d meals_eaten=%d",
        user.pk,
        log_date,
        total_calories,
        meals_eaten,
    )

    _maybe_notify_daily_target(user, log_date, summary)
    return summary


def _maybe_notify_daily_target(user: User, log_date: date, summary: DailyNutritionSummary) -> None:
    """Dispatch a 'daily target met' notification when calories + protein land in band.

    Soft dependency: any failure (no profile, unset targets, dispatch error) is swallowed
    so it never breaks the recompute. Idempotent via the dedup_key in dispatch().
    """
    try:
        from apps.notifications.models import CATEGORY_DAILY_TARGET
        from apps.notifications.services.notification_service import dispatch
        from apps.profiles.models import DietaryProfile

        profile = DietaryProfile.objects.filter(user=user).first()
        if profile is None or profile.target_calories is None or profile.target_protein_g is None:
            return

        target_cal = profile.target_calories
        target_protein = Decimal(str(profile.target_protein_g))
        calories_in_band = 0.9 * target_cal <= summary.calories <= 1.1 * target_cal
        protein_met = summary.protein_g >= Decimal("0.9") * target_protein
        if not (calories_in_band and protein_met):
            return

        dispatch(
            user,
            CATEGORY_DAILY_TARGET,
            dedup_key=f"daily-target:{user.pk}:{log_date.isoformat()}",
        )
    except Exception as exc:  # noqa: BLE001 — intentional soft dependency
        log.warning("event=daily_target_notify_failed user_id=%s error=%s", user.pk, exc)
