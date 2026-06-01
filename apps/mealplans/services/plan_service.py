from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db.models import Sum

from apps.mealplans.models import MealPlan
from apps.mealplans.services.engine import NoSuitableRecipeError, select_recipe  # noqa: F401
from apps.profiles.services.profiles import get_profile
from core.audit import audit_log
from core.error_codes import MEAL_PLAN_NOT_FOUND, REGENERATE_LIMIT
from core.exceptions import NotFoundError, RateLimitError

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)


def _invalidate_grocery_list(user: User, plan_date: date) -> None:
    """Delete cached grocery list for the ISO week containing plan_date."""
    from apps.mealplans.models import GroceryList  # local import — GroceryList lives in same app

    week_monday = plan_date - timedelta(days=plan_date.weekday())
    count, _ = GroceryList.objects.filter(user=user, week_start_date=week_monday).delete()
    if count:
        log.info(
            "event=grocery_list_invalidated user_id=%s week_start=%s",
            user.pk,
            week_monday,
        )


@audit_log("mealplan.generate")
def get_or_generate_plan(user: User, plan_date: date) -> MealPlan:
    """Return existing MealPlan for (user, plan_date) or generate and persist a new one."""
    try:
        return MealPlan.objects.select_related("breakfast", "lunch", "dinner").get(
            user=user, plan_date=plan_date
        )
    except MealPlan.DoesNotExist:
        pass

    profile = get_profile(user)  # raises NotFoundError(PROFILE_NOT_FOUND) if missing

    breakfast = select_recipe(profile, "breakfast", plan_date)
    lunch = select_recipe(profile, "lunch", plan_date)
    dinner = select_recipe(profile, "dinner", plan_date)

    plan = MealPlan(
        user=user,
        plan_date=plan_date,
        breakfast=breakfast,
        lunch=lunch,
        dinner=dinner,
        generated_by="rules",
        regeneration_count={"breakfast": 0, "lunch": 0, "dinner": 0},
    )
    plan.full_clean()
    plan.save()
    log.info(
        "event=meal_plan_generated user_id=%s plan_date=%s",
        user.pk,
        plan_date,
    )
    return plan


@audit_log("mealplan.regenerate_slot")
def regenerate_slot(user: User, plan_date: date, slot: str) -> MealPlan:
    """Swap one slot in an existing MealPlan. Rate limited to 3 regenerations per slot per week."""
    try:
        plan = MealPlan.objects.get(user=user, plan_date=plan_date)
    except MealPlan.DoesNotExist:
        raise NotFoundError(
            code=MEAL_PLAN_NOT_FOUND,
            message=f"No meal plan found for {plan_date}",
        ) from None

    regen_count = plan.regeneration_count.get(slot, 0)
    if regen_count >= 3:
        raise RateLimitError(
            code=REGENERATE_LIMIT,
            message=f"Slot '{slot}' has been regenerated 3 times this week",
        )

    current_recipe_id: int | None = getattr(plan, f"{slot}_id")
    exclude_ids = [current_recipe_id] if current_recipe_id is not None else []

    profile = get_profile(user)
    new_recipe = select_recipe(
        profile=profile,
        slot=slot,
        plan_date=plan_date,
        exclude_recipe_ids=exclude_ids,
    )

    setattr(plan, slot, new_recipe)
    plan.regeneration_count[slot] = regen_count + 1
    plan.save(update_fields=[slot, "regeneration_count", "updated_at"])

    log.info(
        "event=meal_plan_slot_regenerated user_id=%s plan_date=%s slot=%s count=%d",
        user.pk,
        plan_date,
        slot,
        plan.regeneration_count[slot],
    )
    _invalidate_grocery_list(user, plan_date)
    return plan


@audit_log("mealplan.regenerate_plan")
def regenerate_plan(user: User, plan_date: date) -> MealPlan:
    """Delete and regenerate a full MealPlan. Rate limited to 3 full regenerations per ISO week."""
    week_start = plan_date - timedelta(days=plan_date.weekday())
    week_end = week_start + timedelta(days=6)

    week_regen_total = (
        MealPlan.objects.filter(
            user=user,
            plan_date__range=(week_start, week_end),
            full_plan_regenerations__gt=0,
        ).aggregate(total=Sum("full_plan_regenerations"))["total"]
        or 0
    )

    if week_regen_total >= 3:
        raise RateLimitError(
            code=REGENERATE_LIMIT,
            message="Full plan has been regenerated 3 times this week",
        )

    existing = MealPlan.objects.filter(user=user, plan_date=plan_date).first()
    prev_regen_count: int = existing.full_plan_regenerations if existing is not None else 0
    if existing is not None:
        existing.delete()

    plan = get_or_generate_plan(user, plan_date)
    plan.full_plan_regenerations = prev_regen_count + 1
    plan.save(update_fields=["full_plan_regenerations", "updated_at"])

    log.info(
        "event=meal_plan_regenerated user_id=%s plan_date=%s total_regens=%d",
        user.pk,
        plan_date,
        plan.full_plan_regenerations,
    )
    _invalidate_grocery_list(user, plan_date)
    return plan
