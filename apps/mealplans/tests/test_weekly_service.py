"""Tests for GroceryList model and generate_weekly_plan service.

Session 1 — 13 tests:
  - 3 model tests (GroceryList)
  - 10 weekly generation service tests
"""

from datetime import date
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from freezegun import freeze_time

from apps.accounts.tests.factories import UserFactory
from apps.mealplans.models import GroceryList, MealPlan
from apps.mealplans.services.engine import NoSuitableRecipeError
from apps.mealplans.services.weekly_service import generate_weekly_plan
from apps.mealplans.tests.factories import MealPlanFactory
from core.exceptions import NotFoundError

# Frozen dates used across tests
FROZEN_MONDAY = "2026-05-25"  # Monday — weekday=0
FROZEN_WEDNESDAY = "2026-05-27"  # Wednesday — weekday=2
FROZEN_SUNDAY = "2026-05-31"  # Sunday — weekday=6

# ISO week for the frozen Monday
WEEK_START = date(2026, 5, 25)  # Monday 2026-05-25
WEEK_END = date(2026, 5, 31)  # Sunday 2026-05-31

# A prior-week date — makes a user a "returning user" for the frozen Monday week
PRIOR_WEEK_DATE = date(2026, 5, 18)  # Previous Monday


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_mock_generator(user: object, *, fail_on_call: int | None = None):
    """Return a side_effect for patched get_or_generate_plan.

    Creates a real MealPlan row in DB for each call. If fail_on_call is set,
    raises NoSuitableRecipeError on that call number (1-indexed).
    """
    call_count = {"n": 0}

    def _side_effect(u: object, plan_date: date) -> MealPlan:
        call_count["n"] += 1
        if fail_on_call is not None and call_count["n"] == fail_on_call:
            raise NoSuitableRecipeError(slot="lunch", plan_date=plan_date)
        return MealPlanFactory(user=u, plan_date=plan_date)  # type: ignore[arg-type]

    return _side_effect


PATCH_TARGET = "apps.mealplans.services.weekly_service.get_or_generate_plan"

# ===========================================================================
# Model tests
# ===========================================================================


@pytest.mark.django_db
def test_grocerylist_str_representation() -> None:
    user = UserFactory()
    gl = GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})
    s = str(gl)
    assert str(user.pk) in s
    assert str(WEEK_START) in s


@pytest.mark.django_db
def test_grocerylist_unique_together_user_week() -> None:
    user = UserFactory()
    GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})
    with pytest.raises(IntegrityError):
        GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})


@pytest.mark.django_db
def test_grocerylist_cascade_on_user_delete() -> None:
    user = UserFactory()
    GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={})
    assert GroceryList.objects.filter(user=user).count() == 1
    user.delete()
    assert GroceryList.objects.count() == 0


# ===========================================================================
# Weekly generation service tests
# ===========================================================================


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_creates_7_plans() -> None:
    """Returning user on Monday → generates Mon–Sun (7 plans)."""
    user = UserFactory()
    # Make user a "returning user" by giving them a plan from the prior week
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans = generate_weekly_plan(user)

    assert len(plans) == 7
    dates = [p.plan_date for p in plans]
    assert dates[0] == WEEK_START
    assert dates[-1] == WEEK_END


