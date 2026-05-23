import json
import logging
from pathlib import Path

import pytest

from apps.recipes.models import HouseholdUnit, Ingredient, Recipe, RecipeIngredient
from apps.recipes.services.seed import seed_household_units, seed_ingredients, seed_recipes

pytestmark = pytest.mark.django_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_INGREDIENT = {
    "app_id": "test_rice_raw",
    "name": "Test Rice",
    "category": "grain",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 350,
        "protein_g": 7.0,
        "carbs_g": 76.0,
        "fat_g": 1.0,
        "fiber_g": 2.8,
        "micronutrients": {
            "iron_mg": 0.7,
            "calcium_mg": 10.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 115.0,
            "sodium_mg": 5.0,
            "magnesium_mg": 25.0,
            "zinc_mg": 1.1,
            "vit_a_iu": 0.0,
            "folate_ug": 8.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": [],
    "provenance": {
        "source": "ifct",
        "ifct_code": "A001",
        "confidence": "exact",
        "extracted_at": "2026-05-23",
        "package_version": "@ifct2017/compositions@2.0.11",
    },
}

_ZERO_CALORIE_OIL = {
    "app_id": "test_ghee_raw",
    "name": "Test Ghee",
    "category": "oil_fat",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 100.0,
        "fiber_g": 0.0,
        "micronutrients": {
            "iron_mg": 0.0,
            "calcium_mg": 0.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 0.0,
            "sodium_mg": 0.0,
            "magnesium_mg": 0.0,
            "zinc_mg": 0.0,
            "vit_a_iu": 0.0,
            "folate_ug": 0.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": ["dairy"],
    "provenance": {
        "source": "ifct",
        "ifct_code": "J001",
        "confidence": "exact",
        "extracted_at": "2026-05-23",
        "package_version": "@ifct2017/compositions@2.0.11",
    },
}

_ZERO_ALL_NUTRITION = {
    "app_id": "test_spice_trace_raw",
    "name": "Test Trace Spice",
    "category": "spice",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "micronutrients": {
            "iron_mg": 0.0,
            "calcium_mg": 0.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 0.0,
            "sodium_mg": 0.0,
            "magnesium_mg": 0.0,
            "zinc_mg": 0.0,
            "vit_a_iu": 0.0,
            "folate_ug": 0.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": [],
    "provenance": {
        "source": "usda",
        "confidence": "weak",
        "extracted_at": "2026-05-23",
        "package_version": "",
    },
}

_MUSTARD_ALLERGEN = {
    "app_id": "test_mustard_seeds_raw",
    "name": "Test Mustard Seeds",
    "category": "spice",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 508,
        "protein_g": 26.08,
        "carbs_g": 28.09,
        "fat_g": 36.24,
        "fiber_g": 12.2,
        "micronutrients": {
            "iron_mg": 9.21,
            "calcium_mg": 266.0,
            "vit_c_mg": 7.1,
            "potassium_mg": 738.0,
            "sodium_mg": 13.33,
            "magnesium_mg": 370.0,
            "zinc_mg": 6.08,
            "vit_a_iu": 31.18,
            "folate_ug": 162.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": ["mustard"],
    "provenance": {
        "source": "ifct",
        "ifct_code": "G018",
        "confidence": "exact",
        "extracted_at": "2026-05-23",
        "package_version": "@ifct2017/compositions@2.0.11",
    },
}


def _write_seed(tmp_path: Path, entries: list) -> Path:
    p = tmp_path / "ingredients.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_seed_ingredients_creates_all_entries(tmp_path: Path) -> None:
    seed_path = _write_seed(tmp_path, [_MINIMAL_INGREDIENT, _ZERO_CALORIE_OIL])
    created, updated = seed_ingredients(seed_path)
    assert created == 2
    assert updated == 0
    assert Ingredient.objects.count() == 2


def test_seed_ingredients_idempotent(tmp_path: Path) -> None:
    seed_path = _write_seed(tmp_path, [_MINIMAL_INGREDIENT])
    seed_ingredients(seed_path)
    created2, updated2 = seed_ingredients(seed_path)
    assert created2 == 0
    assert updated2 == 1
    assert Ingredient.objects.count() == 1


def test_seed_ingredients_updates_existing_on_rerun(tmp_path: Path) -> None:
    seed_path = _write_seed(tmp_path, [_MINIMAL_INGREDIENT])
    seed_ingredients(seed_path)

    modified = {**_MINIMAL_INGREDIENT, "name": "Test Rice Updated"}
    seed_path2 = _write_seed(tmp_path, [modified])
    seed_ingredients(seed_path2)

    ing = Ingredient.objects.get(app_id="test_rice_raw")
    assert ing.name == "Test Rice Updated"


def test_seed_ingredients_calorie_fallback_for_zero_enerc(tmp_path: Path) -> None:
    seed_path = _write_seed(tmp_path, [_ZERO_CALORIE_OIL])
    seed_ingredients(seed_path)
    ing = Ingredient.objects.get(app_id="test_ghee_raw")
    # fat=100, protein=0, carbs=0 → 100×9 = 900
    assert ing.per_100g_nutrition["calories"] == 900


def test_calorie_fallback_ghee_gets_900_kcal(tmp_path: Path) -> None:
    """Regression guard: pure fat (ghee) must always land at exactly 900 kcal."""
    seed_path = _write_seed(tmp_path, [_ZERO_CALORIE_OIL])
    seed_ingredients(seed_path)
    ghee = Ingredient.objects.get(app_id="test_ghee_raw")
    assert ghee.per_100g_nutrition["calories"] == 900


def test_seed_ingredients_logs_zero_nutrition_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    seed_path = _write_seed(tmp_path, [_ZERO_ALL_NUTRITION])
    # apps logger has propagate=False; inject caplog handler directly.
    seed_logger = logging.getLogger("apps.recipes.services.seed")
    seed_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="apps.recipes.services.seed"):
            seed_ingredients(seed_path)
    finally:
        seed_logger.removeHandler(caplog.handler)
    assert any("zero_nutrition_ingredient" in r.getMessage() for r in caplog.records)


def test_seed_ingredients_calorie_fallback_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    seed_path = _write_seed(tmp_path, [_ZERO_CALORIE_OIL])
    # apps logger has propagate=False; inject caplog handler directly.
    seed_logger = logging.getLogger("apps.recipes.services.seed")
    seed_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="apps.recipes.services.seed"):
            seed_ingredients(seed_path)
    finally:
        seed_logger.removeHandler(caplog.handler)
    assert any("calorie_fallback_computed" in r.getMessage() for r in caplog.records)


def test_seed_ingredients_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        seed_ingredients(tmp_path / "nonexistent.json")


def test_seed_ingredients_invalid_json(tmp_path: Path) -> None:
    from core.exceptions import AppValidationError

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not valid json {{", encoding="utf-8")
    with pytest.raises(AppValidationError):
        seed_ingredients(bad_path)


def test_mustard_allergen_accepted_in_seed(tmp_path: Path) -> None:
    """Regression guard: mustard allergen tag must survive full_clean() validation."""
    seed_path = _write_seed(tmp_path, [_MUSTARD_ALLERGEN])
    seed_ingredients(seed_path)
    ing = Ingredient.objects.get(app_id="test_mustard_seeds_raw")
    assert "mustard" in ing.allergen_tags


def test_seed_ingredients_loads_real_seed_file() -> None:
    """Integration: load the production ingredients.json and verify all 136 entries seed cleanly."""
    real_path = Path(__file__).resolve().parent.parent / "seed_data" / "ingredients.json"
    assert real_path.exists(), f"Production seed file missing: {real_path}"
    created, updated = seed_ingredients(real_path)
    assert created + updated == 136
    assert Ingredient.objects.count() == 136


# ---------------------------------------------------------------------------
# seed_household_units
# ---------------------------------------------------------------------------

_INGREDIENT_FOR_UNIT = {
    "app_id": "dal_for_unit_raw",
    "name": "Dal For Unit",
    "category": "pulse",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 340,
        "protein_g": 24.0,
        "carbs_g": 60.0,
        "fat_g": 1.0,
        "fiber_g": 8.0,
        "micronutrients": {
            "iron_mg": 3.0,
            "calcium_mg": 50.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 900.0,
            "sodium_mg": 5.0,
            "magnesium_mg": 80.0,
            "zinc_mg": 2.0,
            "vit_a_iu": 0.0,
            "folate_ug": 110.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": [],
    "provenance": {"source": "ifct", "confidence": "exact", "extracted_at": "2026-05-23"},
}


def _write_units(tmp_path: Path, entries: list) -> Path:
    p = tmp_path / "household_units.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


def test_seed_household_units_creates_all_entries(tmp_path: Path) -> None:
    ing_path = _write_seed(tmp_path, [_INGREDIENT_FOR_UNIT])
    seed_ingredients(ing_path)

    units_path = _write_units(
        tmp_path,
        [
            {"unit_name": "katori", "ingredient_app_id": "dal_for_unit_raw", "grams": 150.0},
            {"unit_name": "tbsp", "ingredient_app_id": "dal_for_unit_raw", "grams": 15.0},
        ],
    )
    created, updated = seed_household_units(units_path)
    assert created == 2
    assert updated == 0
    assert HouseholdUnit.objects.count() == 2


def test_seed_household_units_idempotent(tmp_path: Path) -> None:
    ing_path = _write_seed(tmp_path, [_INGREDIENT_FOR_UNIT])
    seed_ingredients(ing_path)

    entry = {"unit_name": "katori", "ingredient_app_id": "dal_for_unit_raw", "grams": 150.0}
    units_path = _write_units(tmp_path, [entry])
    seed_household_units(units_path)
    created2, updated2 = seed_household_units(units_path)
    assert created2 == 0
    assert updated2 == 1
    assert HouseholdUnit.objects.count() == 1


def test_seed_household_units_fails_on_missing_ingredient(tmp_path: Path) -> None:
    from core.exceptions import AppValidationError

    units_path = _write_units(
        tmp_path,
        [{"unit_name": "katori", "ingredient_app_id": "nonexistent_raw", "grams": 150.0}],
    )
    with pytest.raises(AppValidationError, match="nonexistent_raw"):
        seed_household_units(units_path)


def test_seed_household_units_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        seed_household_units(tmp_path / "nonexistent_units.json")


# ---------------------------------------------------------------------------
# seed_recipes — helpers
# ---------------------------------------------------------------------------

_INGREDIENT_RICE = {
    "app_id": "sr_rice_raw",
    "name": "SR Basmati Rice",
    "category": "grain",
    "form": "raw",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 350,
        "protein_g": 7.0,
        "carbs_g": 76.0,
        "fat_g": 1.0,
        "fiber_g": 2.8,
        "micronutrients": {
            "iron_mg": 0.7,
            "calcium_mg": 10.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 115.0,
            "sodium_mg": 5.0,
            "magnesium_mg": 25.0,
            "zinc_mg": 1.1,
            "vit_a_iu": 0.0,
            "folate_ug": 8.0,
            "vit_b12_ug": None,
        },
    },
    "approximate_price_inr_per_kg": 80.0,
    "price_as_of_month": "2026-05",
    "allergen_tags": [],
    "provenance": {"source": "ifct", "confidence": "exact", "extracted_at": "2026-05-23"},
}

_INGREDIENT_DAL = {
    "app_id": "sr_dal_raw",
    "name": "SR Masoor Dal",
    "category": "pulse",
    "form": "raw",
    "cooked_yield_ratio": 1.5,
    "per_100g_nutrition": {
        "calories": 340,
        "protein_g": 24.0,
        "carbs_g": 60.0,
        "fat_g": 1.0,
        "fiber_g": 8.0,
        "micronutrients": {
            "iron_mg": 3.0,
            "calcium_mg": 50.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 900.0,
            "sodium_mg": 5.0,
            "magnesium_mg": 80.0,
            "zinc_mg": 2.0,
            "vit_a_iu": 0.0,
            "folate_ug": 110.0,
            "vit_b12_ug": None,
        },
    },
    "approximate_price_inr_per_kg": 100.0,
    "price_as_of_month": "2026-05",
    "allergen_tags": [],
    "provenance": {"source": "ifct", "confidence": "exact", "extracted_at": "2026-05-23"},
}

_INGREDIENT_SALT = {
    "app_id": "sr_salt_raw",
    "name": "SR Salt",
    "category": "spice",
    "form": "as_eaten",
    "cooked_yield_ratio": 1.0,
    "per_100g_nutrition": {
        "calories": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "micronutrients": {
            "iron_mg": 0.0,
            "calcium_mg": 0.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 0.0,
            "sodium_mg": 38758.0,
            "magnesium_mg": 0.0,
            "zinc_mg": 0.0,
            "vit_a_iu": 0.0,
            "folate_ug": 0.0,
            "vit_b12_ug": None,
        },
    },
    "allergen_tags": [],
    "provenance": {"source": "usda", "confidence": "weak", "extracted_at": "2026-05-23"},
}

_MINIMAL_RECIPE = {
    "name": "SR Test Dal Rice",
    "name_alt": "Dal Chawal",
    "slug": "sr-test-dal-rice",
    "meal_type": "lunch",
    "cuisine": "north_indian",
    "diet_tags": ["vegetarian", "vegan"],
    "allergen_tags": [],
    "prep_time_min": 5,
    "cook_time_min": 20,
    "servings": 2,
    "estimated_difficulty": "beginner",
    "spice_level": "mild",
    "ingredients": [
        {
            "ingredient_app_id": "sr_rice_raw",
            "quantity_grams": 100.0,
            "display_quantity": 1.0,
            "display_unit": "katori",
            "notes": "washed",
        },
        {
            "ingredient_app_id": "sr_dal_raw",
            "quantity_grams": 50.0,
            "display_quantity": 0.5,
            "display_unit": "katori",
            "notes": "soaked",
        },
    ],
    "instructions": ["Pressure cook rice and dal together.", "Season and serve."],
    "source": "seed",
}


def _seed_test_ingredients(tmp_path: Path) -> None:
    ing_path = _write_seed(tmp_path, [_INGREDIENT_RICE, _INGREDIENT_DAL, _INGREDIENT_SALT])
    seed_ingredients(ing_path)


def _seed_test_units(tmp_path: Path) -> None:
    units_path = _write_units(
        tmp_path,
        [
            {"unit_name": "katori", "ingredient_app_id": "sr_rice_raw", "grams": 100.0},
            {"unit_name": "katori", "ingredient_app_id": "sr_dal_raw", "grams": 75.0},
        ],
    )
    seed_household_units(units_path)


def _write_recipes(tmp_path: Path, entries: list) -> Path:
    p = tmp_path / "recipes.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# seed_recipes — tests
# ---------------------------------------------------------------------------


def test_seed_recipes_creates_all_entries(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    created, updated = seed_recipes(recipes_path)
    assert created == 1
    assert updated == 0
    assert Recipe.objects.count() == 1


def test_seed_recipes_idempotent(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)
    created2, updated2 = seed_recipes(recipes_path)
    assert created2 == 0
    assert updated2 == 1
    assert Recipe.objects.count() == 1
    # RecipeIngredient rows should be 2 (re-created on each run)
    assert RecipeIngredient.objects.count() == 2


def test_seed_recipes_validates_ingredient_references(tmp_path: Path) -> None:
    from core.exceptions import AppValidationError

    # Do NOT seed ingredients — all refs should be unknown
    bad_recipe = {**_MINIMAL_RECIPE, "slug": "sr-bad-recipe"}
    recipes_path = _write_recipes(tmp_path, [bad_recipe])
    with pytest.raises(AppValidationError, match="sr_rice_raw"):
        seed_recipes(recipes_path)


def test_seed_recipes_collects_all_missing_refs(tmp_path: Path) -> None:
    """Allowlist validation must report ALL unknown refs, not just the first."""
    from core.exceptions import AppValidationError

    bad_recipe = {
        **_MINIMAL_RECIPE,
        "slug": "sr-multi-bad",
        "ingredients": [
            {"ingredient_app_id": "unknown_one_raw", "quantity_grams": 100.0},
            {"ingredient_app_id": "unknown_two_raw", "quantity_grams": 50.0},
        ],
    }
    recipes_path = _write_recipes(tmp_path, [bad_recipe])
    with pytest.raises(AppValidationError) as exc_info:
        seed_recipes(recipes_path)
    msg = str(exc_info.value)
    assert "unknown_one_raw" in msg
    assert "unknown_two_raw" in msg


def test_seed_recipes_creates_recipe_ingredients_with_correct_order(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)

    ris = list(RecipeIngredient.objects.order_by("order"))
    assert len(ris) == 2
    assert ris[0].ingredient.app_id == "sr_rice_raw"
    assert ris[0].order == 0
    assert ris[1].ingredient.app_id == "sr_dal_raw"
    assert ris[1].order == 1


def test_seed_recipes_resolves_display_unit_to_household_unit(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)

    rice_ri = RecipeIngredient.objects.get(ingredient__app_id="sr_rice_raw")
    assert rice_ri.display_unit is not None
    assert rice_ri.display_unit.name == "katori"
    assert float(rice_ri.display_unit.grams) == 100.0


def test_seed_recipes_display_unit_fallback_to_generic(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    # Seed a generic "tbsp" (ingredient=None) but no ingredient-specific one
    generic_units_path = tmp_path / "generic_units.json"
    generic_units_path.write_text(
        json.dumps([{"unit_name": "tbsp", "ingredient_app_id": None, "grams": 15.0}]),
        encoding="utf-8",
    )
    seed_household_units(generic_units_path)

    recipe_with_tbsp = {
        **_MINIMAL_RECIPE,
        "slug": "sr-generic-unit-recipe",
        "ingredients": [
            {
                "ingredient_app_id": "sr_rice_raw",
                "quantity_grams": 15.0,
                "display_quantity": 1.0,
                "display_unit": "tbsp",
                "notes": "",
            }
        ],
    }
    recipes_path = _write_recipes(tmp_path, [recipe_with_tbsp])
    seed_recipes(recipes_path)

    ri = RecipeIngredient.objects.get(ingredient__app_id="sr_rice_raw")
    assert ri.display_unit is not None
    assert ri.display_unit.ingredient is None  # generic unit


def test_seed_recipes_logs_quantity_grams_mismatch_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _seed_test_ingredients(tmp_path)
    # katori for rice = 100g, but recipe says quantity_grams=200 with display_quantity=1 katori
    # deviation = |100 - 200| / 200 = 50% > 5% → should warn
    _seed_test_units(tmp_path)
    mismatched_recipe = {
        **_MINIMAL_RECIPE,
        "slug": "sr-mismatch-recipe",
        "ingredients": [
            {
                "ingredient_app_id": "sr_rice_raw",
                "quantity_grams": 200.0,
                "display_quantity": 1.0,
                "display_unit": "katori",
                "notes": "",
            }
        ],
    }
    recipes_path = _write_recipes(tmp_path, [mismatched_recipe])
    seed_logger = logging.getLogger("apps.recipes.services.seed")
    seed_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="apps.recipes.services.seed"):
            seed_recipes(recipes_path)
    finally:
        seed_logger.removeHandler(caplog.handler)
    assert any("display_unit_mismatch" in r.getMessage() for r in caplog.records)


def test_seed_recipes_logs_zero_nutrition_ingredient_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Recipes that use zero-nutrition trace ingredients must log a named warning."""
    _seed_test_ingredients(tmp_path)  # includes sr_salt_raw: calories=0, all macros=0
    recipe_with_salt = {
        **_MINIMAL_RECIPE,
        "slug": "sr-zero-nutrition-recipe",
        "ingredients": [
            {
                "ingredient_app_id": "sr_salt_raw",
                "quantity_grams": 5.0,
                "display_quantity": None,
                "display_unit": None,
                "notes": "",
            }
        ],
    }
    recipes_path = _write_recipes(tmp_path, [recipe_with_salt])
    seed_logger = logging.getLogger("apps.recipes.services.seed")
    seed_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="apps.recipes.services.seed"):
            seed_recipes(recipes_path)
    finally:
        seed_logger.removeHandler(caplog.handler)
    assert any(
        "recipe_uses_zero_nutrition_ingredient" in r.getMessage()
        and "sr_salt_raw" in r.getMessage()
        for r in caplog.records
    )


def test_seed_recipes_flags_recipe_outside_calorie_range(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Use only 1g of rice → 3.5 kcal / 1 serving → < 50 → out of range
    _seed_test_ingredients(tmp_path)
    tiny_recipe = {
        **_MINIMAL_RECIPE,
        "slug": "sr-tiny-recipe",
        "servings": 1,
        "ingredients": [
            {
                "ingredient_app_id": "sr_rice_raw",
                "quantity_grams": 1.0,
                "display_quantity": None,
                "display_unit": None,
                "notes": "",
            }
        ],
    }
    recipes_path = _write_recipes(tmp_path, [tiny_recipe])
    seed_logger = logging.getLogger("apps.recipes.services.seed")
    seed_logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.WARNING, logger="apps.recipes.services.seed"):
            seed_recipes(recipes_path)
    finally:
        seed_logger.removeHandler(caplog.handler)
    assert any("recipe_calorie_out_of_range" in r.getMessage() for r in caplog.records)


def test_seed_recipes_computes_nutrition_on_each_recipe(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)

    recipe = Recipe.objects.get(slug="sr-test-dal-rice")
    assert recipe.cached_nutrition is not None
    assert recipe.cached_calories_per_serving is not None
    assert recipe.cached_calories_per_serving > 0


def test_seed_recipes_loads_name_alt_estimated_difficulty_spice_level(tmp_path: Path) -> None:
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)

    recipe = Recipe.objects.get(slug="sr-test-dal-rice")
    assert recipe.name_alt == "Dal Chawal"
    assert recipe.estimated_difficulty == "beginner"
    assert recipe.spice_level == "mild"


def test_seed_full_integration(tmp_path: Path) -> None:
    """Load all three seed files in order, verify combined DB state."""
    _seed_test_ingredients(tmp_path)
    _seed_test_units(tmp_path)
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])
    seed_recipes(recipes_path)

    assert Ingredient.objects.count() == 3
    assert HouseholdUnit.objects.count() == 2
    assert Recipe.objects.count() == 1
    recipe = Recipe.objects.get(slug="sr-test-dal-rice")
    assert recipe.cached_nutrition is not None
    assert recipe.cost_known is True  # both ingredients have prices


# ---------------------------------------------------------------------------
# nutrition.py — compute_recipe_nutrition
# ---------------------------------------------------------------------------


def test_compute_nutrition_sums_correctly_two_ingredients(tmp_path: Path) -> None:
    """Handcraft: 100g rice + 50g dal, 2 servings → exact per-serving values."""
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    rice = IngredientFactory(
        app_id="hn_rice_raw",
        name="HN Rice",
        per_100g_nutrition={
            "calories": 350,
            "protein_g": 7.0,
            "carbs_g": 76.0,
            "fat_g": 1.0,
            "fiber_g": 2.8,
            "micronutrients": {
                k: 0.0
                for k in [
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
            },
        },
    )
    dal = IngredientFactory(
        app_id="hn_dal_raw",
        name="HN Dal",
        per_100g_nutrition={
            "calories": 340,
            "protein_g": 24.0,
            "carbs_g": 60.0,
            "fat_g": 1.0,
            "fiber_g": 8.0,
            "micronutrients": {
                k: 0.0
                for k in [
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
            },
        },
    )
    recipe = RecipeFactory(slug="hn-dal-rice", servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=rice, quantity_grams="100.00", order=0)
    RecipeIngredientFactory(recipe=recipe, ingredient=dal, quantity_grams="50.00", order=1)

    # rice: 350 cal, 7 prot, 76 carb, 1 fat, 2.8 fiber (100g → ×1.0)
    # dal:  170 cal, 12 prot, 30 carb, 0.5 fat, 4.0 fiber (50g → ×0.5)
    # total: 520 cal, 19 prot, 106 carb, 1.5 fat, 6.8 fiber
    # per serving (/2): 260 cal, 9.5 prot, 53.0 carb, 0.75 fat, 3.4 fiber
    result = compute_recipe_nutrition(recipe)
    assert result["calories"] == 260
    assert result["protein_g"] == 9.5
    assert result["carbs_g"] == 53.0
    assert result["fat_g"] == 0.75
    assert result["fiber_g"] == 3.4


def test_compute_nutrition_divides_by_servings(tmp_path: Path) -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="div_rice_raw",
        name="Div Rice",
        per_100g_nutrition={
            "calories": 400,
            "protein_g": 8.0,
            "carbs_g": 80.0,
            "fat_g": 2.0,
            "fiber_g": 3.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="div-rice", servings=4)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="200.00")
    result = compute_recipe_nutrition(recipe)
    # 200g of 400cal/100g = 800 cal total, /4 servings = 200 per serving
    assert result["calories"] == 200


def test_compute_nutrition_handles_micronutrients(tmp_path: Path) -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="micro_dal_raw",
        name="Micro Dal",
        per_100g_nutrition={
            "calories": 340,
            "protein_g": 24.0,
            "carbs_g": 60.0,
            "fat_g": 1.0,
            "fiber_g": 8.0,
            "micronutrients": {
                "iron_mg": 3.0,
                "calcium_mg": 50.0,
                "vit_c_mg": 0.0,
                "potassium_mg": 900.0,
                "sodium_mg": 5.0,
                "magnesium_mg": 80.0,
                "zinc_mg": 2.0,
                "vit_a_iu": 0.0,
                "folate_ug": 110.0,
                "vit_b12_ug": None,
            },
        },
    )
    recipe = RecipeFactory(slug="micro-dal", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    result = compute_recipe_nutrition(recipe)
    assert result["micronutrients"]["iron_mg"] == 3.0
    assert result["micronutrients"]["calcium_mg"] == 50.0
    assert result["micronutrients"]["folate_ug"] == 110.0


def test_compute_nutrition_null_micronutrients_treated_as_zero() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="null_micro_raw",
        name="Null Micro Ing",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {
                "iron_mg": None,
                "calcium_mg": None,
                "vit_c_mg": None,
                "potassium_mg": None,
                "sodium_mg": None,
                "magnesium_mg": None,
                "zinc_mg": None,
                "vit_a_iu": None,
                "folate_ug": None,
                "vit_b12_ug": None,
            },
        },
    )
    recipe = RecipeFactory(slug="null-micro", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    result = compute_recipe_nutrition(recipe)
    assert result["micronutrients"]["iron_mg"] == 0.0
    assert result["micronutrients"]["vit_b12_ug"] == 0.0


def test_compute_nutrition_writes_computed_at_timestamp() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="ts_ing_raw",
        name="TS Ingredient",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="ts-recipe", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    result = compute_recipe_nutrition(recipe)
    assert "computed_at" in result
    assert "T" in result["computed_at"]  # ISO 8601


def test_compute_nutrition_computes_cost_from_ingredient_prices() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="cost_rice_raw",
        name="Cost Rice",
        approximate_price_inr_per_kg="80.00",
        per_100g_nutrition={
            "calories": 350,
            "protein_g": 7.0,
            "carbs_g": 76.0,
            "fat_g": 1.0,
            "fiber_g": 2.8,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="cost-rice", servings=1)
    # 200g at ₹80/kg = 200/1000 * 80 = ₹16.00
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="200.00")
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cached_cost_inr is not None
    assert float(recipe.cached_cost_inr) == pytest.approx(16.0)


def test_compute_nutrition_sets_cost_known_true_when_priced_ingredients_dominate() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    priced = IngredientFactory(
        app_id="priced_ing_raw",
        name="Priced Ingredient",
        approximate_price_inr_per_kg="50.00",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    unpriced = IngredientFactory(
        app_id="unpriced_ing_raw",
        name="Unpriced Ingredient",
        approximate_price_inr_per_kg=None,
        per_100g_nutrition={
            "calories": 50,
            "protein_g": 1.0,
            "carbs_g": 10.0,
            "fat_g": 0.5,
            "fiber_g": 0.5,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="cost-known-true", servings=1)
    # 90g priced + 10g unpriced = 90% priced → cost_known=True
    RecipeIngredientFactory(recipe=recipe, ingredient=priced, quantity_grams="90.00", order=0)
    RecipeIngredientFactory(recipe=recipe, ingredient=unpriced, quantity_grams="10.00", order=1)
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cost_known is True


def test_compute_nutrition_sets_cost_known_false_when_most_weight_unpriced() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    priced = IngredientFactory(
        app_id="priced2_ing_raw",
        name="Priced2 Ingredient",
        approximate_price_inr_per_kg="50.00",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    unpriced = IngredientFactory(
        app_id="unpriced2_ing_raw",
        name="Unpriced2 Ingredient",
        approximate_price_inr_per_kg=None,
        per_100g_nutrition={
            "calories": 50,
            "protein_g": 1.0,
            "carbs_g": 10.0,
            "fat_g": 0.5,
            "fiber_g": 0.5,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="cost-known-false", servings=1)
    # 10g priced + 90g unpriced = 10% priced → cost_known=False
    RecipeIngredientFactory(recipe=recipe, ingredient=priced, quantity_grams="10.00", order=0)
    RecipeIngredientFactory(recipe=recipe, ingredient=unpriced, quantity_grams="90.00", order=1)
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cost_known is False


def test_compute_nutrition_cost_null_when_no_ingredients_have_price() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="free_ing_raw",
        name="Free Ingredient",
        approximate_price_inr_per_kg=None,
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="free-recipe", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cached_cost_inr is None
    assert recipe.cost_known is False


def test_compute_nutrition_handles_zero_calorie_ingredient() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="zero_cal_raw",
        name="Zero Cal Ingredient",
        per_100g_nutrition={
            "calories": 0,
            "protein_g": 0.0,
            "carbs_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="zero-cal-recipe", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    result = compute_recipe_nutrition(recipe)
    assert result["calories"] == 0


def test_compute_nutrition_per_serving_is_stored_on_recipe() -> None:
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="stored_ing_raw",
        name="Stored Ingredient",
        per_100g_nutrition={
            "calories": 400,
            "protein_g": 8.0,
            "carbs_g": 80.0,
            "fat_g": 2.0,
            "fiber_g": 3.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="stored-recipe", servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="200.00")
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cached_nutrition is not None
    assert recipe.cached_nutrition["calories"] == recipe.cached_calories_per_serving


def test_compute_nutrition_populates_cached_calories_per_serving() -> None:
    """Denormalized integer field must match cached_nutrition['calories'] exactly."""
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="denom_ing_raw",
        name="Denom Ingredient",
        per_100g_nutrition={
            "calories": 350,
            "protein_g": 7.0,
            "carbs_g": 76.0,
            "fat_g": 1.0,
            "fiber_g": 2.8,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="denom-recipe", servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")
    result = compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert recipe.cached_calories_per_serving == result["calories"]
    assert isinstance(recipe.cached_calories_per_serving, int)


def test_compute_cost_is_total_recipe_not_per_serving() -> None:
    """cached_cost_inr is total recipe cost (all servings), not per-serving."""
    from apps.recipes.services.nutrition import compute_recipe_nutrition
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="total_cost_raw",
        name="Total Cost Ingredient",
        approximate_price_inr_per_kg="100.00",
        per_100g_nutrition={
            "calories": 350,
            "protein_g": 7.0,
            "carbs_g": 76.0,
            "fat_g": 1.0,
            "fiber_g": 2.8,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="total-cost-recipe", servings=4)
    # 400g at ₹100/kg = ₹40 total for 4 servings (₹10/serving)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="400.00")
    compute_recipe_nutrition(recipe)

    recipe.refresh_from_db()
    assert float(recipe.cached_cost_inr) == pytest.approx(40.0)


def test_recompute_recipes_using_ingredient_updates_all_recipes() -> None:
    from apps.recipes.services.nutrition import (
        recompute_recipes_using_ingredient,
    )
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="recomp_ing_raw",
        name="Recomp Ingredient",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    recipe1 = RecipeFactory(slug="recomp-recipe-1", servings=1)
    recipe2 = RecipeFactory(slug="recomp-recipe-2", servings=1)
    RecipeIngredientFactory(recipe=recipe1, ingredient=ing, quantity_grams="100.00")
    RecipeIngredientFactory(recipe=recipe2, ingredient=ing, quantity_grams="100.00")

    recompute_recipes_using_ingredient(ing.pk)

    recipe1.refresh_from_db()
    recipe2.refresh_from_db()
    assert recipe1.cached_calories_per_serving == 100
    assert recipe2.cached_calories_per_serving == 100


def test_recompute_returns_correct_count() -> None:
    from apps.recipes.services.nutrition import recompute_recipes_using_ingredient
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="count_ing_raw",
        name="Count Ingredient",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    for i in range(3):
        r = RecipeFactory(slug=f"count-recipe-{i}", servings=1)
        RecipeIngredientFactory(recipe=r, ingredient=ing, quantity_grams="100.00")

    count = recompute_recipes_using_ingredient(ing.pk)
    assert count == 3


def test_recompute_skips_inactive_recipes() -> None:
    from apps.recipes.services.nutrition import recompute_recipes_using_ingredient
    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="inactive_ing_raw",
        name="Inactive Ingredient",
        per_100g_nutrition={
            "calories": 100,
            "protein_g": 2.0,
            "carbs_g": 20.0,
            "fat_g": 1.0,
            "fiber_g": 1.0,
            "micronutrients": {},
        },
    )
    active_r = RecipeFactory(slug="inactive-active-recipe", servings=1, is_active=True)
    inactive_r = RecipeFactory(slug="inactive-inactive-recipe", servings=1, is_active=False)
    RecipeIngredientFactory(recipe=active_r, ingredient=ing, quantity_grams="100.00")
    RecipeIngredientFactory(recipe=inactive_r, ingredient=ing, quantity_grams="100.00")

    count = recompute_recipes_using_ingredient(ing.pk)
    assert count == 1


# ---------------------------------------------------------------------------
# Management command — integration tests
# ---------------------------------------------------------------------------


def test_seed_recipes_command_runs_full_flow(tmp_path: Path) -> None:
    """seed_recipes command seeds all three tables end-to-end."""
    from django.core.management import call_command

    ing_path = _write_seed(tmp_path, [_INGREDIENT_RICE, _INGREDIENT_DAL])
    units_path = _write_units(
        tmp_path,
        [{"unit_name": "katori", "ingredient_app_id": "sr_rice_raw", "grams": 100.0}],
    )
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])

    call_command(
        "seed_recipes",
        ingredients_path=ing_path,
        household_units_path=units_path,
        recipes_path=recipes_path,
    )

    assert Ingredient.objects.count() == 2
    assert HouseholdUnit.objects.count() == 1
    assert Recipe.objects.count() == 1
    recipe = Recipe.objects.get(slug="sr-test-dal-rice")
    assert recipe.cached_calories_per_serving is not None


def test_seed_recipes_command_idempotent(tmp_path: Path) -> None:
    """Running seed_recipes twice produces the same final state."""
    from django.core.management import call_command

    ing_path = _write_seed(tmp_path, [_INGREDIENT_RICE, _INGREDIENT_DAL])
    units_path = _write_units(
        tmp_path,
        [{"unit_name": "katori", "ingredient_app_id": "sr_rice_raw", "grams": 100.0}],
    )
    recipes_path = _write_recipes(tmp_path, [_MINIMAL_RECIPE])

    kwargs = dict(
        ingredients_path=ing_path,
        household_units_path=units_path,
        recipes_path=recipes_path,
    )
    call_command("seed_recipes", **kwargs)
    call_command("seed_recipes", **kwargs)

    assert Ingredient.objects.count() == 2
    assert Recipe.objects.count() == 1


def test_seed_recipes_command_rollback_on_bad_data(tmp_path: Path) -> None:
    """If seed_recipes fails (bad ingredient ref), the whole transaction rolls back."""
    from django.core.management import call_command

    from core.exceptions import AppValidationError

    ing_path = _write_seed(tmp_path, [_INGREDIENT_RICE])
    units_path = _write_units(tmp_path, [])
    bad_recipe = {
        **_MINIMAL_RECIPE,
        "ingredients": [{"ingredient_app_id": "does_not_exist_raw", "quantity_grams": 100.0}],
    }
    recipes_path = _write_recipes(tmp_path, [bad_recipe])

    with pytest.raises((AppValidationError, Exception)):
        call_command(
            "seed_recipes",
            ingredients_path=ing_path,
            household_units_path=units_path,
            recipes_path=recipes_path,
        )
    # Ingredient was seeded inside the same transaction → must also roll back
    assert Recipe.objects.count() == 0


def test_recompute_nutrition_command(tmp_path: Path) -> None:
    """recompute_nutrition command updates cached values on existing recipes."""
    from django.core.management import call_command

    from apps.recipes.tests.factories import (
        IngredientFactory,
        RecipeFactory,
        RecipeIngredientFactory,
    )

    ing = IngredientFactory(
        app_id="cmd_ing_raw",
        name="Cmd Ingredient",
        per_100g_nutrition={
            "calories": 200,
            "protein_g": 4.0,
            "carbs_g": 40.0,
            "fat_g": 2.0,
            "fiber_g": 2.0,
            "micronutrients": {},
        },
    )
    recipe = RecipeFactory(slug="cmd-recipe", servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ing, quantity_grams="100.00")

    call_command("recompute_nutrition")

    recipe.refresh_from_db()
    assert recipe.cached_calories_per_serving == 200
