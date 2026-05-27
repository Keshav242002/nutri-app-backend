from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db import transaction

from apps.mealplans.models import GroceryList, MealPlan
from apps.mealplans.services.plan_service import get_or_generate_plan

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)


def generate_weekly_plan(user: User, reference_date: date | None = None) -> list[MealPlan]:
    """Generate meal plans for the current (or specified) week.

    First-time user (no existing MealPlan rows): today through upcoming Sunday.
    Returning user: Monday through Sunday of the ISO week containing today, filling gaps only.

    Atomic: if any day raises NoSuitableRecipeError the entire batch rolls back.
    Idempotent: days that already have a MealPlan are skipped.
    Invalidates the cached GroceryList for the week after generation.
    """
    today = reference_date or date.today()

    has_any_plan = MealPlan.objects.filter(user=user).exists()
    if not has_any_plan:
        start_date = today
        end_date = today + timedelta(days=(6 - today.weekday()))
    else:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)

    existing: dict[date, MealPlan] = {
        p.plan_date: p
        for p in MealPlan.objects.filter(
            user=user, plan_date__range=(start_date, end_date)
        ).select_related("breakfast", "lunch", "dinner")
    }

    new_plans: list[MealPlan] = []
    with transaction.atomic():
        for offset in range((end_date - start_date).days + 1):
            day = start_date + timedelta(days=offset)
            if day in existing:
                continue
            plan = get_or_generate_plan(user, day)
            new_plans.append(plan)

    week_monday = start_date - timedelta(days=start_date.weekday())
    count, _ = GroceryList.objects.filter(user=user, week_start_date=week_monday).delete()
    if count:
        log.info(
            "event=grocery_list_invalidated user_id=%s week_start=%s reason=weekly_generate",
            user.pk,
            week_monday,
        )

    log.info(
        "event=weekly_plan_generated user_id=%s week_start=%s days_new=%d days_existing=%d",
        user.pk,
        week_monday,
        len(new_plans),
        len(existing),
    )

    all_plans = list(existing.values()) + new_plans
    return sorted(all_plans, key=lambda p: p.plan_date)