@freeze_time(FROZEN_WEDNESDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_first_time_midweek() -> None:
    """First-time user on Wednesday → generates Wed–Sun (5 plans)."""
    user = UserFactory()
    # No prior plans → first-time user

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans = generate_weekly_plan(user)

    assert len(plans) == 5
    assert plans[0].plan_date == date(2026, 5, 27)  # Wednesday
    assert plans[-1].plan_date == date(2026, 5, 31)  # Sunday


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_idempotent() -> None:
    """Calling generate_weekly_plan twice produces no duplicates."""
    user = UserFactory()
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans_first = generate_weekly_plan(user)

    # Second call: all 7 days already exist → mock should not be called
    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)) as mock_gen:
        plans_second = generate_weekly_plan(user)
        mock_gen.assert_not_called()

    assert len(plans_first) == 7
    assert len(plans_second) == 7
    assert MealPlan.objects.filter(user=user, plan_date__range=(WEEK_START, WEEK_END)).count() == 7


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_fills_gaps() -> None:
    """If 3 plans already exist in the week, function generates the 4 missing ones."""
    user = UserFactory()
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    # Pre-create Mon, Tue, Wed
    MealPlanFactory(user=user, plan_date=date(2026, 5, 25))
    MealPlanFactory(user=user, plan_date=date(2026, 5, 26))
    MealPlanFactory(user=user, plan_date=date(2026, 5, 27))

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)) as mock_gen:
        plans = generate_weekly_plan(user)

    assert len(plans) == 7
    assert mock_gen.call_count == 4  # Thu, Fri, Sat, Sun generated
    assert MealPlan.objects.filter(user=user, plan_date__range=(WEEK_START, WEEK_END)).count() == 7


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_atomic_rollback() -> None:
    """If day 5 fails, all 4 newly created plans for the week are rolled back."""
    user = UserFactory()
    # First-time user → generates Mon–Sun (7 days); fail on call 5 (Friday)

    with pytest.raises(NoSuitableRecipeError):
        with patch(PATCH_TARGET, side_effect=_make_mock_generator(user, fail_on_call=5)):
            generate_weekly_plan(user)

    # All 4 successfully created plans (Mon–Thu) should be rolled back
    assert MealPlan.objects.filter(user=user, plan_date__range=(WEEK_START, WEEK_END)).count() == 0


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_invalidates_grocery_cache() -> None:
    """An existing GroceryList for the week is deleted after generate_weekly_plan."""
    user = UserFactory()
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    # Pre-create a cached grocery list for this week
    GroceryList.objects.create(user=user, week_start_date=WEEK_START, items={"cached": True})
    assert GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        generate_weekly_plan(user)

    assert not GroceryList.objects.filter(user=user, week_start_date=WEEK_START).exists()


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_requires_profile() -> None:
    """User with no DietaryProfile → NotFoundError propagates from get_or_generate_plan."""
    user = UserFactory()
    # No profile, no prior plans → first-time user → real get_or_generate_plan is called
    # which calls get_profile → raises NotFoundError

    with pytest.raises(NotFoundError):
        generate_weekly_plan(user)

    assert MealPlan.objects.filter(user=user).count() == 0


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_returns_ordered_by_date() -> None:
    """Returned plans are sorted Monday → Sunday regardless of creation order."""
    user = UserFactory()
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans = generate_weekly_plan(user)

    plan_dates = [p.plan_date for p in plans]
    assert plan_dates == sorted(plan_dates)
    assert plan_dates[0] == WEEK_START
    assert plan_dates[-1] == WEEK_END


@freeze_time(FROZEN_MONDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_with_explicit_date() -> None:
    """Passing reference_date generates the ISO week containing that date."""
    user = UserFactory()
    MealPlanFactory(user=user, plan_date=PRIOR_WEEK_DATE)

    # Generate for the week of 2026-06-01 (Monday)
    future_monday = date(2026, 6, 1)
    future_sunday = date(2026, 6, 7)

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans = generate_weekly_plan(user, reference_date=future_monday)

    assert len(plans) == 7
    assert plans[0].plan_date == future_monday
    assert plans[-1].plan_date == future_sunday


@freeze_time(FROZEN_SUNDAY)
@pytest.mark.django_db
def test_generate_weekly_plan_first_time_sunday() -> None:
    """First-time user installing on Sunday → generates only 1 plan (Sunday)."""
    user = UserFactory()
    # No prior plans → first-time, today=Sunday → start=today, end=today+(6-6)=today

    with patch(PATCH_TARGET, side_effect=_make_mock_generator(user)):
        plans = generate_weekly_plan(user)

    assert len(plans) == 1
    assert plans[0].plan_date == date(2026, 5, 31)
