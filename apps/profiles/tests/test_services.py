"""
test_services.py — Pure math tests (no DB) + service-layer tests (DB).

Section 1: Pure math (no @pytest.mark.django_db needed).
  21 tests covering BMR, TDEE, goal deltas, macro splits, fiber targets,
  age computation, and year-boundary behaviour.

Section 2: Service tests (DB).
  13 tests covering budget derivation, Jain rule, dislikes normalisation,
  disclaimer gate, vocab validation, upsert behaviour, and get_profile errors.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from core.error_codes import VALIDATION_ERROR
from core.exceptions import AppValidationError, NotFoundError
from core.utils.nutrition_math import (
    compute_age,
    compute_targets,
)

# ---------------------------------------------------------------------------
# Helpers: build a minimal mock profile for math-only tests (no DB)
# ---------------------------------------------------------------------------


def _mock_profile(
    *,
    weight_kg: float = 80.0,
    height_cm: int = 180,
    sex: str = "male",
    dob: date = date(1994, 6, 15),
    activity_level: str = "moderate",
    goal: str = "maintain",
) -> MagicMock:
    """Return a MagicMock that satisfies compute_targets()'s attribute access."""
    p = MagicMock()
    p.weight_kg = Decimal(str(weight_kg))
    p.height_cm = height_cm
    p.sex = sex
    p.date_of_birth = dob
    p.activity_level = activity_level
    p.goal = goal
    return p


# ---------------------------------------------------------------------------
# Section 1 — Pure math tests (no DB)
# ---------------------------------------------------------------------------


class TestBMR:
    """
    Known-value tests for Mifflin-St Jeor BMR.
    Formula: 10*W + 6.25*H - 5*A + sex_offset
    """

    def test_bmr_male_known_value(self) -> None:
        """Male 30yo 80kg 180cm: base = 10*80 + 6.25*180 - 5*30 = 800+1125-150 = 1775; +5 = 1780."""
        p = _mock_profile(weight_kg=80, height_cm=180, sex="male", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):  # age = 30 exactly
            compute_targets(p)
        assert p.target_calories is not None
        # TDEE = 1780 * 1.55 (moderate) = 2759 → maintain (delta=0) → 2759
        assert p.target_calories == 2759

    def test_bmr_female_known_value(self) -> None:
        """Female 25yo 60kg 165cm: bmr_base=1506.25; female offset -161 → bmr=1345.25."""
        p = _mock_profile(
            weight_kg=60,
            height_cm=165,
            sex="female",
            dob=date(1999, 6, 15),
            goal="maintain",
        )
        with freeze_time("2024-06-15"):  # age = 25
            compute_targets(p)
        # TDEE = 1345.25 * 1.55 = 2085.1375 → round → 2085
        assert p.target_calories == 2085

    def test_bmr_other_uses_average(self) -> None:
        """sex='other' uses (bmr_base - 78); result matches midpoint of male/female."""
        p_other = _mock_profile(
            weight_kg=80, height_cm=180, sex="other", dob=date(1994, 6, 15), goal="maintain"
        )
        p_male = _mock_profile(
            weight_kg=80, height_cm=180, sex="male", dob=date(1994, 6, 15), goal="maintain"
        )
        p_female = _mock_profile(
            weight_kg=80, height_cm=180, sex="female", dob=date(1994, 6, 15), goal="maintain"
        )
        with freeze_time("2024-06-15"):
            compute_targets(p_other)
            compute_targets(p_male)
            compute_targets(p_female)
        # other should equal (male + female) / 2 rounded
        expected = round((p_male.target_calories + p_female.target_calories) / 2)
        assert p_other.target_calories == expected

    def test_bmr_prefer_not_to_say_uses_average(self) -> None:
        """prefer_not_to_say uses the same -78 offset as 'other'."""
        p_other = _mock_profile(sex="other", dob=date(1994, 6, 15))
        p_pnts = _mock_profile(sex="prefer_not_to_say", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p_other)
            compute_targets(p_pnts)
        assert p_pnts.target_calories == p_other.target_calories


