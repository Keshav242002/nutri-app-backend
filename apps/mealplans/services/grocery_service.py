from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from apps.mealplans.models import (
    CATEGORY_DISPLAY_NAMES,
    CATEGORY_DISPLAY_ORDER,
    GroceryList,
    MealPlan,
)
from apps.profiles.services.profiles import get_profile

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)

RETAIL_ROUNDING: dict[str, tuple[float, str]] = {
    "spice": (50.0, "g"),
    "oil_fat": (250.0, "ml"),
    "vegetable": (250.0, "g"),
    "fruit": (250.0, "g"),
    "grain": (500.0, "g"),
    "pulse": (250.0, "g"),
    "dairy": (250.0, "ml"),
    "meat": (250.0, "g"),
    "fish": (250.0, "g"),
    "egg": (1.0, "pcs"),
    "nut_seed": (100.0, "g"),
    "sweetener": (250.0, "g"),
    "beverage": (50.0, "g"),
    "processed": (1.0, "pcs"),
}

PANTRY_STAPLE_THRESHOLD_G = 25.0


def _round_to_retail_unit(grams: float, category: str) -> tuple[float, str]:
    """Round raw gram total up to the nearest practical retail purchase unit."""
    round_to, unit = RETAIL_ROUNDING.get(category, (250.0, "g"))
    return _format_display_quantity(grams, round_to, unit)


def _format_display_quantity(grams: float, round_to: float, unit: str) -> tuple[float, str]:
    """Round up to retail unit and return (value, unit) for display."""
    if unit == "pcs":
        count = math.ceil(grams / 50.0)
        return (float(count), "pcs")

    rounded = math.ceil(grams / round_to) * round_to
    if rounded >= 1000:
        return (rounded / 1000.0, "kg")
    return (rounded, unit)


def get_or_compute_grocery_list(user: User, week_start_date: date) -> GroceryList:
    """Return cached GroceryList for the week or compute and persist a new one."""
    try:
        return GroceryList.objects.get(user=user, week_start_date=week_start_date)
    except GroceryList.DoesNotExist:
        pass

    return _compute_and_persist(user, week_start_date)


def _compute_and_persist(user: User, week_start_date: date) -> GroceryList:
    """Compute grocery list from this week's meal plans and persist it."""
    from apps.recipes.models import RecipeIngredient

    profile = get_profile(user)
    household_size = max(1, profile.household_size)

    week_end = week_start_date + timedelta(days=6)
    plans = list(
        MealPlan.objects.filter(
            user=user, plan_date__range=(week_start_date, week_end)
        ).select_related("breakfast", "lunch", "dinner")
    )

    # Count recipe usages and meal slots across all days
    recipe_usage_count: dict[int, int] = defaultdict(int)
    meals_covered = 0
    for plan in plans:
        for slot in ("breakfast", "lunch", "dinner"):
            recipe = getattr(plan, slot)
            if recipe is not None:
                recipe_usage_count[recipe.id] += 1
                meals_covered += 1

    recipe_ids = set(recipe_usage_count.keys())

    ingredient_totals: dict[str, float] = defaultdict(float)
    recipe_counts: dict[str, int] = defaultdict(int)
    ingredients_by_app_id: dict[str, Any] = {}

    if recipe_ids:
        ris = RecipeIngredient.objects.filter(recipe_id__in=recipe_ids).select_related(
            "ingredient", "recipe"
        )
        for ri in ris:
            app_id = ri.ingredient.app_id
            usage_count = recipe_usage_count[ri.recipe_id]
            recipe_servings = ri.recipe.servings or 1
            # Scale quantities so all household members are fed (round up to full batch)
            scaling_factor = max(1.0, household_size / recipe_servings)
            scaled_grams = float(ri.quantity_grams) * scaling_factor * usage_count
            ingredient_totals[app_id] += scaled_grams
            recipe_counts[app_id] += usage_count
            ingredients_by_app_id[app_id] = ri.ingredient

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total_cost = 0.0
    priced_count = 0

    for app_id, total_grams in ingredient_totals.items():
        ingredient = ingredients_by_app_id[app_id]
        category = ingredient.category

        display_value, display_unit = _round_to_retail_unit(total_grams, category)
        display_quantity = f"{display_value:g} {display_unit}"

        item_cost: float | None = None
        price_per_kg = ingredient.approximate_price_inr_per_kg
        if price_per_kg is not None:
            item_cost = round(float(price_per_kg) * (total_grams / 1000.0), 2)
            total_cost += item_cost
            priced_count += 1

        pantry_staple = (category == "spice") and (total_grams < PANTRY_STAPLE_THRESHOLD_G)

        by_category[category].append(
            {
                "ingredient_app_id": app_id,
                "ingredient_name": ingredient.name,
                "total_grams": round(total_grams, 2),
                "display_quantity": display_quantity,
                "display_quantity_value": display_value,
                "display_unit": display_unit,
                "estimated_cost_inr": item_cost,
                "recipe_count": recipe_counts[app_id],
                "pantry_staple": pantry_staple,
                "notes": "",
            }
        )

    categories: list[dict[str, Any]] = []
    for cat in CATEGORY_DISPLAY_ORDER:
        if cat not in by_category:
            continue
        categories.append(
            {
                "category": cat,
                "category_display": CATEGORY_DISPLAY_NAMES.get(cat, cat),
                "items": sorted(by_category[cat], key=lambda x: x["ingredient_name"]),
            }
        )

    total_items = sum(len(c["items"]) for c in categories)
    total_categories = len(categories)
    cost_coverage_pct = round(priced_count / total_items * 100) if total_items > 0 else 0
    estimated_total: float | None = round(total_cost, 2) if priced_count > 0 else None

    items: dict[str, Any] = {
        "categories": categories,
        "summary": {
            "total_items": total_items,
            "total_categories": total_categories,
            "estimated_total_cost_inr": estimated_total,
            "cost_coverage_pct": cost_coverage_pct,
            "household_size": household_size,
            "days_covered": len(plans),
            "meals_covered": meals_covered,
        },
    }

    gl = GroceryList(
        user=user,
        week_start_date=week_start_date,
        items=items,
        estimated_cost_inr=estimated_total,
    )
    gl.full_clean()
    gl.save()

    log.info(
        "event=grocery_list_computed user_id=%s week_start=%s items=%d days=%d cost_inr=%s",
        user.pk,
        week_start_date,
        total_items,
        len(plans),
        estimated_total,
    )

    return gl
