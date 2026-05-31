"""
Validate and persist AI-generated recipes into the curated recipe library.

AI-generated recipes are Layer 1 first-class recipes — once validated they are
immediately selectable by the meal plan engine in future plan generations.

Validation pipeline (8 steps):
1. All ingredient_names resolve to an active Ingredient (4-tier lookup; reject whole
   recipe — NOT partial persist — if any ingredient fails all tiers)
2. quantity_grams in (1, 5000)
3. servings in (1, 12)
4. meal_type is a valid enum value
5. Compute nutrition via compute_recipe_nutrition
6. Computed calories/serving in (50, 1500)
7. Persist as Recipe(source='ai_generated', is_active=True)
8. Return saved Recipe
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from django.utils.text import slugify

from apps.recipes.models import (
    MEAL_TYPE_CHOICES,
    RECIPE_SOURCE_AI,
    Ingredient,
    Recipe,
    RecipeIngredient,
)
from apps.recipes.services.nutrition import compute_recipe_nutrition
from core.error_codes import VALIDATION_ERROR
from core.exceptions import AppValidationError

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

_VALID_MEAL_TYPES = frozenset(k for k, _ in MEAL_TYPE_CHOICES)
_MAX_QUANTITY_GRAMS = 5000
_MIN_QUANTITY_GRAMS = 1
_MAX_SERVINGS = 12
_MIN_SERVINGS = 1
_MIN_CALORIES_PER_SERVING = 50
_MAX_CALORIES_PER_SERVING = 1500

_STRIP_PARENS_RE = re.compile(r"\s*\([^)]+\)")

# True-synonym alias map: GPT drift name (lowercase) → exact DB Ingredient.name.
# Only 1:1 unambiguous mappings. Do NOT add "rice" (ambiguous: basmati/sona masoori/parboiled).
# Update values to match actual Ingredient.name values in the DB.
_INGREDIENT_ALIAS_MAP: dict[str, str] = {
    "arhar dal": "Toor dal (raw)",  # arhar = toor, regional synonyms for same pulse
    "pigeon pea": "Toor dal (raw)",  # English name for toor/arhar dal
    "pigeon pea dal": "Toor dal (raw)",
    "dahi": "Curd (raw)",  # Hindi name for curd/yogurt
    "yogurt": "Curd (raw)",  # Western synonym for dahi/curd
}


def _strip_parens(s: str) -> str:
    """Remove parenthetical suffixes like '(raw)' or '(boiled)' from ingredient names."""
    return _STRIP_PARENS_RE.sub("", s).strip()


def _resolve_single_ingredient(
    ai_name: str,
    all_ingredients: list[Ingredient],
    by_exact_lower: dict[str, Ingredient],
    by_stripped_lower: dict[str, Ingredient],
) -> Ingredient | None:
    """Try 4 tiers to resolve an AI-generated name to an active DB Ingredient.

    Returns None if all tiers fail (caller must reject the recipe).
    """
    ai_lower = ai_name.strip().lower()

    # Tier 1: exact case-insensitive name match
    if ai_lower in by_exact_lower:
        return by_exact_lower[ai_lower]

    # Tier 2: strip parentheticals from both sides, then case-insensitive match
    # Catches "basmati rice" → "Basmati rice (raw)"
    ai_stripped = _strip_parens(ai_lower)
    if ai_stripped and ai_stripped in by_stripped_lower:
        return by_stripped_lower[ai_stripped]

    # Tier 3: icontains in both directions (ordered by name for determinism)
    # Direction A: DB name contains AI name as substring
    for ing in all_ingredients:
        if ai_lower in ing.name.lower():
            return ing
    # Direction B: AI name contains DB name as substring (guards against very short names)
    for ing in all_ingredients:
        if len(ing.name) >= 4 and ing.name.lower() in ai_lower:
            return ing

    # Tier 4: alias map for true synonyms (regional names, alternate spellings)
    alias_target = _INGREDIENT_ALIAS_MAP.get(ai_lower)
    if alias_target:
        target_lower = alias_target.lower()
        if target_lower in by_exact_lower:
            return by_exact_lower[target_lower]

    return None


def validate_and_persist_ai_recipe(recipe_json: dict[str, Any], user: User) -> Recipe:
    """Validate an AI-generated recipe dict and persist it to the DB.

    Raises AppValidationError on any validation failure (including unresolvable
    ingredients — the whole recipe is rejected, never a partial persist).
    Returns the saved Recipe instance on success.
    """
    name: str = recipe_json.get("name", "").strip()
    meal_type: str = recipe_json.get("meal_type", "").strip()
    servings: Any = recipe_json.get("servings", 1)
    diet_tags: list[str] = recipe_json.get("diet_tags", [])
    allergen_tags: list[str] = recipe_json.get("allergen_tags", [])
    steps: list[str] = recipe_json.get("steps", [])
    ingredients_data: list[dict[str, Any]] = recipe_json.get("ingredients", [])

    # Step 4 — meal_type
    if meal_type not in _VALID_MEAL_TYPES:
        valid = ", ".join(_VALID_MEAL_TYPES)
        raise AppValidationError(
            code=VALIDATION_ERROR,
            message=f"Invalid meal_type '{meal_type}'. Must be one of: {valid}",
        )

    # Step 3 — servings
    try:
        servings = int(servings)
    except (TypeError, ValueError):
        servings = 0
    if not (_MIN_SERVINGS <= servings <= _MAX_SERVINGS):
        raise AppValidationError(
            code=VALIDATION_ERROR,
            message=f"servings must be between {_MIN_SERVINGS} and {_MAX_SERVINGS}.",
        )

    if not name:
        raise AppValidationError(code=VALIDATION_ERROR, message="Recipe name is required.")

    if not ingredients_data:
        raise AppValidationError(
            code=VALIDATION_ERROR,
            message="Recipe must have at least one ingredient.",
        )

    # Step 1 & 2 — resolve all ingredients (4-tier lookup), validate quantities.
    # Load all active ingredients once; do all resolution in Python to avoid N+1 queries.
    all_ingredients = list(Ingredient.objects.filter(is_active=True).order_by("name"))
    by_exact_lower: dict[str, Ingredient] = {ing.name.lower(): ing for ing in all_ingredients}
    by_stripped_lower: dict[str, Ingredient] = {
        _strip_parens(ing.name).lower(): ing for ing in all_ingredients
    }

    resolved: list[tuple[Ingredient, float]] = []
    for item in ingredients_data:
        ing_name: str = item.get("ingredient_name", "")
        qty = item.get("quantity_grams")

        match = _resolve_single_ingredient(
            ing_name, all_ingredients, by_exact_lower, by_stripped_lower
        )

        if match is None:
            logger.warning(
                "ai_ingredient_unresolvable",
                extra={
                    "event": "ai_ingredient_unresolvable",
                    "ingredient_name": ing_name,
                    "recipe_name": name,
                },
            )
            raise AppValidationError(
                code=VALIDATION_ERROR,
                message=f"Ingredient '{ing_name}' does not exist in the ingredient database.",
            )

        if match.name != ing_name:
            logger.debug(
                "ai_ingredient_resolved",
                extra={
                    "event": "ai_ingredient_resolved",
                    "ai_name": ing_name,
                    "matched_name": match.name,
                },
            )

        try:
            qty_f = float(qty)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise AppValidationError(
                code=VALIDATION_ERROR,
                message=f"Invalid quantity_grams for '{ing_name}'.",
            ) from exc

        if not (_MIN_QUANTITY_GRAMS < qty_f <= _MAX_QUANTITY_GRAMS):
            raise AppValidationError(
                code=VALIDATION_ERROR,
                message=(
                    f"quantity_grams for '{ing_name}' must be between "
                    f"{_MIN_QUANTITY_GRAMS} and {_MAX_QUANTITY_GRAMS}."
                ),
            )

        resolved.append((match, qty_f))

    # Guard: two AI-generated names that resolved to the same DB Ingredient would
    # violate RecipeIngredient.unique_together and leave an orphan Recipe row.
    seen_pks: set[int] = set()
    for match, _ in resolved:
        if match.pk in seen_pks:
            raise AppValidationError(
                code=VALIDATION_ERROR,
                message=(
                    f"Ingredient '{match.name}' appears more than once in the recipe "
                    f"after resolution. Use a single entry with the combined quantity."
                ),
            )
        seen_pks.add(match.pk)

    # Step 7 — create Recipe + RecipeIngredients
    slug = _unique_slug(name)
    recipe = Recipe(
        name=name,
        slug=slug,
        meal_type=meal_type,
        cuisine="north_indian",  # default; AI can't reliably infer this
        diet_tags=diet_tags,
        allergen_tags=allergen_tags,
        servings=servings,
        instructions=steps,
        source=RECIPE_SOURCE_AI,
        is_active=True,
    )
    recipe.full_clean()
    recipe.save()

    for ingredient, qty_grams in resolved:
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            quantity_grams=qty_grams,
        )

    # Step 5 — compute nutrition
    # compute_recipe_nutrition saves calories_per_serving on the model AND returns a dict
    # with key "calories" (not "calories_per_serving") — read from the returned dict.
    nutrition = compute_recipe_nutrition(recipe)
    calories_per_serving = nutrition.get("calories", 0)

    # Step 6 — calorie range guard
    if not (_MIN_CALORIES_PER_SERVING < calories_per_serving < _MAX_CALORIES_PER_SERVING):
        recipe.delete()
        raise AppValidationError(
            code=VALIDATION_ERROR,
            message=(
                f"Computed calories/serving ({calories_per_serving:.0f}) is outside "
                f"the valid range ({_MIN_CALORIES_PER_SERVING}–{_MAX_CALORIES_PER_SERVING})."
            ),
        )

    logger.info(
        "ai_recipe_persisted",
        extra={
            "event": "ai_recipe_persisted",
            "recipe_id": recipe.pk,
            "recipe_slug": recipe.slug,
            "calories_per_serving": calories_per_serving,
        },
    )
    return recipe


def _unique_slug(name: str) -> str:
    """Generate a unique slug for the recipe, appending a counter if needed."""
    base = slugify(name)[:200] or "ai-recipe"
    slug = f"ai-{base}"
    counter = 1
    while Recipe.objects.filter(slug=slug).exists():
        suffix = re.sub(r"-\d+$", "", slug)
        slug = f"{suffix}-{counter}"
        counter += 1
    return slug
