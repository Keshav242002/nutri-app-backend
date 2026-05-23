import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any

from apps.recipes.models import HouseholdUnit, Ingredient, Recipe, RecipeIngredient
from core.exceptions import AppValidationError

logger = logging.getLogger(__name__)


def seed_ingredients(path: Path) -> tuple[int, int]:
    """Upsert ingredients from a JSON seed file into the Ingredient model (idempotent)."""
    if not path.exists():
        raise FileNotFoundError(f"Ingredient seed file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppValidationError(f"Invalid JSON in ingredient seed file: {exc}") from exc

    if not isinstance(data, list):
        raise AppValidationError("Ingredient seed file must be a JSON array.")

    logger.info("event=seed_ingredients_started path=%s count=%d", path, len(data))

    created_count = 0
    updated_count = 0
    calorie_fallback_ids: list[str] = []
    zero_nutrition_ids: list[str] = []

    for entry in data:
        if not isinstance(entry, dict):
            raise AppValidationError(
                f"Each ingredient entry must be a JSON object, got: {type(entry)}"
            )

        app_id = entry.get("app_id")
        if not app_id:
            raise AppValidationError(f"Ingredient entry missing required field 'app_id': {entry}")

        nutrition = entry.get("per_100g_nutrition")
        if not isinstance(nutrition, dict):
            raise AppValidationError(f"Ingredient '{app_id}' missing valid 'per_100g_nutrition'.")

        # Calorie fallback for IFCT oils: enerc=0 kJ but macros are present.
        nutrition = dict(nutrition)  # copy so we don't mutate the original
        calories = nutrition.get("calories", 0) or 0
        protein = nutrition.get("protein_g", 0) or 0
        carbs = nutrition.get("carbs_g", 0) or 0
        fat = nutrition.get("fat_g", 0) or 0

        if calories == 0 and (protein + carbs + fat) > 0:
            computed = round(protein * 4 + carbs * 4 + fat * 9)
            nutrition["calories"] = computed
            calorie_fallback_ids.append(app_id)

        elif calories == 0 and (protein + carbs + fat) == 0:
            zero_nutrition_ids.append(app_id)

        provenance = entry.get("provenance") or {}

        defaults: dict[str, Any] = {
            "name": entry.get("name", ""),
            "name_hi": entry.get("name_hi", ""),
            "category": entry.get("category", ""),
            "form": entry.get("form", "raw"),
            "cooked_yield_ratio": entry.get("cooked_yield_ratio", "1.00"),
            "per_100g_nutrition": nutrition,
            "approximate_price_inr_per_kg": entry.get("approximate_price_inr_per_kg"),
            "price_as_of_month": entry.get("price_as_of_month", ""),
            "allergen_tags": entry.get("allergen_tags") or [],
            "source": provenance.get("source", "manual"),
            "ifct_code": provenance.get("ifct_code") or "",
            "ifct_name": provenance.get("ifct_name") or "",
            "ifct_regn": provenance.get("ifct_regn"),
            "usda_fdc_id": provenance.get("usda_fdc_id"),
            "usda_description": provenance.get("usda_description") or "",
            "confidence": provenance.get("confidence") or "",
            "extracted_at": provenance.get("extracted_at"),
            "package_version": provenance.get("package_version") or "",
            "overlays": entry.get("overlays"),
        }

        try:
            obj = Ingredient.objects.get(app_id=app_id)
            created = False
            for field, val in defaults.items():
                setattr(obj, field, val)
        except Ingredient.DoesNotExist:
            obj = Ingredient(app_id=app_id, **defaults)
            created = True
        obj.full_clean()
        obj.save()

        if created:
            created_count += 1
        else:
            updated_count += 1

    if calorie_fallback_ids:
        logger.warning(
            "event=calorie_fallback_computed app_ids=%s",
            calorie_fallback_ids,
        )

    if zero_nutrition_ids:
        logger.warning(
            "event=zero_nutrition_ingredient app_ids=%s",
            zero_nutrition_ids,
        )

    logger.info(
        "event=seed_ingredients_completed created=%d updated=%d",
        created_count,
        updated_count,
    )
    return created_count, updated_count


def seed_household_units(path: Path) -> tuple[int, int]:
    """Upsert household units from a JSON seed file into the HouseholdUnit model (idempotent)."""
    if not path.exists():
        raise FileNotFoundError(f"Household units seed file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppValidationError(f"Invalid JSON in household units seed file: {exc}") from exc

    if not isinstance(data, list):
        raise AppValidationError("Household units seed file must be a JSON array.")

    logger.info("event=seed_household_units_started path=%s count=%d", path, len(data))

    created_count = 0
    updated_count = 0

    for entry in data:
        if not isinstance(entry, dict):
            raise AppValidationError(
                f"Each household unit entry must be a JSON object, got: {type(entry)}"
            )

        unit_name = entry.get("unit_name")
        if not unit_name:
            raise AppValidationError(
                f"Household unit entry missing required field 'unit_name': {entry}"
            )

        ingredient_app_id = entry.get("ingredient_app_id")
        ingredient: Ingredient | None = None
        if ingredient_app_id:
            try:
                ingredient = Ingredient.objects.get(app_id=ingredient_app_id)
            except Ingredient.DoesNotExist as exc:
                raise AppValidationError(
                    f"Household unit '{unit_name}' references unknown"
                    f" ingredient '{ingredient_app_id}'."
                ) from exc

        grams = entry.get("grams")
        if grams is None:
            raise AppValidationError(
                f"Household unit entry '{unit_name}' missing required field 'grams'."
            )
        # Decimal(str(...)) avoids float→Decimal precision noise in DecimalField.to_python
        grams = Decimal(str(round(float(grams), 2)))

        try:
            obj = HouseholdUnit.objects.get(name=unit_name, ingredient=ingredient)
            created = False
            obj.grams = grams
        except HouseholdUnit.DoesNotExist:
            obj = HouseholdUnit(name=unit_name, ingredient=ingredient, grams=grams)
            created = True
        obj.full_clean()
        obj.save()

        if created:
            created_count += 1
        else:
            updated_count += 1

    logger.info(
        "event=seed_household_units_completed created=%d updated=%d",
        created_count,
        updated_count,
    )
    return created_count, updated_count


def seed_recipes(path: Path) -> tuple[int, int]:
    """Upsert recipes from a JSON seed file, create RecipeIngredients, compute nutrition."""
    # deferred import avoids any potential import-order issues at module load time
    from apps.recipes.services.nutrition import compute_recipe_nutrition

    if not path.exists():
        raise FileNotFoundError(f"Recipe seed file not found: {path}")

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppValidationError(f"Invalid JSON in recipe seed file: {exc}") from exc

    if not isinstance(data, list):
        raise AppValidationError("Recipe seed file must be a JSON array.")

    logger.info("event=seed_recipes_started path=%s count=%d", path, len(data))

    # ------------------------------------------------------------------
    # Pre-validation: collect ALL missing ingredient refs before writing
    # ------------------------------------------------------------------
    all_known_app_ids = set(Ingredient.objects.values_list("app_id", flat=True))
    missing_refs: list[str] = []
    for recipe_entry in data:
        for ing_entry in recipe_entry.get("ingredients", []):
            ref = ing_entry.get("ingredient_app_id", "")
            if ref and ref not in all_known_app_ids:
                missing_refs.append(ref)

    if missing_refs:
        raise AppValidationError(
            f"Recipe seed references {len(missing_refs)} unknown ingredient app_id(s): "
            f"{sorted(set(missing_refs))}"
        )

    # Build ingredient lookup cache (app_id → Ingredient instance)
    ingredient_cache: dict[str, Ingredient] = {
        ing.app_id: ing for ing in Ingredient.objects.filter(app_id__in=all_known_app_ids)
    }

    created_count = 0
    updated_count = 0

    for recipe_entry in data:
        slug = recipe_entry.get("slug", "")
        if not slug:
            raise AppValidationError(f"Recipe entry missing required field 'slug': {recipe_entry}")

        recipe_defaults: dict[str, Any] = {
            "name": recipe_entry.get("name", ""),
            "name_alt": recipe_entry.get("name_alt", ""),
            "meal_type": recipe_entry.get("meal_type", ""),
            "cuisine": recipe_entry.get("cuisine", ""),
            "diet_tags": recipe_entry.get("diet_tags") or [],
            "allergen_tags": recipe_entry.get("allergen_tags") or [],
            "prep_time_min": recipe_entry.get("prep_time_min", 0),
            "cook_time_min": recipe_entry.get("cook_time_min", 0),
            "servings": recipe_entry.get("servings", 2),
            "estimated_difficulty": recipe_entry.get("estimated_difficulty", "intermediate"),
            "spice_level": recipe_entry.get("spice_level", "medium"),
            "instructions": recipe_entry.get("instructions") or [],
            "image_url": recipe_entry.get("image_url", ""),
            "source": recipe_entry.get("source", "seed"),
        }

        try:
            recipe = Recipe.objects.get(slug=slug)
            created = False
            for field, val in recipe_defaults.items():
                setattr(recipe, field, val)
        except Recipe.DoesNotExist:
            recipe = Recipe(slug=slug, **recipe_defaults)
            created = True
        recipe.full_clean()
        recipe.save()

        # Delete existing RecipeIngredient rows for idempotent re-seed
        RecipeIngredient.objects.filter(recipe=recipe).delete()

        for order, ing_entry in enumerate(recipe_entry.get("ingredients", [])):
            app_id: str = ing_entry["ingredient_app_id"]
            ingredient = ingredient_cache[app_id]
            quantity_grams = Decimal(str(round(float(ing_entry.get("quantity_grams", 0)), 2)))
            raw_dq = ing_entry.get("display_quantity")
            display_quantity = Decimal(str(round(float(raw_dq), 2))) if raw_dq is not None else None
            display_unit_name: str | None = ing_entry.get("display_unit")
            notes: str = ing_entry.get("notes", "")

            # Resolve display_unit: ingredient-specific first, then generic
            display_unit: HouseholdUnit | None = None
            if display_unit_name:
                display_unit = (
                    HouseholdUnit.objects.filter(
                        name=display_unit_name, ingredient=ingredient
                    ).first()
                    or HouseholdUnit.objects.filter(
                        name=display_unit_name, ingredient__isnull=True
                    ).first()
                )
                # Soft warning for quantity mismatch > 5%
                if (
                    display_unit is not None
                    and display_quantity is not None
                    and float(display_unit.grams) > 0
                ):
                    computed_grams = float(display_quantity) * float(display_unit.grams)
                    qty_f = float(quantity_grams)
                    if qty_f > 0:
                        deviation = abs(computed_grams - qty_f) / qty_f
                        if deviation > 0.05:
                            logger.warning(
                                "event=display_unit_mismatch recipe_slug=%s ingredient=%s "
                                "quantity_grams=%s display_computed=%s deviation=%.2f%%",
                                slug,
                                app_id,
                                quantity_grams,
                                computed_grams,
                                deviation * 100,
                            )

            ri = RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient,
                order=order,
                quantity_grams=quantity_grams,
                display_quantity=display_quantity,
                display_unit=display_unit,
                notes=notes,
            )
            ri.full_clean()
            ri.save()

        # Warn if any ingredient in this recipe carries zero nutrition (spec M3_plan.md §233)
        zero_nutrition_ids: list[str] = []
        for ing_entry in recipe_entry.get("ingredients", []):
            ing_app_id: str = ing_entry["ingredient_app_id"]
            ing = ingredient_cache[ing_app_id]
            n = ing.per_100g_nutrition or {}
            if (n.get("calories") or 0) == 0 and (
                (n.get("protein_g") or 0) + (n.get("carbs_g") or 0) + (n.get("fat_g") or 0) == 0
            ):
                zero_nutrition_ids.append(ing_app_id)

        if zero_nutrition_ids:
            logger.warning(
                "event=recipe_uses_zero_nutrition_ingredient recipe_slug=%s ingredient_app_ids=%s",
                slug,
                zero_nutrition_ids,
                extra={
                    "event": "recipe_uses_zero_nutrition_ingredient",
                    "recipe_slug": slug,
                    "ingredient_app_ids": zero_nutrition_ids,
                },
            )

        # Compute and cache nutrition immediately after all ingredients are loaded
        nutrition = compute_recipe_nutrition(recipe)
        calories_per_serving = nutrition.get("calories", 0)
        if not (50 <= calories_per_serving <= 1200):
            logger.warning(
                "event=recipe_calorie_out_of_range recipe_slug=%s calories_per_serving=%s",
                slug,
                calories_per_serving,
            )

        if created:
            created_count += 1
        else:
            updated_count += 1

    logger.info(
        "event=seed_recipes_completed created=%d updated=%d",
        created_count,
        updated_count,
    )
    return created_count, updated_count