class TestTDEE:
    """TDEE = BMR × activity multiplier."""

    def _calories_for_activity(self, activity: str) -> int:
        """Helper: compute target_calories for male 30yo 80kg 180cm with given activity."""
        p = _mock_profile(activity_level=activity, goal="maintain", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        return p.target_calories  # type: ignore[return-value]

    def test_tdee_sedentary(self) -> None:
        calories = self._calories_for_activity("sedentary")
        # BMR=1780, TDEE=1780*1.2=2136
        assert calories == 2136

    def test_tdee_light(self) -> None:
        calories = self._calories_for_activity("light")
        # BMR=1780, TDEE=1780*1.375=2447.5→2448
        assert calories == 2448

    def test_tdee_moderate(self) -> None:
        calories = self._calories_for_activity("moderate")
        # BMR=1780, TDEE=1780*1.55=2759
        assert calories == 2759

    def test_tdee_very(self) -> None:
        calories = self._calories_for_activity("very")
        # BMR=1780, TDEE=1780*1.725=3070.5 → round() with banker's rounding → 3070
        assert calories == 3070

    def test_tdee_athlete(self) -> None:
        calories = self._calories_for_activity("athlete")
        # BMR=1780, TDEE=1780*1.9=3382
        assert calories == 3382


class TestGoalDeltas:
    def _calories_for_goal(self, goal: str) -> int:
        p = _mock_profile(goal=goal, dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        return p.target_calories  # type: ignore[return-value]

    def test_target_calories_maintain(self) -> None:
        # TDEE moderate = 2759, delta=0 → 2759
        assert self._calories_for_goal("maintain") == 2759

    def test_target_calories_lose_weight(self) -> None:
        # 2759 - 500 = 2259
        assert self._calories_for_goal("lose_weight") == 2259

    def test_target_calories_gain_muscle(self) -> None:
        # 2759 + 300 = 3059
        assert self._calories_for_goal("gain_muscle") == 3059

    def test_target_calories_gain_weight_healthy(self) -> None:
        # 2759 + 500 = 3259
        assert self._calories_for_goal("gain_weight_healthy") == 3259

    def test_target_calories_eat_healthier(self) -> None:
        # delta=0 → same as maintain = 2759
        assert self._calories_for_goal("eat_healthier") == self._calories_for_goal("maintain")

    def test_target_calories_floors_at_1200(self) -> None:
        """Very small person with lose_weight should floor at 1200."""
        p = _mock_profile(
            weight_kg=30.0,
            height_cm=100,
            sex="female",
            dob=date(2011, 6, 15),  # age=13, minimum
            activity_level="sedentary",
            goal="lose_weight",
        )
        with freeze_time("2024-06-15"):
            compute_targets(p)
        assert p.target_calories == 1200


class TestMacroSplits:
    def test_macro_split_lose_weight(self) -> None:
        """lose_weight: 35% protein, 40% carbs, 25% fat."""
        p = _mock_profile(goal="lose_weight", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        calories = p.target_calories  # 2259
        assert float(p.target_protein_g) == round(calories * 0.35 / 4, 1)
        assert float(p.target_carbs_g) == round(calories * 0.40 / 4, 1)
        assert float(p.target_fat_g) == round(calories * 0.25 / 9, 1)

    def test_macro_split_eat_healthier(self) -> None:
        """eat_healthier: 25% protein, 50% carbs, 25% fat (same splits as maintain)."""
        p = _mock_profile(goal="eat_healthier", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        calories = p.target_calories  # 2759
        assert float(p.target_protein_g) == round(calories * 0.25 / 4, 1)
        assert float(p.target_carbs_g) == round(calories * 0.50 / 4, 1)
        assert float(p.target_fat_g) == round(calories * 0.25 / 9, 1)


class TestFiberTargets:
    def test_fiber_target_default_14g(self) -> None:
        """maintain → 14g/1000 kcal."""
        p = _mock_profile(goal="maintain", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        calories = p.target_calories  # 2759
        expected = round(calories / 1000 * 14.0, 1)
        assert float(p.target_fiber_g) == expected

    def test_fiber_target_eat_healthier_uses_18g(self) -> None:
        """eat_healthier → elevated 18g/1000 kcal."""
        p = _mock_profile(goal="eat_healthier", dob=date(1994, 6, 15))
        with freeze_time("2024-06-15"):
            compute_targets(p)
        calories = p.target_calories  # 2759
        expected = round(calories / 1000 * 18.0, 1)
        assert float(p.target_fiber_g) == expected
        # Sanity: must differ from maintain's 14g rate
        assert float(p.target_fiber_g) > round(calories / 1000 * 14.0, 1)


class TestComputeAge:
    def test_age_computed_from_dob_not_stored(self) -> None:
        dob = date(1994, 6, 15)
        today = date(2024, 6, 15)
        assert compute_age(dob, today=today) == 30

    def test_age_year_boundary(self) -> None:
        """DOB = today - exactly N years → age = N (not N-1)."""
        dob = date(1994, 6, 15)
        # One day before birthday: still 29
        assert compute_age(dob, today=date(2024, 6, 14)) == 29
        # Exactly on birthday: 30
        assert compute_age(dob, today=date(2024, 6, 15)) == 30

    @freeze_time("2024-06-15")
    def test_age_with_freezegun(self) -> None:
        """compute_age() with no today argument uses frozen date.today()."""
        dob = date(1994, 6, 15)
        assert compute_age(dob) == 30


# ---------------------------------------------------------------------------
# Section 2 — Service tests (DB required)
# ---------------------------------------------------------------------------

from apps.accounts.tests.factories import UserFactory  # noqa: E402
from apps.profiles.services.profiles import get_profile, upsert_profile  # noqa: E402

ONBOARDING_BASE: dict = {
    "date_of_birth": date(1994, 6, 15),
    "sex": "male",
    "height_cm": 180,
    "weight_kg": Decimal("80.0"),
    "activity_level": "moderate",
    "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": [],
    "spice_tolerance": "medium",
    "diet_pattern": "vegetarian",
    "no_onion_garlic": False,
    "allergies": [],
    "dislikes": [],
    "daily_food_budget_inr": Decimal("150.00"),
    "weekly_food_budget_inr": None,
    "household_size": 1,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "beginner",
    "disclaimer_acknowledged": True,
}


def _data(**overrides: object) -> dict:
    """Return a copy of ONBOARDING_BASE with overrides applied."""
    return {**ONBOARDING_BASE, **overrides}


@pytest.mark.django_db
class TestBudgetDerivation:
    def test_budget_derivation_weekly_from_daily(self) -> None:
        """daily=100 given, weekly=None → weekly derived as 700."""
        user = UserFactory()
        profile, _ = upsert_profile(
            user,
            _data(
                daily_food_budget_inr=Decimal("100.00"),
                weekly_food_budget_inr=None,
            ),
        )
        assert float(profile.weekly_food_budget_inr) == 700.0

    def test_budget_derivation_daily_from_weekly(self) -> None:
        """weekly=700 given, daily=None → daily derived as 100."""
        user = UserFactory()
        profile, _ = upsert_profile(
            user,
            _data(
                daily_food_budget_inr=None,
                weekly_food_budget_inr=Decimal("700.00"),
            ),
        )
        assert float(profile.daily_food_budget_inr) == pytest.approx(100.00, rel=1e-2)

    def test_budget_rejects_inconsistent_pair(self) -> None:
        """daily=100, weekly=800 → inconsistency (>5%) → VALIDATION_ERROR."""
        user = UserFactory()
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(
                user,
                _data(
                    daily_food_budget_inr=Decimal("100.00"),
                    weekly_food_budget_inr=Decimal("800.00"),
                ),
            )
        assert exc_info.value.code == VALIDATION_ERROR

    def test_budget_requires_at_least_one_field(self) -> None:
        """Neither daily nor weekly provided → VALIDATION_ERROR."""
        user = UserFactory()
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(
                user,
                _data(
                    daily_food_budget_inr=None,
                    weekly_food_budget_inr=None,
                ),
            )
        assert exc_info.value.code == VALIDATION_ERROR


@pytest.mark.django_db
class TestJainRule:
    def test_jain_implies_no_onion_garlic_true(self) -> None:
        """diet_pattern=jain forces no_onion_garlic=True regardless of client input."""
        user = UserFactory()
        profile, _ = upsert_profile(
            user,
            _data(
                diet_pattern="jain",
                no_onion_garlic=False,  # client says False — should be overridden
            ),
        )
        assert profile.no_onion_garlic is True


@pytest.mark.django_db
class TestDislikes:
    def test_dislikes_lowercases_and_trims(self) -> None:
        """' Paneer ', ' ONION ' → ['paneer', 'onion']."""
        user = UserFactory()
        profile, _ = upsert_profile(user, _data(dislikes=[" Paneer ", " ONION "]))
        assert profile.dislikes == ["paneer", "onion"]


@pytest.mark.django_db
class TestDisclaimerGate:
    def test_disclaimer_required_to_submit(self) -> None:
        """disclaimer_acknowledged=False → VALIDATION_ERROR."""
        user = UserFactory()
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(user, _data(disclaimer_acknowledged=False))
        assert exc_info.value.code == VALIDATION_ERROR

    def test_disclaimer_missing_raises_validation_error(self) -> None:
        """disclaimer_acknowledged not provided at all → VALIDATION_ERROR."""
        user = UserFactory()
        data = _data()
        del data["disclaimer_acknowledged"]
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(user, data)
        assert exc_info.value.code == VALIDATION_ERROR


@pytest.mark.django_db
class TestVocabValidation:
    def test_cuisine_preferences_validates_controlled_vocab(self) -> None:
        """Unknown secondary_cuisine_preferences entry → VALIDATION_ERROR."""
        user = UserFactory()
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(user, _data(secondary_cuisine_preferences=["unknown_cuisine"]))
        assert exc_info.value.code == VALIDATION_ERROR

    def test_allergies_controlled_vocab(self) -> None:
        """Unknown allergy entry → VALIDATION_ERROR."""
        user = UserFactory()
        with pytest.raises(AppValidationError) as exc_info:
            upsert_profile(user, _data(allergies=["unknown_allergen"]))
        assert exc_info.value.code == VALIDATION_ERROR


@pytest.mark.django_db
class TestUpsertBehaviour:
    def test_upsert_creates_profile(self) -> None:
        """upsert_profile creates a profile with computed non-null targets."""
        user = UserFactory()
        profile, _ = upsert_profile(user, _data())
        assert profile.pk is not None
        assert profile.target_calories is not None
        assert profile.target_calories > 0

    def test_upsert_is_idempotent(self) -> None:
        """Calling upsert_profile twice → same profile row (count stays 1)."""
        from apps.profiles.models import DietaryProfile

        user = UserFactory()
        upsert_profile(user, _data())
        upsert_profile(user, _data())
        assert DietaryProfile.objects.filter(user=user).count() == 1

    def test_upsert_recomputes_on_update(self) -> None:
        """Change weight via second upsert → target_calories changes."""
        user = UserFactory()
        p1, _ = upsert_profile(user, _data(weight_kg=Decimal("80.0")))
        cal1 = p1.target_calories

        p2, _ = upsert_profile(user, _data(weight_kg=Decimal("120.0")))
        assert p2.target_calories != cal1


@pytest.mark.django_db
class TestGetProfile:
    def test_get_profile_raises_not_found(self) -> None:
        """No profile → NotFoundError with PROFILE_NOT_FOUND code."""
        from core.error_codes import PROFILE_NOT_FOUND

        user = UserFactory()
        with pytest.raises(NotFoundError) as exc_info:
            get_profile(user)
        assert exc_info.value.code == PROFILE_NOT_FOUND
