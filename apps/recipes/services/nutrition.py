import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from apps.recipes.models import Recipe

logger = logging.getLogger(__name__)


def compute_recipe_nutrition(recipe: Recipe) -> dict[str, Any]:
    """Sum ingredient-level nutrition × quantities into per-serving cached values on Recipe."""
    recipe_ingredients = list(recipe.recipe_ingredients.select_related("ingredient").all())

    total_calories: float = 0.0
    total_protein: float = 0.0
    total_carbs: float = 0.0
    total_fat: float = 0.0
    total_fiber: float = 0.0

    # Micronutrient running totals
    micro_keys = [
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
    micro_totals: dict[str, float] = {k: 0.0 for k in micro_keys}

    # Cost tracking
    total_cost: float = 0.0
    total_grams: float = 0.0
    priced_grams: float = 0.0

    for ri in recipe_ingredients:
        ing = ri.ingredient
        nutrition = ing.per_100g_nutrition or {}
        weight_fraction = float(ri.quantity_grams) / 100.0

        total_calories += (nutrition.get("calories") or 0) * weight_fraction
        total_protein += (nutrition.get("protein_g") or 0) * weight_fraction
        total_carbs += (nutrition.get("carbs_g") or 0) * weight_fraction
        total_fat += (nutrition.get("fat_g") or 0) * weight_fraction
        total_fiber += (nutrition.get("fiber_g") or 0) * weight_fraction

        micros = nutrition.get("micronutrients") or {}
        for key in micro_keys:
            micro_totals[key] += (micros.get(key) or 0) * weight_fraction

        qty_grams = float(ri.quantity_grams)
        total_grams += qty_grams
        if ing.approximate_price_inr_per_kg is not None:
            total_cost += (qty_grams / 1000.0) * float(ing.approximate_price_inr_per_kg)
            priced_grams += qty_grams

    servings = max(recipe.servings, 1)

    calories_per_serving = round(total_calories / servings)
    nutrition_dict: dict[str, Any] = {
        "calories": calories_per_serving,
        "protein_g": round(total_protein / servings, 2),
        "carbs_g": round(total_carbs / servings, 2),
        "fat_g": round(total_fat / servings, 2),
        "fiber_g": round(total_fiber / servings, 2),
        "micronutrients": {k: round(v / servings, 2) for k, v in micro_totals.items()},
        "computed_at": datetime.now(UTC).isoformat(),
    }

    # Cost fields
    cached_cost_inr: Decimal | None = (
        Decimal(str(round(total_cost, 2))) if total_grams > 0 and total_cost > 0 else None
    )
    cost_known = (priced_grams / total_grams >= 0.80) if total_grams > 0 else False

    recipe.cached_nutrition = nutrition_dict
    recipe.cached_calories_per_serving = calories_per_serving
    recipe.cached_cost_inr = cached_cost_inr
    recipe.cost_known = cost_known
    recipe.full_clean()
    recipe.save(
        update_fields=[
            "cached_nutrition",
            "cached_calories_per_serving",
            "cached_cost_inr",
            "cost_known",
            "updated_at",
        ]
    )

    logger.debug(
        "event=compute_recipe_nutrition recipe_slug=%s calories_per_serving=%d",
        recipe.slug,
        calories_per_serving,
    )

    if calories_per_serving < 1:
        logger.warning(
            "event=zero_calorie_recipe recipe_slug=%s",
            recipe.slug,
        )

    return nutrition_dict


def recompute_recipes_using_ingredient(ingredient_id: int) -> int:
    """Find all active recipes using the given ingredient and recompute their nutrition."""
    recipes = list(
        Recipe.objects.filter(
            recipe_ingredients__ingredient_id=ingredient_id,
            is_active=True,
        ).distinct()
    )

    for recipe in recipes:
        compute_recipe_nutrition(recipe)

    logger.info(
        "event=recompute_triggered ingredient_id=%d recipe_count=%d",
        ingredient_id,
        len(recipes),
    )
    return len(recipes)
