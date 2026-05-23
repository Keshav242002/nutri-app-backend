"""
View / endpoint tests for apps/recipes.

All tests use the registered_user fixture from conftest.py, which returns
(client_with_auth, user) with Firebase mock active for registration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from apps.recipes.models import Recipe
from apps.recipes.tests.conftest import FAKE_TOKEN_PAYLOAD, RECIPE_LIST_URL
from apps.recipes.tests.factories import (
    HouseholdUnitFactory,
    IngredientFactory,
    RecipeFactory,
    RecipeIngredientFactory,
)

pytestmark = pytest.mark.django_db

RECIPE_DETAIL_URL = "/api/v1/recipes/{slug}/"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NUTRITION = {
    "calories": 400,
    "protein_g": 12.0,
    "carbs_g": 60.0,
    "fat_g": 8.0,
    "fiber_g": 3.0,
    "micronutrients": {
        "iron_mg": 2.0,
        "calcium_mg": 50.0,
        "vit_c_mg": 5.0,
        "potassium_mg": 200.0,
        "sodium_mg": 150.0,
        "magnesium_mg": 30.0,
        "zinc_mg": 1.5,
        "vit_a_iu": 100.0,
        "folate_ug": 20.0,
        "vit_b12_ug": 0.0,
    },
    "computed_at": "2026-05-24T10:00:00+00:00",
}


def _make_recipe(**kwargs: Any) -> Recipe:  # type: ignore[return]
    """Create a Recipe with sensible defaults for view tests."""
    defaults: dict[str, Any] = {
        "cached_nutrition": _NUTRITION,
        "cached_calories_per_serving": 400,
        "cached_cost_inr": Decimal("60.00"),
        "cost_known": True,
        "is_active": True,
    }
    defaults.update(kwargs)
    return RecipeFactory(**defaults)


# ---------------------------------------------------------------------------
# List view tests
# ---------------------------------------------------------------------------


def test_recipe_list_returns_200_with_recipes(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe()
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "results" in data["data"]
    assert len(data["data"]["results"]) >= 1


def test_recipe_list_requires_authentication() -> None:
    from django.test import Client

    anon = Client()
    response = anon.get(RECIPE_LIST_URL)
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"


def test_recipe_list_pagination_default_page_size(registered_user: Any) -> None:
    client, _ = registered_user
    for _ in range(3):
        _make_recipe()
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "results" in data
    assert "next" in data
    assert "previous" in data


def test_recipe_list_pagination_cursor_next(registered_user: Any) -> None:
    client, _ = registered_user
    for i in range(22):
        RecipeFactory(
            name=f"Pagination Recipe {i}",
            slug=f"pagination-recipe-{i}",
            is_active=True,
        )
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["results"]) == 20
    assert data["next"] is not None

    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response2 = client.get(data["next"])
    assert response2.status_code == 200
    data2 = response2.json()["data"]
    assert len(data2["results"]) >= 2


def test_recipe_list_filter_by_meal_type(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(meal_type="breakfast", slug="bfast-1")
    _make_recipe(meal_type="lunch", slug="lunch-1")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?meal_type=breakfast")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert all(r["meal_type"] == "breakfast" for r in results)
    slugs = [r["slug"] for r in results]
    assert "bfast-1" in slugs
    assert "lunch-1" not in slugs


def test_recipe_list_filter_by_cuisine(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(cuisine="north_indian", slug="north-1")
    _make_recipe(cuisine="bengali", slug="bengali-1")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?cuisine=bengali")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "bengali-1" in slugs
    assert "north-1" not in slugs


def test_recipe_list_filter_by_diet_tags_single(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="vegan-r", diet_tags=["vegan", "gluten_free"])
    _make_recipe(slug="nonveg-r", diet_tags=["non_vegetarian"])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?diet_tags=vegan")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "vegan-r" in slugs
    assert "nonveg-r" not in slugs


def test_recipe_list_filter_by_diet_tags_multiple_all_must_match(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="both-tags", diet_tags=["vegan", "gluten_free"])
    _make_recipe(slug="only-vegan", diet_tags=["vegan"])
    _make_recipe(slug="only-gf", diet_tags=["gluten_free"])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?diet_tags=vegan,gluten_free")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "both-tags" in slugs
    assert "only-vegan" not in slugs
    assert "only-gf" not in slugs


def test_recipe_list_excludes_allergens_single(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="has-dairy", allergen_tags=["dairy"])
    _make_recipe(slug="no-dairy", allergen_tags=[])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?exclude_allergens=dairy")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "no-dairy" in slugs
    assert "has-dairy" not in slugs


def test_recipe_list_excludes_allergens_multiple(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="has-gluten", allergen_tags=["gluten"])
    _make_recipe(slug="has-dairy-gluten", allergen_tags=["dairy", "gluten"])
    _make_recipe(slug="clean", allergen_tags=[])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?exclude_allergens=dairy,gluten")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "clean" in slugs
    assert "has-gluten" not in slugs
    assert "has-dairy-gluten" not in slugs


def test_recipe_list_filter_by_max_prep_time(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="fast", prep_time_min=10)
    _make_recipe(slug="slow", prep_time_min=60)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?max_prep_time=15")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "fast" in slugs
    assert "slow" not in slugs


def test_recipe_list_filter_by_estimated_difficulty(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="beginner-r", estimated_difficulty="beginner")
    _make_recipe(slug="advanced-r", estimated_difficulty="advanced")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?estimated_difficulty=beginner")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "beginner-r" in slugs
    assert "advanced-r" not in slugs


def test_recipe_list_filter_by_spice_level(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="mild-r", spice_level="mild")
    _make_recipe(slug="hot-r", spice_level="hot")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?spice_level=mild")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "mild-r" in slugs
    assert "hot-r" not in slugs


def test_recipe_list_search_by_name(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="aloo-paratha", name="Aloo Paratha")
    _make_recipe(slug="dal-rice", name="Dal Rice")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?search=paratha")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "aloo-paratha" in slugs
    assert "dal-rice" not in slugs


def test_recipe_list_search_by_name_alt(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="onion-poha", name="Onion Poha", name_alt="kanda poha")
    _make_recipe(slug="upma", name="Upma", name_alt="")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?search=kanda")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "onion-poha" in slugs
    assert "upma" not in slugs


def test_recipe_list_search_case_insensitive(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="idli-sambar", name="Idli Sambar")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?search=IDLI")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "idli-sambar" in slugs


def test_recipe_list_filter_by_max_cost_per_serving(registered_user: Any) -> None:
    client, _ = registered_user
    # cost_known=True, cached_cost_inr=30 (2 servings → 15/serving)
    _make_recipe(slug="cheap", cached_cost_inr=Decimal("30.00"), servings=2, cost_known=True)
    # cost_known=True, cached_cost_inr=200 (2 servings → 100/serving)
    _make_recipe(slug="expensive", cached_cost_inr=Decimal("200.00"), servings=2, cost_known=True)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?max_cost_per_serving_inr=20")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "cheap" in slugs
    assert "expensive" not in slugs


def test_recipe_list_cost_filter_only_includes_cost_known_recipes(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="known-cheap", cached_cost_inr=Decimal("10.00"), servings=2, cost_known=True)
    _make_recipe(slug="unknown-cost", cached_cost_inr=None, servings=2, cost_known=False)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?max_cost_per_serving_inr=100")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "known-cheap" in slugs
    assert "unknown-cost" not in slugs


def test_recipe_list_filter_includes_ingredients_single(registered_user: Any) -> None:
    client, _ = registered_user
    ing_rice = IngredientFactory(app_id="filter_rice_raw", name="Filter Rice Raw")
    ing_dal = IngredientFactory(app_id="filter_dal_raw", name="Filter Dal Raw")
    recipe_a = _make_recipe(slug="with-rice-only")
    recipe_b = _make_recipe(slug="with-dal-only")
    RecipeIngredientFactory(recipe=recipe_a, ingredient=ing_rice)
    RecipeIngredientFactory(recipe=recipe_b, ingredient=ing_dal)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?includes_ingredients=filter_rice_raw")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "with-rice-only" in slugs
    assert "with-dal-only" not in slugs


def test_recipe_list_filter_includes_ingredients_multiple(registered_user: Any) -> None:
    client, _ = registered_user
    ing_rice = IngredientFactory(app_id="multi_rice_raw", name="Multi Rice Raw")
    ing_dal = IngredientFactory(app_id="multi_dal_raw", name="Multi Dal Raw")
    recipe_both = _make_recipe(slug="both-ingr")
    recipe_rice_only = _make_recipe(slug="rice-only-ingr")
    recipe_dal_only = _make_recipe(slug="dal-only-ingr")
    RecipeIngredientFactory(recipe=recipe_both, ingredient=ing_rice)
    # use a different ingredient for dal in recipe_both to avoid unique_together conflict
    ing_dal2 = IngredientFactory(app_id="multi_dal2_raw", name="Multi Dal2 Raw")
    RecipeIngredientFactory(recipe=recipe_both, ingredient=ing_dal2)
    RecipeIngredientFactory(recipe=recipe_rice_only, ingredient=ing_rice)
    RecipeIngredientFactory(recipe=recipe_dal_only, ingredient=ing_dal)

    # Filter for recipes containing BOTH multi_rice_raw and multi_dal2_raw
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(
            RECIPE_LIST_URL + "?includes_ingredients=multi_rice_raw,multi_dal2_raw"
        )
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "both-ingr" in slugs
    assert "rice-only-ingr" not in slugs
    assert "dal-only-ingr" not in slugs


def test_recipe_list_filter_excludes_ingredients(registered_user: Any) -> None:
    client, _ = registered_user
    ing_onion = IngredientFactory(app_id="excl_onion_raw", name="Excl Onion Raw")
    recipe_with = _make_recipe(slug="recipe-with-onion")
    _make_recipe(slug="recipe-without-onion")
    RecipeIngredientFactory(recipe=recipe_with, ingredient=ing_onion)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?excludes_ingredients=excl_onion_raw")
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "recipe-without-onion" in slugs
    assert "recipe-with-onion" not in slugs


def test_recipe_list_combined_filters(registered_user: Any) -> None:
    client, _ = registered_user
    # matches all: breakfast + north_indian + vegan + prep_time=5
    _make_recipe(
        slug="combo-match",
        meal_type="breakfast",
        cuisine="north_indian",
        diet_tags=["vegan"],
        prep_time_min=5,
    )
    # wrong meal_type
    _make_recipe(
        slug="combo-wrong-meal",
        meal_type="lunch",
        cuisine="north_indian",
        diet_tags=["vegan"],
        prep_time_min=5,
    )
    # wrong cuisine
    _make_recipe(
        slug="combo-wrong-cuisine",
        meal_type="breakfast",
        cuisine="bengali",
        diet_tags=["vegan"],
        prep_time_min=5,
    )
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(
            RECIPE_LIST_URL
            + "?meal_type=breakfast&cuisine=north_indian&diet_tags=vegan&max_prep_time=10"
        )
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "combo-match" in slugs
    assert "combo-wrong-meal" not in slugs
    assert "combo-wrong-cuisine" not in slugs


def test_recipe_list_response_envelope_shape(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe()
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "message" in body
    assert "data" in body
    data = body["data"]
    assert "results" in data
    assert "next" in data
    assert "previous" in data


def test_recipe_list_excludes_inactive_recipes(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="active-r", is_active=True)
    _make_recipe(slug="inactive-r", is_active=False)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    slugs = [r["slug"] for r in results]
    assert "active-r" in slugs
    assert "inactive-r" not in slugs


def test_recipe_list_includes_cached_nutrition_summary(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="nutri-r")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    result = next(r for r in response.json()["data"]["results"] if r["slug"] == "nutri-r")
    summary = result["cached_nutrition_summary"]
    assert summary is not None
    assert "calories" in summary
    assert "protein_g" in summary
    assert "carbs_g" in summary
    assert "fat_g" in summary
    assert "fiber_g" in summary
    # Summary must NOT include micronutrients
    assert "micronutrients" not in summary


def test_recipe_list_includes_cost_per_serving(registered_user: Any) -> None:
    client, _ = registered_user
    _make_recipe(slug="cost-r", cached_cost_inr=Decimal("80.00"), servings=2, cost_known=True)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    result = next(r for r in response.json()["data"]["results"] if r["slug"] == "cost-r")
    assert result["cached_cost_per_serving_inr"] == 40.0


def test_recipe_list_empty_result(registered_user: Any) -> None:
    client, _ = registered_user
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL + "?meal_type=breakfast")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["results"] == []


# ---------------------------------------------------------------------------
# Detail view tests
# ---------------------------------------------------------------------------


def test_recipe_detail_returns_200_with_full_payload(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="detail-r", name="Detail Recipe", instructions=["Step A", "Step B"])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["slug"] == "detail-r"
    assert data["name"] == "Detail Recipe"


def test_recipe_detail_requires_authentication() -> None:
    from django.test import Client

    recipe = _make_recipe(slug="auth-check-r")
    anon = Client()
    response = anon.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 401
    assert response.json()["status"] == "error"


def test_recipe_detail_404_for_nonexistent_slug(registered_user: Any) -> None:
    client, _ = registered_user
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug="nonexistent-recipe-slug"))
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NOT_FOUND"


def test_recipe_detail_404_for_inactive_recipe(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="inactive-detail-r", is_active=False)
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 404


def test_recipe_detail_includes_ingredients_list(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="detail-with-ingr")
    ing = IngredientFactory(app_id="detail_rice_raw", name="Detail Rice Raw")
    unit = HouseholdUnitFactory(name="katori", ingredient=ing, grams=Decimal("150.00"))
    RecipeIngredientFactory(
        recipe=recipe,
        ingredient=ing,
        quantity_grams=Decimal("150.00"),
        display_quantity=Decimal("1.00"),
        display_unit=unit,
        notes="washed",
        order=0,
    )
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 200
    data = response.json()["data"]
    assert "ingredients" in data
    assert len(data["ingredients"]) >= 1
    ingr = data["ingredients"][0]
    assert ingr["ingredient_name"] == "Detail Rice Raw"
    assert ingr["ingredient_app_id"] == "detail_rice_raw"
    assert ingr["display_unit_name"] == "katori"
    assert ingr["notes"] == "washed"


def test_recipe_detail_includes_full_micronutrients(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="detail-micros")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 200
    cached = response.json()["data"]["cached_nutrition"]
    assert cached is not None
    assert "micronutrients" in cached
    micros = cached["micronutrients"]
    for key in [
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
    ]:
        assert key in micros


def test_recipe_detail_includes_instructions(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="detail-instr", instructions=["Boil water", "Add dal", "Serve"])
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["instructions"] == ["Boil water", "Add dal", "Serve"]


def test_recipe_detail_response_envelope_shape(registered_user: Any) -> None:
    client, _ = registered_user
    recipe = _make_recipe(slug="envelope-check-r")
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug=recipe.slug))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "message" in body
    assert "data" in body
    data = body["data"]
    # Must have all list fields plus detail-only fields
    for field in [
        "name",
        "slug",
        "meal_type",
        "cuisine",
        "ingredients",
        "instructions",
        "cached_nutrition",
        "cached_cost_inr",
    ]:
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def test_end_to_end_seed_and_query(registered_user: Any, tmp_path: Any) -> None:
    """Seed all three JSON files → hit list endpoint → verify response shape."""
    import json

    from apps.recipes.services.seed import seed_household_units, seed_ingredients, seed_recipes

    client, _ = registered_user

    # Minimal ingredient + household unit + recipe seed data
    ing_data = [
        {
            "app_id": "e2e_rice_raw",
            "name": "E2E Rice Raw",
            "category": "grain",
            "form": "raw",
            "cooked_yield_ratio": 1.0,
            "allergen_tags": [],
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
            "provenance": {"source": "ifct", "confidence": "exact"},
        }
    ]
    hu_data: list[dict[str, Any]] = []
    recipe_data = [
        {
            "name": "E2E Dal Rice",
            "slug": "e2e-dal-rice",
            "meal_type": "lunch",
            "cuisine": "north_indian",
            "diet_tags": ["vegetarian"],
            "allergen_tags": [],
            "prep_time_min": 10,
            "cook_time_min": 20,
            "servings": 2,
            "estimated_difficulty": "beginner",
            "spice_level": "mild",
            "instructions": ["Cook rice"],
            "ingredients": [
                {
                    "ingredient_app_id": "e2e_rice_raw",
                    "quantity_grams": 100,
                    "display_quantity": None,
                    "display_unit": None,
                    "notes": "",
                }
            ],
        }
    ]

    ing_path = tmp_path / "ingredients.json"
    hu_path = tmp_path / "household_units.json"
    recipe_path = tmp_path / "recipes.json"
    ing_path.write_text(json.dumps(ing_data))
    hu_path.write_text(json.dumps(hu_data))
    recipe_path.write_text(json.dumps(recipe_data))

    seed_ingredients(ing_path)
    seed_household_units(hu_path)
    seed_recipes(recipe_path)

    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_LIST_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    slugs = [r["slug"] for r in body["data"]["results"]]
    assert "e2e-dal-rice" in slugs


def test_end_to_end_seed_and_detail(registered_user: Any, tmp_path: Any) -> None:
    """Seed data → hit detail endpoint → verify ingredient list in payload."""
    import json

    from apps.recipes.services.seed import seed_household_units, seed_ingredients, seed_recipes

    client, _ = registered_user

    ing_data = [
        {
            "app_id": "e2e2_potato_raw",
            "name": "E2E2 Potato Raw",
            "category": "vegetable",
            "form": "raw",
            "cooked_yield_ratio": "0.90",
            "allergen_tags": [],
            "per_100g_nutrition": {
                "calories": 77,
                "protein_g": 2.0,
                "carbs_g": 17.0,
                "fat_g": 0.1,
                "fiber_g": 2.2,
                "micronutrients": {
                    "iron_mg": 0.8,
                    "calcium_mg": 12.0,
                    "vit_c_mg": 20.0,
                    "potassium_mg": 421.0,
                    "sodium_mg": 6.0,
                    "magnesium_mg": 23.0,
                    "zinc_mg": 0.3,
                    "vit_a_iu": 2.0,
                    "folate_ug": 15.0,
                    "vit_b12_ug": 0.0,
                },
            },
            "provenance": {"source": "ifct", "confidence": "good"},
        }
    ]
    recipe_data = [
        {
            "name": "E2E Aloo Sabzi",
            "slug": "e2e-aloo-sabzi",
            "meal_type": "dinner",
            "cuisine": "north_indian",
            "diet_tags": ["vegetarian"],
            "allergen_tags": [],
            "prep_time_min": 15,
            "cook_time_min": 25,
            "servings": 2,
            "estimated_difficulty": "beginner",
            "spice_level": "medium",
            "instructions": ["Peel potatoes", "Cook"],
            "ingredients": [
                {
                    "ingredient_app_id": "e2e2_potato_raw",
                    "quantity_grams": 200,
                    "display_quantity": None,
                    "display_unit": None,
                    "notes": "peeled",
                }
            ],
        }
    ]

    ing_path = tmp_path / "ingredients.json"
    hu_path = tmp_path / "household_units.json"
    recipe_path = tmp_path / "recipes.json"
    ing_path.write_text(json.dumps(ing_data))
    hu_path.write_text(json.dumps([]))
    recipe_path.write_text(json.dumps(recipe_data))

    seed_ingredients(ing_path)
    seed_household_units(hu_path)
    seed_recipes(recipe_path)

    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        response = client.get(RECIPE_DETAIL_URL.format(slug="e2e-aloo-sabzi"))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["slug"] == "e2e-aloo-sabzi"
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["ingredient_app_id"] == "e2e2_potato_raw"
    assert data["ingredients"][0]["notes"] == "peeled"


def test_admin_registered() -> None:
    """Ingredient, Recipe, HouseholdUnit, RecipeIngredient are registered in admin."""
    from django.contrib import admin

    from apps.recipes.models import HouseholdUnit, Ingredient, Recipe, RecipeIngredient

    for model in [Ingredient, Recipe, HouseholdUnit, RecipeIngredient]:
        assert admin.site.is_registered(model), f"{model.__name__} not registered in admin"
