"""Fixtures for mealplan view tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client
from freezegun import freeze_time

from apps.accounts.models import User

REGISTER_URL = "/api/v1/auth/register"
MEALPLANS_TODAY_URL = "/api/v1/mealplans/today/"
MEALPLANS_WEEK_URL = "/api/v1/mealplans/week/"
MEALPLANS_DAY_URL = "/api/v1/mealplans/day/{}/"
MEALPLANS_REGEN_SLOT_URL = "/api/v1/mealplans/regenerate-slot/"
MEALPLANS_REGEN_URL = "/api/v1/mealplans/regenerate/"
MEALPLANS_WEEK_GENERATE_URL = "/api/v1/mealplans/week/generate/"
MEALPLANS_GROCERY_URL = "/api/v1/mealplans/week/{}/grocery/"
MEALPLANS_GROCERY_REGEN_URL = "/api/v1/mealplans/week/{}/grocery/regenerate/"

# Frozen date: 2026-05-25 is a Monday — weekday=0, week=[2026-05-25, 2026-05-31]
FROZEN_TODAY = "2026-05-25"

FAKE_TOKEN_PAYLOAD: dict[str, Any] = {
    "uid": "test-firebase-uid-mealplans",
    "email": "mealplantest@example.com",
    "name": "MealPlan Test User",
}


def _auth_header() -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": "Bearer fake-mealplan-token"}


@pytest.fixture()
def registered_user(client: Client) -> tuple[Client, User]:  # type: ignore[type-arg]
    """User registered via auth API — no DietaryProfile attached."""
    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])
    return client, user


@pytest.fixture()
def registered_user_with_profile(
    client: Client,
) -> tuple[Client, User, Any, dict[str, list[Any]]]:
    """User + DietaryProfile + 2 active recipes per slot.

    Profile: 31-yr-old male 80 kg / 180 cm, moderate, maintain, vegetarian,
    no budget, max_prep_time_min=60.
    target_calories ≈ 2751, so calorie windows:
        breakfast [515, 858]  → recipes use 688, 700
        lunch     [825, 1375] → recipes use 1100, 1050
        dinner    [721, 1202] → recipes use 962, 950
    """
    from apps.profiles.tests.factories import DietaryProfileFactory
    from apps.recipes.tests.factories import RecipeFactory

    client.defaults.update(_auth_header())
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        client.post(REGISTER_URL)
    user = User.objects.get(firebase_uid=FAKE_TOKEN_PAYLOAD["uid"])

    with freeze_time(FROZEN_TODAY):
        profile = DietaryProfileFactory(
            user=user,
            daily_food_budget_inr=None,
            weekly_food_budget_inr=None,
            max_prep_time_min=60,
            diet_pattern="vegetarian",
        )

    def _nutrition(cal: int) -> dict[str, Any]:
        return {
            "calories": cal,
            "protein_g": 20.0,
            "carbs_g": 80.0,
            "fat_g": 15.0,
            "fiber_g": 4.0,
        }

    def _r(meal_type: str, cal: int) -> Any:
        return RecipeFactory(
            meal_type=meal_type,
            diet_tags=["vegetarian"],
            cached_calories_per_serving=cal,
            cached_nutrition=_nutrition(cal),
            is_active=True,
            prep_time_min=15,
            cost_known=False,
        )

    slot_recipes: dict[str, list[Any]] = {
        "breakfast": [_r("breakfast", 688), _r("breakfast", 700)],
        "lunch": [_r("lunch", 1100), _r("lunch", 1050)],
        "dinner": [_r("dinner", 962), _r("dinner", 950)],
    }

    return client, user, profile, slot_recipes
