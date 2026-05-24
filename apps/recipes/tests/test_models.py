import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.recipes.models import (
    HouseholdUnit,
    Ingredient,
    Recipe,
    RecipeIngredient,
)
from apps.recipes.tests.factories import (
    HouseholdUnitFactory,
    IngredientFactory,
    RecipeFactory,
    RecipeIngredientFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Ingredient
# ---------------------------------------------------------------------------


def test_ingredient_str_representation() -> None:
    ing = IngredientFactory(app_id="rice_raw", name="Basmati Rice")
    assert str(ing) == "Basmati Rice (rice_raw)"


def test_ingredient_unique_app_id_constraint() -> None:
    IngredientFactory(app_id="dal_raw")
    with pytest.raises(IntegrityError):
        # bypass factory get_or_create to force a real duplicate insert
        Ingredient.objects.create(
            app_id="dal_raw",
            name="Dal Duplicate",
            category="pulse",
            form="raw",
            source="ifct",
            per_100g_nutrition={
                "calories": 350,
                "protein_g": 25.0,
                "carbs_g": 60.0,
                "fat_g": 1.0,
                "fiber_g": 8.0,
                "micronutrients": {},
            },
        )


def test_ingredient_unique_name_constraint() -> None:
    IngredientFactory(app_id="dal_raw_2", name="Unique Dal")
    with pytest.raises(IntegrityError):
        Ingredient.objects.create(
            app_id="dal_raw_3",
            name="Unique Dal",
            category="pulse",
            form="raw",
            source="ifct",
            per_100g_nutrition={
                "calories": 350,
                "protein_g": 25.0,
                "carbs_g": 60.0,
                "fat_g": 1.0,
                "fiber_g": 8.0,
                "micronutrients": {},
            },
        )


def test_ingredient_category_choices_validation() -> None:
    ing = IngredientFactory.build(category="invalid_category")
    with pytest.raises(ValidationError):
        ing.full_clean()


def test_ingredient_form_choices_validation() -> None:
    ing = IngredientFactory.build(form="invalid_form")
    with pytest.raises(ValidationError):
        ing.full_clean()


def test_ingredient_cooked_yield_ratio_min_max_validation() -> None:
    ing_low = IngredientFactory.build(cooked_yield_ratio="0.05")
    with pytest.raises(ValidationError):
        ing_low.full_clean()

    ing_high = IngredientFactory.build(cooked_yield_ratio="11.00")
    with pytest.raises(ValidationError):
        ing_high.full_clean()


# ---------------------------------------------------------------------------
# HouseholdUnit
# ---------------------------------------------------------------------------


def test_household_unit_str_representation_with_ingredient() -> None:
    ing = IngredientFactory(app_id="rice_str_raw", name="Rice Str")
    unit = HouseholdUnitFactory(name="katori", ingredient=ing, grams="150.00")
    assert str(unit) == "1 katori = 150.00g (Rice Str)"


def test_household_unit_str_representation_generic() -> None:
    unit = HouseholdUnit.objects.create(name="tbsp", ingredient=None, grams="15.00")
    assert str(unit) == "1 tbsp = 15.00g"


def test_household_unit_unique_together_constraint() -> None:
    ing = IngredientFactory(app_id="dal_unit_raw", name="Dal Unit")
    HouseholdUnitFactory(name="katori", ingredient=ing, grams="150.00")
    with pytest.raises(IntegrityError):
        HouseholdUnit.objects.create(name="katori", ingredient=ing, grams="200.00")


def test_household_unit_cascade_on_ingredient_delete() -> None:
    ing = IngredientFactory(app_id="temp_ing_raw", name="Temp Ingredient")
    unit = HouseholdUnitFactory(name="katori", ingredient=ing, grams="150.00")
    unit_id = unit.pk
    ing.delete()
    assert not HouseholdUnit.objects.filter(pk=unit_id).exists()


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


def test_recipe_str_representation() -> None:
    recipe = RecipeFactory(name="Dal Tadka")
    assert str(recipe) == "Dal Tadka"


def test_recipe_unique_slug_constraint() -> None:
    RecipeFactory(slug="dal-tadka")
    with pytest.raises(IntegrityError):
        Recipe.objects.create(
            name="Dal Tadka Duplicate",
            slug="dal-tadka",
            meal_type="lunch",
            cuisine="north_indian",
            source="seed",
            servings=2,
        )


# ---------------------------------------------------------------------------
# RecipeIngredient
# ---------------------------------------------------------------------------


def test_recipe_ingredient_protect_on_ingredient_delete() -> None:
    from django.db.models.deletion import ProtectedError

    ri = RecipeIngredientFactory()
    with pytest.raises(ProtectedError):
        ri.ingredient.delete()


def test_recipe_ingredient_cascade_on_recipe_delete() -> None:
    ri = RecipeIngredientFactory()
    ri_id = ri.pk
    ri.recipe.delete()
    assert not RecipeIngredient.objects.filter(pk=ri_id).exists()


def test_recipe_ingredient_unique_together_constraint() -> None:
    ri = RecipeIngredientFactory()
    with pytest.raises(IntegrityError):
        RecipeIngredient.objects.create(
            recipe=ri.recipe,
            ingredient=ri.ingredient,
            quantity_grams="50.00",
            order=1,
        )


# ---------------------------------------------------------------------------
# protein_source field
# ---------------------------------------------------------------------------


def test_recipe_protein_source_rejects_invalid_choice() -> None:
    recipe = RecipeFactory.build(protein_source="invalid_source")
    with pytest.raises(ValidationError) as exc_info:
        recipe.full_clean()
    assert "protein_source" in str(exc_info.value)


def test_recipe_protein_source_accepts_all_valid_choices() -> None:
    from apps.recipes.models import PROTEIN_SOURCE_CHOICES

    for value, _ in PROTEIN_SOURCE_CHOICES:
        recipe = RecipeFactory.build(protein_source=value)
        recipe.full_clean()  # should not raise
