"""View / endpoint tests for apps/mealplans — Session 3."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client
from freezegun import freeze_time

from apps.mealplans.models import MealPlan
from apps.mealplans.services.engine import NoSuitableRecipeError
from apps.mealplans.tests.conftest import (
    FAKE_TOKEN_PAYLOAD,
    FROZEN_TODAY,
    MEALPLANS_DAY_URL,
    MEALPLANS_REGEN_SLOT_URL,
    MEALPLANS_REGEN_URL,
    MEALPLANS_TODAY_URL,
    MEALPLANS_WEEK_URL,
)
from apps.mealplans.tests.factories import MealPlanFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_get(client: Client, url: str) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        return client.get(url)


def _auth_post(client: Client, url: str, data: dict[str, Any]) -> Any:
    with patch("firebase_admin.auth.verify_id_token", return_value=FAKE_TOKEN_PAYLOAD):
        return client.post(url, data=data, content_type="application/json")


# ---------------------------------------------------------------------------
# TODAY endpoint
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_today_endpoint_returns_200_with_plan(registered_user_with_profile: Any) -> None:
    client, user, profile, _ = registered_user_with_profile
    response = _auth_get(client, MEALPLANS_TODAY_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["plan_date"] == FROZEN_TODAY
    assert "breakfast" in data
    assert "lunch" in data
    assert "dinner" in data


def test_today_endpoint_requires_auth() -> None:
    anon = Client()
    response = anon.get(MEALPLANS_TODAY_URL)
    assert response.status_code == 401
    assert response.json()["status"] == "error"


@freeze_time(FROZEN_TODAY)
def test_today_endpoint_creates_plan_lazily(registered_user_with_profile: Any) -> None:
    client, user, profile, _ = registered_user_with_profile
    assert not MealPlan.objects.filter(user=user, plan_date=date(2026, 5, 25)).exists()
    response = _auth_get(client, MEALPLANS_TODAY_URL)
    assert response.status_code == 200
    assert MealPlan.objects.filter(user=user, plan_date=date(2026, 5, 25)).exists()


@freeze_time(FROZEN_TODAY)
def test_today_endpoint_returns_profile_not_found_without_profile(
    registered_user: Any,
) -> None:
    client, user = registered_user
    response = _auth_get(client, MEALPLANS_TODAY_URL)
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "PROFILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# DAY endpoint
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_day_endpoint_returns_specific_date(registered_user_with_profile: Any) -> None:
    client, user, profile, _ = registered_user_with_profile
    target_date = "2026-05-26"
    response = _auth_get(client, MEALPLANS_DAY_URL.format(target_date))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["plan_date"] == target_date


def test_day_endpoint_requires_auth() -> None:
    anon = Client()
    response = anon.get(MEALPLANS_DAY_URL.format("2026-05-26"))
    assert response.status_code == 401


@freeze_time(FROZEN_TODAY)
def test_day_endpoint_creates_plan_lazily_for_future_date(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, _ = registered_user_with_profile
    future = "2026-05-30"
    assert not MealPlan.objects.filter(user=user, plan_date=date(2026, 5, 30)).exists()
    response = _auth_get(client, MEALPLANS_DAY_URL.format(future))
    assert response.status_code == 200
    assert MealPlan.objects.filter(user=user, plan_date=date(2026, 5, 30)).exists()


# ---------------------------------------------------------------------------
# WEEK endpoint
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_week_endpoint_returns_up_to_7_plans(registered_user_with_profile: Any) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    MealPlanFactory(user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=ln, dinner=d)
    MealPlanFactory(user=user, plan_date=date(2026, 5, 26), breakfast=b, lunch=ln, dinner=d)
    MealPlanFactory(user=user, plan_date=date(2026, 5, 27), breakfast=b, lunch=ln, dinner=d)

    response = _auth_get(client, MEALPLANS_WEEK_URL)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 3


@freeze_time("2026-05-27")  # Wednesday — Monday of week = 2026-05-25
def test_week_endpoint_defaults_to_current_week_monday(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    # Create plans for Mon, Tue, Wed of the current week
    MealPlanFactory(user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=ln, dinner=d)
    MealPlanFactory(user=user, plan_date=date(2026, 5, 26), breakfast=b, lunch=ln, dinner=d)
    MealPlanFactory(user=user, plan_date=date(2026, 5, 27), breakfast=b, lunch=ln, dinner=d)
    # Plan in the previous week — should NOT be returned
    MealPlanFactory(user=user, plan_date=date(2026, 5, 24), breakfast=b, lunch=ln, dinner=d)

    response = _auth_get(client, MEALPLANS_WEEK_URL)
    assert response.status_code == 200
    plan_dates = [p["plan_date"] for p in response.json()["data"]]
    assert "2026-05-25" in plan_dates
    assert "2026-05-26" in plan_dates
    assert "2026-05-27" in plan_dates
    assert "2026-05-24" not in plan_dates


def test_week_endpoint_accepts_from_param(registered_user_with_profile: Any) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    MealPlanFactory(user=user, plan_date=date(2026, 5, 26), breakfast=b, lunch=ln, dinner=d)
    MealPlanFactory(user=user, plan_date=date(2026, 5, 27), breakfast=b, lunch=ln, dinner=d)
    # Plan before from= date — should not be returned
    MealPlanFactory(user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=ln, dinner=d)

    response = _auth_get(client, MEALPLANS_WEEK_URL + "?from=2026-05-26")
    assert response.status_code == 200
    plan_dates = [p["plan_date"] for p in response.json()["data"]]
    assert "2026-05-26" in plan_dates
    assert "2026-05-27" in plan_dates
    assert "2026-05-25" not in plan_dates


def test_week_endpoint_requires_auth() -> None:
    anon = Client()
    response = anon.get(MEALPLANS_WEEK_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# REGENERATE SLOT endpoint
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_regenerate_slot_endpoint_returns_updated_plan(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, l1, _, d = (
        slot_recipes["breakfast"][0],
        slot_recipes["lunch"][0],
        slot_recipes["lunch"][1],
        slot_recipes["dinner"][0],
    )
    plan = MealPlanFactory(user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=l1, dinner=d)

    response = _auth_post(client, MEALPLANS_REGEN_SLOT_URL, {"date": FROZEN_TODAY, "slot": "lunch"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    # Lunch must have changed (l1 excluded, other lunch recipe selected)
    plan.refresh_from_db()
    assert plan.lunch_id != l1.id


@freeze_time(FROZEN_TODAY)
def test_regenerate_slot_endpoint_returns_429_on_limit(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    MealPlanFactory(
        user=user,
        plan_date=date(2026, 5, 25),
        breakfast=b,
        lunch=ln,
        dinner=d,
        regeneration_count={"breakfast": 3, "lunch": 3, "dinner": 3},
    )
    response = _auth_post(client, MEALPLANS_REGEN_SLOT_URL, {"date": FROZEN_TODAY, "slot": "lunch"})
    assert response.status_code == 429
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "REGENERATE_LIMIT"


def test_regenerate_slot_endpoint_validates_slot_choices(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, _ = registered_user_with_profile
    response = _auth_post(
        client, MEALPLANS_REGEN_SLOT_URL, {"date": "2026-05-25", "slot": "BRUNCH"}
    )
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "VALIDATION_ERROR"


@freeze_time(FROZEN_TODAY)
def test_regenerate_slot_endpoint_returns_404_when_no_plan(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, _ = registered_user_with_profile
    # No MealPlan exists for today
    response = _auth_post(client, MEALPLANS_REGEN_SLOT_URL, {"date": FROZEN_TODAY, "slot": "lunch"})
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "MEAL_PLAN_NOT_FOUND"


@freeze_time(FROZEN_TODAY)
def test_regenerate_slot_endpoint_returns_422_when_no_suitable_recipe(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    MealPlanFactory(user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=ln, dinner=d)

    with patch(
        "apps.mealplans.views.regenerate_slot",
        side_effect=NoSuitableRecipeError(slot="lunch", plan_date=date(2026, 5, 25)),
    ):
        response = _auth_post(
            client, MEALPLANS_REGEN_SLOT_URL, {"date": FROZEN_TODAY, "slot": "lunch"}
        )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "NO_SUITABLE_RECIPE"


def test_regenerate_slot_endpoint_requires_auth() -> None:
    anon = Client()
    response = anon.post(
        MEALPLANS_REGEN_SLOT_URL,
        data={"date": "2026-05-25", "slot": "lunch"},
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# REGENERATE PLAN endpoint
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_regenerate_plan_endpoint_full_plan(registered_user_with_profile: Any) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    old_plan = MealPlanFactory(
        user=user, plan_date=date(2026, 5, 25), breakfast=b, lunch=ln, dinner=d
    )
    old_id = old_plan.pk

    response = _auth_post(client, MEALPLANS_REGEN_URL, {"date": FROZEN_TODAY})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["plan_date"] == FROZEN_TODAY
    # Old plan was deleted and a new one created
    assert not MealPlan.objects.filter(pk=old_id).exists()
    assert MealPlan.objects.filter(user=user, plan_date=date(2026, 5, 25)).exists()


@freeze_time(FROZEN_TODAY)
def test_regenerate_plan_endpoint_returns_429_on_weekly_limit(
    registered_user_with_profile: Any,
) -> None:
    client, user, profile, slot_recipes = registered_user_with_profile
    b, ln, d = slot_recipes["breakfast"][0], slot_recipes["lunch"][0], slot_recipes["dinner"][0]
    # A plan in the current week (Mon 2026-05-25 to Sun 2026-05-31) with 3 regenerations
    MealPlanFactory(
        user=user,
        plan_date=date(2026, 5, 25),
        breakfast=b,
        lunch=ln,
        dinner=d,
        full_plan_regenerations=3,
    )

    response = _auth_post(client, MEALPLANS_REGEN_URL, {"date": "2026-05-26"})
    assert response.status_code == 429
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "REGENERATE_LIMIT"


def test_regenerate_plan_endpoint_requires_auth() -> None:
    anon = Client()
    response = anon.post(
        MEALPLANS_REGEN_URL,
        data={"date": "2026-05-25"},
        content_type="application/json",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Envelope shape tests
# ---------------------------------------------------------------------------


@freeze_time(FROZEN_TODAY)
def test_response_envelope_shape_today(registered_user_with_profile: Any) -> None:
    client, user, profile, _ = registered_user_with_profile
    response = _auth_get(client, MEALPLANS_TODAY_URL)
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "message" in body
    assert "data" in body
    assert body["status"] == "success"
    data = body["data"]
    for field in ["id", "plan_date", "breakfast", "lunch", "dinner", "generated_by"]:
        assert field in data, f"Missing field in response data: {field}"


def test_response_envelope_shape_error() -> None:
    """Error envelope must have status/message/error with code."""
    anon = Client()
    response = anon.get(MEALPLANS_TODAY_URL)
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "message" in body
    assert "error" in body
    assert "code" in body["error"]
