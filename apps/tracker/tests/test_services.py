"""Service-layer tests for tracker_service and nutrition_service."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from apps.tracker.models import (
    STATUS_ATE_CUSTOM,
    STATUS_ATE_PLANNED,
    STATUS_ATE_SUBSTITUTED,
    STATUS_PLANNED,
    STATUS_SKIPPED,
    DailyNutritionSummary,
    MealLog,
)
from apps.tracker.services.nutrition_service import recompute_daily_summary
from apps.tracker.services.tracker_service import upsert_meal_log
from core.exceptions import AppValidationError

pytestmark = pytest.mark.django_db

LOG_DATE = date(2026, 5, 30)


def _make_recipe(cal: int = 400) -> Any:
    from apps.recipes.tests.factories import RecipeFactory

    return RecipeFactory(
        cached_nutrition={
            "calories": cal,
            "protein_g": 30.0,
            "carbs_g": 50.0,
            "fat_g": 10.0,
            "fiber_g": 5.0,
            "micronutrients": {
                "iron_mg": 2.0,
                "calcium_mg": 50.0,
                "vit_c_mg": 10.0,
                "potassium_mg": 300.0,
                "sodium_mg": 200.0,
                "magnesium_mg": 25.0,
                "zinc_mg": 1.5,
                "vit_a_iu": 100.0,
                "folate_ug": 20.0,
                "vit_b12_ug": 0.0,
            },
        },
        cached_calories_per_serving=cal,
        is_active=True,
    )


def _make_user() -> Any:
    from apps.accounts.tests.factories import UserFactory

    return UserFactory()


# ---------------------------------------------------------------------------
# upsert_meal_log — idempotency
# ---------------------------------------------------------------------------


def test_log_upsert_idempotent() -> None:
    user = _make_user()
    recipe = _make_recipe()

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=recipe)
    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=recipe)

    assert MealLog.objects.filter(user=user, log_date=LOG_DATE, slot="lunch").count() == 1


# ---------------------------------------------------------------------------
# recompute_daily_summary — triggers
# ---------------------------------------------------------------------------


def test_log_creates_summary() -> None:
    user = _make_user()
    recipe = _make_recipe()

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=recipe)

    assert DailyNutritionSummary.objects.filter(user=user, summary_date=LOG_DATE).exists()


# ---------------------------------------------------------------------------
# Nutrition contribution per status
# ---------------------------------------------------------------------------


def test_ate_planned_uses_planned_recipe_for_macros() -> None:
    user = _make_user()
    recipe = _make_recipe(cal=400)

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=recipe)

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 400
    assert float(summary.protein_g) == pytest.approx(30.0, abs=0.1)


def test_substituted_uses_actual_recipe_for_macros() -> None:
    user = _make_user()
    planned = _make_recipe(cal=400)
    actual = _make_recipe(cal=500)

    upsert_meal_log(
        user,
        LOG_DATE,
        "lunch",
        STATUS_ATE_SUBSTITUTED,
        planned_recipe=planned,
        actual_recipe=actual,
    )

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 500


def test_skipped_contributes_zero_calories() -> None:
    user = _make_user()

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_SKIPPED)

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 0
    assert summary.meals_skipped == 1
    assert summary.meals_eaten == 0


def test_planned_contributes_zero_calories() -> None:
    user = _make_user()
    recipe = _make_recipe()

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_PLANNED, planned_recipe=recipe)

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 0
    assert summary.meals_eaten == 0


def test_ate_custom_contributes_custom_fields_to_summary() -> None:
    user = _make_user()

    upsert_meal_log(
        user,
        LOG_DATE,
        "lunch",
        STATUS_ATE_CUSTOM,
        custom_description="Homemade dal",
        custom_calories=350,
        custom_protein_g=Decimal("18.0"),
        custom_carbs_g=Decimal("40.0"),
        custom_fat_g=Decimal("8.0"),
    )

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 350
    assert float(summary.protein_g) == pytest.approx(18.0, abs=0.01)
    assert summary.meals_eaten == 1


def test_summary_includes_ate_custom_in_meals_eaten_count() -> None:
    user = _make_user()

    upsert_meal_log(
        user,
        LOG_DATE,
        "dinner",
        STATUS_ATE_CUSTOM,
        custom_description="Snack",
        custom_calories=200,
    )

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.meals_eaten == 1


# ---------------------------------------------------------------------------
# servings_eaten scaling
# ---------------------------------------------------------------------------


def test_servings_eaten_scales_macros() -> None:
    user = _make_user()
    recipe = _make_recipe(cal=400)

    upsert_meal_log(
        user,
        LOG_DATE,
        "lunch",
        STATUS_ATE_PLANNED,
        planned_recipe=recipe,
        servings_eaten=Decimal("2.00"),
    )

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 800


def test_servings_eaten_fractional() -> None:
    user = _make_user()
    recipe = _make_recipe(cal=400)

    upsert_meal_log(
        user,
        LOG_DATE,
        "lunch",
        STATUS_ATE_PLANNED,
        planned_recipe=recipe,
        servings_eaten=Decimal("0.50"),
    )

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 200


# ---------------------------------------------------------------------------
# servings_eaten validation
# ---------------------------------------------------------------------------


def test_servings_eaten_rejects_non_quarter_increment() -> None:
    user = _make_user()
    recipe = _make_recipe()

    with pytest.raises(AppValidationError, match="multiple of 0.25"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_PLANNED,
            planned_recipe=recipe,
            servings_eaten=Decimal("0.33"),
        )


def test_servings_eaten_rejects_above_6() -> None:
    user = _make_user()
    recipe = _make_recipe()

    with pytest.raises(AppValidationError, match="between"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_PLANNED,
            planned_recipe=recipe,
            servings_eaten=Decimal("7.00"),
        )


def test_servings_eaten_rejects_below_025() -> None:
    user = _make_user()
    recipe = _make_recipe()

    with pytest.raises(AppValidationError, match="between"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_PLANNED,
            planned_recipe=recipe,
            servings_eaten=Decimal("0.10"),
        )


# ---------------------------------------------------------------------------
# Custom field validation
# ---------------------------------------------------------------------------


def test_ate_custom_requires_description() -> None:
    user = _make_user()

    with pytest.raises(AppValidationError, match="custom_description"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_CUSTOM,
            custom_calories=300,
        )


def test_ate_custom_requires_calories() -> None:
    user = _make_user()

    with pytest.raises(AppValidationError, match="custom_calories"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_CUSTOM,
            custom_description="Some food",
        )


def test_non_custom_status_rejects_custom_fields() -> None:
    user = _make_user()
    recipe = _make_recipe()

    with pytest.raises(AppValidationError, match="ate_custom"):
        upsert_meal_log(
            user,
            LOG_DATE,
            "lunch",
            STATUS_ATE_PLANNED,
            planned_recipe=recipe,
            custom_calories=300,
        )


def test_ate_custom_with_optional_macros() -> None:
    user = _make_user()

    log = upsert_meal_log(
        user,
        LOG_DATE,
        "lunch",
        STATUS_ATE_CUSTOM,
        custom_description="Salad",
        custom_calories=200,
        custom_protein_g=Decimal("10.0"),
    )
    assert log.custom_protein_g == Decimal("10.0")


# ---------------------------------------------------------------------------
# ate_substituted validation
# ---------------------------------------------------------------------------


def test_ate_substituted_requires_actual_recipe() -> None:
    user = _make_user()

    with pytest.raises(AppValidationError, match="actual_recipe_id"):
        upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_SUBSTITUTED)


# ---------------------------------------------------------------------------
# recompute idempotency
# ---------------------------------------------------------------------------


def test_recompute_daily_summary_idempotent() -> None:
    user = _make_user()
    recipe = _make_recipe(cal=300)

    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=recipe)
    # Call again — must not throw or duplicate
    recompute_daily_summary(user, LOG_DATE)

    assert DailyNutritionSummary.objects.filter(user=user, summary_date=LOG_DATE).count() == 1
    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 300


def test_multi_slot_summary_aggregation() -> None:
    """Breakfast + lunch both eaten → calories sum correctly."""
    user = _make_user()
    r1 = _make_recipe(cal=400)
    r2 = _make_recipe(cal=600)

    upsert_meal_log(user, LOG_DATE, "breakfast", STATUS_ATE_PLANNED, planned_recipe=r1)
    upsert_meal_log(user, LOG_DATE, "lunch", STATUS_ATE_PLANNED, planned_recipe=r2)

    summary = DailyNutritionSummary.objects.get(user=user, summary_date=LOG_DATE)
    assert summary.calories == 1000
    assert summary.meals_eaten == 2
