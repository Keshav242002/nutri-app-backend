"""Model-level tests for MealLog and DailyNutritionSummary."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.accounts.tests.factories import UserFactory
from apps.tracker.models import (
    STATUS_ATE_PLANNED,
    STATUS_PLANNED,
    DailyNutritionSummary,
    MealLog,
)
from apps.tracker.tests.factories import DailyNutritionSummaryFactory, MealLogFactory

pytestmark = pytest.mark.django_db


def test_meallog_str() -> None:
    log = MealLogFactory(slot="lunch", status=STATUS_PLANNED)
    assert "lunch" in str(log)
    assert "planned" in str(log)


def test_meallog_unique_together_enforced() -> None:
    log = MealLogFactory(slot="breakfast")
    duplicate = MealLog(
        user=log.user,
        log_date=log.log_date,
        slot="breakfast",
        status=STATUS_ATE_PLANNED,
    )
    with pytest.raises(IntegrityError):
        duplicate.save()


def test_daily_nutrition_summary_str() -> None:
    summary = DailyNutritionSummaryFactory(calories=500)
    assert "500" in str(summary)


def test_meallog_default_servings() -> None:
    user = UserFactory()
    ml = MealLog.objects.create(user=user, log_date="2026-05-30", slot="breakfast")
    ml.refresh_from_db()
    assert ml.servings_eaten == Decimal("1")


def test_meallog_default_notes_empty() -> None:
    user = UserFactory()
    ml = MealLog.objects.create(user=user, log_date="2026-05-30", slot="dinner")
    assert ml.notes == ""


def test_daily_summary_unique_together_enforced() -> None:
    s = DailyNutritionSummaryFactory()
    duplicate = DailyNutritionSummary(
        user=s.user,
        summary_date=s.summary_date,
    )
    with pytest.raises(IntegrityError):
        duplicate.save()
