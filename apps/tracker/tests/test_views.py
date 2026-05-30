"""Endpoint tests for tracker and nutrition views."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from apps.tracker.models import (
    STATUS_ATE_CUSTOM,
    STATUS_ATE_PLANNED,
    STATUS_PLANNED,
    DailyNutritionSummary,
    MealLog,
)
from apps.tracker.tests.conftest import (
    LOG_DATE,
    NUTRITION_DAILY_URL,
    NUTRITION_WEEKLY_URL,
    TRACKER_LIST_URL,
    TRACKER_LOG_URL,
    TRACKER_RANGE_URL,
    _auth_get,
    _auth_post,
)

pytestmark = pytest.mark.django_db


def _recipe(cal: int = 400) -> Any:
    from apps.recipes.tests.factories import RecipeFactory

    return RecipeFactory(
        cached_nutrition={
            "calories": cal,
            "protein_g": 25.0,
            "carbs_g": 50.0,
            "fat_g": 8.0,
            "fiber_g": 4.0,
            "micronutrients": {
                "iron_mg": 2.0,
                "calcium_mg": 50.0,
                "vit_c_mg": 0.0,
                "potassium_mg": 200.0,
                "sodium_mg": 100.0,
                "magnesium_mg": 20.0,
                "zinc_mg": 1.0,
                "vit_a_iu": 0.0,
                "folate_ug": 10.0,
                "vit_b12_ug": 0.0,
            },
        },
        cached_calories_per_serving=cal,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# POST /tracker/log/
# ---------------------------------------------------------------------------


def test_log_requires_auth() -> None:
    from django.test import Client

    resp = Client().post(TRACKER_LOG_URL, data={}, content_type="application/json")
    assert resp.status_code == 401


def test_log_planned_status_returns_200(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    payload = {
        "log_date": LOG_DATE,
        "slot": "lunch",
        "status": STATUS_PLANNED,
        "planned_recipe_id": recipe.pk,
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["slot"] == "lunch"
    assert body["data"]["status"] == STATUS_PLANNED


def test_log_ate_planned_creates_summary(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe(400)
    payload = {
        "log_date": LOG_DATE,
        "slot": "dinner",
        "status": STATUS_ATE_PLANNED,
        "planned_recipe_id": recipe.pk,
        "servings_eaten": "1.00",
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 200
    assert DailyNutritionSummary.objects.filter(user=user, summary_date=date(2026, 5, 30)).exists()


def test_log_upsert_overwrites_existing(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()

    payload = {
        "log_date": LOG_DATE,
        "slot": "lunch",
        "status": STATUS_PLANNED,
        "planned_recipe_id": recipe.pk,
    }
    _auth_post(client, TRACKER_LOG_URL, payload)
    _auth_post(client, TRACKER_LOG_URL, payload)

    assert MealLog.objects.filter(user=user, log_date=date(2026, 5, 30), slot="lunch").count() == 1


def test_log_ate_custom_success(tracker_client: Any) -> None:
    client, user = tracker_client
    payload = {
        "log_date": LOG_DATE,
        "slot": "breakfast",
        "status": STATUS_ATE_CUSTOM,
        "custom_description": "Poha",
        "custom_calories": 280,
        "custom_protein_g": "8.0",
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["custom_calories"] == 280


def test_log_ate_custom_missing_calories_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    payload = {
        "log_date": LOG_DATE,
        "slot": "breakfast",
        "status": STATUS_ATE_CUSTOM,
        "custom_description": "Something",
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400
    assert resp.json()["status"] == "error"


def test_log_ate_custom_missing_description_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    payload = {
        "log_date": LOG_DATE,
        "slot": "breakfast",
        "status": STATUS_ATE_CUSTOM,
        "custom_calories": 300,
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400


def test_log_non_custom_with_custom_fields_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    payload = {
        "log_date": LOG_DATE,
        "slot": "lunch",
        "status": STATUS_ATE_PLANNED,
        "planned_recipe_id": recipe.pk,
        "custom_calories": 300,
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400


def test_log_invalid_servings_non_quarter_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    payload = {
        "log_date": LOG_DATE,
        "slot": "lunch",
        "status": STATUS_ATE_PLANNED,
        "planned_recipe_id": recipe.pk,
        "servings_eaten": "0.33",
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400


def test_log_invalid_servings_above_6_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    payload = {
        "log_date": LOG_DATE,
        "slot": "lunch",
        "status": STATUS_ATE_PLANNED,
        "planned_recipe_id": recipe.pk,
        "servings_eaten": "7.00",
    }
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400


def test_log_missing_slot_returns_400(tracker_client: Any) -> None:
    client, user = tracker_client
    payload = {"log_date": LOG_DATE, "status": STATUS_PLANNED}
    resp = _auth_post(client, TRACKER_LOG_URL, payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /tracker/?date=
# ---------------------------------------------------------------------------


def test_tracker_list_returns_logs_for_date(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    _auth_post(
        client,
        TRACKER_LOG_URL,
        {
            "log_date": LOG_DATE,
            "slot": "lunch",
            "status": STATUS_PLANNED,
            "planned_recipe_id": recipe.pk,
        },
    )
    resp = _auth_get(client, f"{TRACKER_LIST_URL}?date={LOG_DATE}")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["data"], list)
    assert len(body["data"]) == 1
    assert body["data"][0]["slot"] == "lunch"


def test_tracker_list_missing_date_returns_400(tracker_client: Any) -> None:
    client, _ = tracker_client
    resp = _auth_get(client, TRACKER_LIST_URL)
    assert resp.status_code == 400


def test_tracker_list_invalid_date_returns_400(tracker_client: Any) -> None:
    client, _ = tracker_client
    resp = _auth_get(client, f"{TRACKER_LIST_URL}?date=not-a-date")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /tracker/range?from=&to=
# ---------------------------------------------------------------------------


def test_tracker_range_returns_logs_in_range(tracker_client: Any) -> None:
    client, user = tracker_client
    recipe = _recipe()
    _auth_post(
        client,
        TRACKER_LOG_URL,
        {
            "log_date": LOG_DATE,
            "slot": "lunch",
            "status": STATUS_PLANNED,
            "planned_recipe_id": recipe.pk,
        },
    )
    resp = _auth_get(client, f"{TRACKER_RANGE_URL}?from={LOG_DATE}&to={LOG_DATE}")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def test_tracker_range_to_before_from_returns_400(tracker_client: Any) -> None:
    client, _ = tracker_client
    resp = _auth_get(client, f"{TRACKER_RANGE_URL}?from=2026-05-30&to=2026-05-28")
    assert resp.status_code == 400


def test_tracker_range_exceeds_90_days_returns_400(tracker_client: Any) -> None:
    client, _ = tracker_client
    resp = _auth_get(client, f"{TRACKER_RANGE_URL}?from=2026-01-01&to=2026-06-01")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /nutrition/daily?date=
# ---------------------------------------------------------------------------


def test_daily_endpoint_requires_auth() -> None:
    from django.test import Client

    resp = Client().get(f"{NUTRITION_DAILY_URL}?date={LOG_DATE}")
    assert resp.status_code == 401


def test_daily_endpoint_returns_targets_and_percentages(tracker_client_with_profile: Any) -> None:
    client, user, profile = tracker_client_with_profile
    recipe = _recipe(cal=500)
    _auth_post(
        client,
        TRACKER_LOG_URL,
        {
            "log_date": LOG_DATE,
            "slot": "lunch",
            "status": STATUS_ATE_PLANNED,
            "planned_recipe_id": recipe.pk,
        },
    )
    resp = _auth_get(client, f"{NUTRITION_DAILY_URL}?date={LOG_DATE}")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert "totals" in data
    assert "targets" in data
    assert "percentage_of_target" in data
    assert data["totals"]["calories"] == 500
    assert data["targets"]["calories"] == profile.target_calories
    assert data["percentage_of_target"]["calories"] > 0


def test_daily_endpoint_no_profile_returns_404(tracker_client: Any) -> None:
    client, user = tracker_client
    resp = _auth_get(client, f"{NUTRITION_DAILY_URL}?date={LOG_DATE}")
    assert resp.status_code == 404


def test_daily_endpoint_missing_date_returns_400(tracker_client_with_profile: Any) -> None:
    client, user, profile = tracker_client_with_profile
    resp = _auth_get(client, NUTRITION_DAILY_URL)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /nutrition/weekly?from=&to=
# ---------------------------------------------------------------------------


def test_weekly_endpoint_includes_averages(tracker_client_with_profile: Any) -> None:
    client, user, profile = tracker_client_with_profile
    recipe = _recipe(cal=400)

    # Log for two different days
    for log_date in ("2026-05-28", "2026-05-29"):
        _auth_post(
            client,
            TRACKER_LOG_URL,
            {
                "log_date": log_date,
                "slot": "lunch",
                "status": STATUS_ATE_PLANNED,
                "planned_recipe_id": recipe.pk,
            },
        )

    resp = _auth_get(client, f"{NUTRITION_WEEKLY_URL}?from=2026-05-28&to=2026-05-29")
    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert "days" in data
    assert "averages" in data
    assert data["averages"]["calories"] == 400
    assert len(data["days"]) == 2


def test_weekly_endpoint_no_profile_returns_404(tracker_client: Any) -> None:
    client, _ = tracker_client
    resp = _auth_get(client, f"{NUTRITION_WEEKLY_URL}?from=2026-05-28&to=2026-05-29")
    assert resp.status_code == 404
