"""Tests for grocery_service: get_or_compute_grocery_list and helpers.

Session 2 — 12 tests:
  - 3 rounding unit tests (no DB)
  - 9 integration tests (with DB)
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.mealplans.models import GroceryList
from apps.mealplans.services.grocery_service import (
    _round_to_retail_unit,
    get_or_compute_grocery_list,
)
from apps.mealplans.tests.factories import MealPlanFactory
from apps.profiles.tests.factories import DietaryProfileFactory
from apps.recipes.models import CATEGORY_GRAIN, CATEGORY_SPICE, CATEGORY_VEGETABLE
from apps.recipes.tests.factories import (
    IngredientFactory,
    RecipeFactory,
    RecipeIngredientFactory,
)

WEEK_START = date(2026, 5, 25)  # Monday


# ===========================================================================
# Unit tests — retail rounding helpers (no DB)
# ===========================================================================


def test_compute_grocery_retail_rounding_rice() -> None:
    """1 400 g grain → ceil(1400/500)*500 = 1 500 g → 1.5 kg."""
    value, unit = _round_to_retail_unit(1400.0, "grain")
    assert value == 1.5
    assert unit == "kg"


def test_compute_grocery_retail_rounding_spice() -> None:
    """12 g spice → ceil(12/50)*50 = 50 g."""
    value, unit = _round_to_retail_unit(12.0, "spice")
    assert value == 50.0
    assert unit == "g"


def test_compute_grocery_retail_rounding_eggs() -> None:
    """600 g eggs → ceil(600/50) = 12 pcs."""
    value, unit = _round_to_retail_unit(600.0, "egg")
    assert value == 12.0
    assert unit == "pcs"


# ===========================================================================
# Integration tests
# ===========================================================================


@pytest.mark.django_db
def test_compute_grocery_aggregates_across_week() -> None:
    """7 plans each using the same recipe → ingredient total = qty × 7 usages."""
    user = UserFactory()
    DietaryProfileFactory(user=user, household_size=1)

    ingredient = IngredientFactory(category=CATEGORY_GRAIN)
    recipe = RecipeFactory(servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=ingredient, quantity_grams="100.00")

    for i in range(7):
        MealPlanFactory(user=user, plan_date=WEEK_START + timedelta(days=i), lunch=recipe)

    gl = get_or_compute_grocery_list(user, WEEK_START)

    # household_size=1, servings=2 → scaling = max(1.0, 0.5) = 1.0
    # total = 100 * 1.0 * 7 = 700 g
    summary = gl.items["summary"]
    assert summary["days_covered"] == 7
    assert summary["meals_covered"] == 7
    assert summary["total_items"] == 1

    cat_items = gl.items["categories"][0]["items"]
    assert len(cat_items) == 1
    assert cat_items[0]["total_grams"] == 700.0
    assert cat_items[0]["recipe_count"] == 7


@pytest.mark.django_db
def test_compute_grocery_groups_by_category() -> None:
    """Items from different categories appear in CATEGORY_DISPLAY_ORDER order."""
    user = UserFactory()
    DietaryProfileFactory(user=user)

    grain_ing = IngredientFactory(app_id="rice_test_raw", category=CATEGORY_GRAIN)
    veg_ing = IngredientFactory(app_id="tomato_test_raw", category=CATEGORY_VEGETABLE)

    recipe = RecipeFactory(servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=grain_ing, quantity_grams="100.00")
    RecipeIngredientFactory(recipe=recipe, ingredient=veg_ing, quantity_grams="100.00")

    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)

    gl = get_or_compute_grocery_list(user, WEEK_START)

    category_names = [c["category"] for c in gl.items["categories"]]
    assert "vegetable" in category_names
    assert "grain" in category_names
    # vegetable (index 0 in CATEGORY_DISPLAY_ORDER) comes before grain (index 6)
    assert category_names.index("vegetable") < category_names.index("grain")


@pytest.mark.django_db
def test_compute_grocery_cached_on_second_call() -> None:
    """Second call returns the same cached GroceryList without recomputing."""
    user = UserFactory()
    DietaryProfileFactory(user=user)

    gl1 = get_or_compute_grocery_list(user, WEEK_START)
    gl2 = get_or_compute_grocery_list(user, WEEK_START)

    assert gl1.pk == gl2.pk
    assert GroceryList.objects.filter(user=user, week_start_date=WEEK_START).count() == 1


@pytest.mark.django_db
def test_compute_grocery_invalidated_on_slot_regen() -> None:
    """regenerate_slot deletes the cached GroceryList for that week."""
    from apps.mealplans.services.plan_service import regenerate_slot

    user = UserFactory()
    DietaryProfileFactory(user=user)
    recipe = RecipeFactory()
    new_recipe = RecipeFactory()
    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)
    GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})

    assert GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()

    with patch("apps.mealplans.services.plan_service.select_recipe", return_value=new_recipe):
        regenerate_slot(user, WEEK_START, "lunch")

    assert not GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()


@pytest.mark.django_db
def test_compute_grocery_invalidated_on_plan_regen() -> None:
    """regenerate_plan deletes the cached GroceryList for that week."""
    from apps.mealplans.services.plan_service import regenerate_plan

    user = UserFactory()
    DietaryProfileFactory(user=user)
    recipe = RecipeFactory()
    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)
    GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})

    assert GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()

    replacement = MealPlanFactory(user=user, plan_date=date(2026, 5, 26), lunch=RecipeFactory())
    with patch(
        "apps.mealplans.services.plan_service.get_or_generate_plan", return_value=replacement
    ):
        regenerate_plan(user, WEEK_START)

    assert not GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()


@pytest.mark.django_db
def test_compute_grocery_scales_by_household_size() -> None:
    """household_size=2 with recipe.servings=1 doubles ingredient quantities."""
    user = UserFactory()
    DietaryProfileFactory(user=user, household_size=2)

    ingredient = IngredientFactory(category=CATEGORY_GRAIN)
    recipe = RecipeFactory(servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ingredient, quantity_grams="100.00")

    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)

    gl = get_or_compute_grocery_list(user, WEEK_START)

    # scaling = max(1.0, 2/1) = 2.0 → 100 * 2.0 * 1 = 200 g
    cat_items = gl.items["categories"][0]["items"]
    assert cat_items[0]["total_grams"] == 200.0


@pytest.mark.django_db
def test_compute_grocery_cost_estimate() -> None:
    """Cost per item = price_per_kg × total_kg; summary totals non-null costs."""
    user = UserFactory()
    DietaryProfileFactory(user=user, household_size=1)

    ingredient = IngredientFactory(
        category=CATEGORY_GRAIN,
        approximate_price_inr_per_kg=Decimal("100.00"),
    )
    recipe = RecipeFactory(servings=1)
    RecipeIngredientFactory(recipe=recipe, ingredient=ingredient, quantity_grams="500.00")

    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)

    gl = get_or_compute_grocery_list(user, WEEK_START)

    # 100 INR/kg × 0.5 kg = 50.0 INR
    cat_items = gl.items["categories"][0]["items"]
    assert cat_items[0]["estimated_cost_inr"] == 50.0

    summary = gl.items["summary"]
    assert summary["estimated_total_cost_inr"] == 50.0
    assert summary["cost_coverage_pct"] == 100

    assert gl.estimated_cost_inr is not None
    assert float(gl.estimated_cost_inr) == 50.0


@pytest.mark.django_db
def test_compute_grocery_handles_no_meal_plans() -> None:
    """No plans for the week → empty grocery list with zero summary counts."""
    user = UserFactory()
    DietaryProfileFactory(user=user)

    gl = get_or_compute_grocery_list(user, WEEK_START)

    assert gl.items["categories"] == []
    summary = gl.items["summary"]
    assert summary["days_covered"] == 0
    assert summary["meals_covered"] == 0
    assert summary["total_items"] == 0
    assert summary["estimated_total_cost_inr"] is None
    assert gl.estimated_cost_inr is None


@pytest.mark.django_db
def test_compute_grocery_pantry_staple_flag_set_for_small_spices() -> None:
    """Spice with total < 25 g → pantry_staple=True; ≥ 25 g → pantry_staple=False."""
    user = UserFactory()
    DietaryProfileFactory(user=user, household_size=1)

    small_spice = IngredientFactory(
        app_id="turmeric_grocery_test",
        name="Turmeric",
        category=CATEGORY_SPICE,
    )
    large_spice = IngredientFactory(
        app_id="cumin_grocery_test",
        name="Cumin seeds",
        category=CATEGORY_SPICE,
    )

    recipe = RecipeFactory(servings=2)
    RecipeIngredientFactory(recipe=recipe, ingredient=small_spice, quantity_grams="12.00")
    RecipeIngredientFactory(recipe=recipe, ingredient=large_spice, quantity_grams="30.00")

    MealPlanFactory(user=user, plan_date=WEEK_START, lunch=recipe)

    # household_size=1, servings=2 → scaling = max(1.0, 0.5) = 1.0
    # small_spice: 12 * 1.0 * 1 = 12 g  (< 25 → True)
    # large_spice: 30 * 1.0 * 1 = 30 g  (≥ 25 → False)
    gl = get_or_compute_grocery_list(user, WEEK_START)

    spice_cat = next(c for c in gl.items["categories"] if c["category"] == "spice")
    items_by_id = {item["ingredient_app_id"]: item for item in spice_cat["items"]}

    assert items_by_id["turmeric_grocery_test"]["pantry_staple"] is True
    assert items_by_id["cumin_grocery_test"]["pantry_staple"] is False
