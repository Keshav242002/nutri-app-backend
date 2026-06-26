"""Engine + plan_service tests — Sessions 1 and 2.

Session 1: hard filters (12), budget (5), scoring (10), diet hierarchy (4).
Session 2: generate_week (3), plan_service (8), thin_cell_inventory (1).
All engine tests use random.Random(0) for determinism.
"""

import random
from datetime import date
from decimal import Decimal

import pytest

from apps.mealplans.services.engine import (
    SLOT_CALORIE_WINDOW,
    NoSuitableRecipeError,
    _compute_macro_match,
    generate_week,
    select_recipe,
    select_recipe_with_fallback,
)
from apps.profiles.tests.factories import DietaryProfileFactory
from apps.recipes.tests.factories import RecipeFactory

PLAN_DATE = date(2026, 5, 26)


def _rng() -> random.Random:
    """Fresh seeded RNG per test for independence."""
    return random.Random(0)


def _profile(**kwargs):  # type: ignore[no-untyped-def]
    """Build a DietaryProfile with sensible engine-friendly defaults."""
    defaults = dict(
        diet_pattern="vegetarian",
        max_prep_time_min=60,
        allergies=[],
        daily_food_budget_inr=None,
        cooking_frequency="daily",
        goal="maintain",
        primary_cuisine_region="north_indian",
        secondary_cuisine_preferences=[],
    )
    defaults.update(kwargs)
    return DietaryProfileFactory(**defaults)


def _recipe(**kwargs):  # type: ignore[no-untyped-def]
    """Build an active Recipe with sensible defaults.

    Default calories=1100 fits the lunch window ([825, 1375]) for the standard
    DietaryProfileFactory profile (~2751 kcal/day). Tests using a different
    slot must override cached_calories_per_serving explicitly.
    """
    defaults = dict(
        is_active=True,
        meal_type="lunch",
        prep_time_min=20,
        cook_time_min=20,
        servings=2,
        diet_tags=["vegetarian"],
        allergen_tags=[],
        cached_calories_per_serving=1100,
        cached_nutrition={
            "calories": 1100,
            "protein_g": 40.0,
            "carbs_g": 140.0,
            "fat_g": 30.0,
            "fiber_g": 5.0,
        },
        cuisine="north_indian",
        cost_known=False,
        cached_cost_inr=None,
    )
    defaults.update(kwargs)
    return RecipeFactory(**defaults)


# ---------------------------------------------------------------------------
# Hard filter tests (12)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEngineHardFilters:
    def test_engine_filters_by_meal_type(self) -> None:
        profile = _profile()
        # Breakfast window for standard profile (~2751 kcal): int(2751*0.25)=687
        # window = [int(687*0.75), int(687*1.25)] = [515, 858]
        breakfast = _recipe(
            meal_type="breakfast", slug="bf-meal-type", cached_calories_per_serving=700
        )
        _recipe(meal_type="dinner", slug="din-meal-type", cached_calories_per_serving=700)
        result = select_recipe(profile, "breakfast", PLAN_DATE, rng=_rng())
        assert result == breakfast

    def test_engine_filters_by_is_active(self) -> None:
        profile = _profile()
        active = _recipe(slug="active-recipe-1")
        _recipe(slug="inactive-recipe-1", is_active=False)
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == active

    def test_engine_respects_max_prep_time(self) -> None:
        profile = _profile(max_prep_time_min=15)
        fast = _recipe(slug="fast-recipe", prep_time_min=10)
        _recipe(slug="slow-recipe", prep_time_min=30)
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == fast

    def test_engine_excludes_allergens(self) -> None:
        profile = _profile(allergies=["dairy"])
        safe = _recipe(slug="no-dairy", allergen_tags=[])
        _recipe(slug="has-dairy", allergen_tags=["dairy"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == safe

    def test_engine_respects_diet_pattern_vegetarian(self) -> None:
        profile = _profile(diet_pattern="vegetarian")
        veg = _recipe(slug="veg-only", diet_tags=["vegetarian"])
        _recipe(slug="nonveg-only", diet_tags=[])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == veg

    def test_engine_respects_diet_pattern_vegan(self) -> None:
        profile = _profile(diet_pattern="vegan")
        vegan = _recipe(slug="vegan-only", diet_tags=["vegan"])
        _recipe(slug="veg-not-vegan", diet_tags=["vegetarian"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == vegan

    def test_engine_respects_diet_pattern_eggetarian(self) -> None:
        profile = _profile(diet_pattern="eggetarian")
        egg = _recipe(slug="egg-recipe", diet_tags=["eggetarian"])
        veg = _recipe(slug="veg-ok-for-egg", diet_tags=["vegetarian"])
        _recipe(slug="non-veg-excl", diet_tags=[])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {egg, veg}

    def test_engine_respects_diet_pattern_nonveg(self) -> None:
        profile = _profile(diet_pattern="non_vegetarian")
        r1 = _recipe(slug="nv-recipe1", diet_tags=[])
        r2 = _recipe(slug="nv-recipe2", diet_tags=["vegetarian"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {r1, r2}

    def test_engine_respects_calorie_window(self) -> None:
        profile = _profile()
        target_calories = profile.target_calories or 2000
        slot_target = int(target_calories * 0.40)  # lunch ratio
        low_ratio, high_ratio = SLOT_CALORIE_WINDOW["lunch"]
        out_low_cal = int(slot_target * low_ratio) - 10
        out_high_cal = int(slot_target * high_ratio) + 10

        in_window = _recipe(slug="in-window", cached_calories_per_serving=slot_target)
        _recipe(slug="too-low-cal", cached_calories_per_serving=out_low_cal)
        _recipe(slug="too-high-cal", cached_calories_per_serving=out_high_cal)

        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == in_window

    def test_engine_calorie_window_boundaries(self) -> None:
        profile = _profile()
        target_calories = profile.target_calories or 2000
        slot_target = int(target_calories * 0.40)
        low_ratio, high_ratio = SLOT_CALORIE_WINDOW["lunch"]
        low_boundary = int(slot_target * low_ratio)
        high_boundary = int(slot_target * high_ratio)

        at_low = _recipe(slug="at-low-boundary", cached_calories_per_serving=low_boundary)
        at_high = _recipe(slug="at-high-boundary", cached_calories_per_serving=high_boundary)
        _recipe(slug="one-below-low", cached_calories_per_serving=max(0, low_boundary - 1))

        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {at_low, at_high}

    def test_engine_excludes_specified_recipe_ids(self) -> None:
        profile = _profile()
        r1 = _recipe(slug="exclude-me")
        r2 = _recipe(slug="keep-me")
        result = select_recipe(profile, "lunch", PLAN_DATE, exclude_recipe_ids=[r1.id], rng=_rng())
        assert result == r2

    def test_engine_raises_when_no_match(self) -> None:
        # Profile allergic to dairy; only recipe has dairy → empty pool
        profile = _profile(allergies=["dairy"])
        _recipe(slug="dairy-recipe", allergen_tags=["dairy"])
        with pytest.raises(NoSuitableRecipeError):
            select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())

    def test_breakfast_calorie_window_is_50_to_150_percent(self) -> None:
        low_ratio, high_ratio = SLOT_CALORIE_WINDOW["breakfast"]
        assert low_ratio == 0.50
        assert high_ratio == 1.50

    def test_lunch_calorie_window_is_75_to_125_percent(self) -> None:
        low_ratio, high_ratio = SLOT_CALORIE_WINDOW["lunch"]
        assert low_ratio == 0.75
        assert high_ratio == 1.25

    def test_dinner_calorie_window_is_75_to_125_percent(self) -> None:
        low_ratio, high_ratio = SLOT_CALORIE_WINDOW["dinner"]
        assert low_ratio == 0.75
        assert high_ratio == 1.25


# ---------------------------------------------------------------------------
# Budget tests (5)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEngineBudget:
    def test_engine_respects_budget_window(self) -> None:
        # slot_budget = 200 * 0.40 = 80; strict = 80 * 1.15 = 92
        # cheap: 150/2 = 75 ≤ 92 → passes strict
        # expensive: 200/2 = 100 > 92, ≤ 80*1.40=112 → fails strict, passes relaxed
        # strict pool is non-empty → use strict → only cheap included
        profile = _profile(daily_food_budget_inr=Decimal("200.00"))
        cheap = _recipe(
            slug="cheap-recipe", cached_cost_inr=Decimal("150.00"), cost_known=True, servings=2
        )
        _recipe(
            slug="expensive-recipe", cached_cost_inr=Decimal("200.00"), cost_known=True, servings=2
        )
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == cheap

    def test_engine_budget_grace_factor_1_15(self) -> None:
        # slot_budget = 100 * 0.40 = 40; strict limit = 40 * 1.15 = 46
        # recipe: cost_per_serving = 90/2 = 45 ≤ 46 → within grace → passes
        profile = _profile(daily_food_budget_inr=Decimal("100.00"))
        within_grace = _recipe(
            slug="within-grace", cached_cost_inr=Decimal("90.00"), cost_known=True, servings=2
        )
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == within_grace

    def test_engine_relaxes_budget_when_pool_empty(self) -> None:
        # slot_budget = 100 * 0.40 = 40; strict = 46; relaxed = 56
        # cost_per_serving = 100/2 = 50 → fails strict (>46), passes relaxed (≤56)
        profile = _profile(daily_food_budget_inr=Decimal("100.00"))
        relaxed_ok = _recipe(
            slug="relaxed-ok", cached_cost_inr=Decimal("100.00"), cost_known=True, servings=2
        )
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == relaxed_ok

    def test_engine_budget_includes_cost_unknown_in_fallback(self) -> None:
        # Budget so tight no known-cost recipe passes strict → fallback includes cost_known=False
        profile = _profile(daily_food_budget_inr=Decimal("50.00"))
        # strict limit = 50 * 0.40 * 1.15 = 23; no known-cost recipe in range
        unknown_cost = _recipe(slug="unknown-cost", cached_cost_inr=None, cost_known=False)
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == unknown_cost

    def test_engine_no_budget_filter_when_budget_not_set(self) -> None:
        profile = _profile(daily_food_budget_inr=None)
        expensive = _recipe(
            slug="expensive-no-filter",
            cached_cost_inr=Decimal("9999.00"),
            cost_known=True,
            servings=1,
        )
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == expensive


# ---------------------------------------------------------------------------
# Scoring tests (10)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEngineScoring:
    def test_engine_cuisine_boost_applied(self) -> None:
        # north_indian profile; matching recipe gets +30, non-matching gets 0
        profile = _profile(primary_cuisine_region="north_indian")
        matching = _recipe(slug="north-ind-recipe", cuisine="north_indian")
        _recipe(slug="south-ind-recipe", cuisine="south_indian")
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == matching

    def test_engine_macro_match_score_perfect(self) -> None:
        profile = _profile()
        slot_macros = {
            "protein_g": float(profile.target_protein_g or 60) * 0.40,
            "carbs_g": float(profile.target_carbs_g or 220) * 0.40,
            "fat_g": float(profile.target_fat_g or 55) * 0.40,
        }
        recipe = _recipe(
            slug="perfect-macro",
            cached_nutrition={
                "calories": 1100,
                "protein_g": slot_macros["protein_g"],
                "carbs_g": slot_macros["carbs_g"],
                "fat_g": slot_macros["fat_g"],
                "fiber_g": 3.0,
            },
        )
        score = _compute_macro_match(recipe, slot_macros)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_engine_macro_match_score_poor(self) -> None:
        slot_macros = {"protein_g": 50.0, "carbs_g": 80.0, "fat_g": 20.0}
        recipe = _recipe(
            slug="poor-macro",
            cached_nutrition={
                "calories": 1100,
                "protein_g": 1.0,
                "carbs_g": 1.0,
                "fat_g": 1.0,
                "fiber_g": 0.0,
            },
        )
        score = _compute_macro_match(recipe, slot_macros)
        assert score < 0.2

    def test_engine_variety_penalty_for_recent_recipes(self) -> None:
        from apps.mealplans.tests.factories import MealPlanFactory

        profile = _profile()
        slot_target = int((profile.target_calories or 2000) * 0.40)

        recent = _recipe(slug="recent-recipe", cached_calories_per_serving=slot_target)
        fresh = _recipe(slug="fresh-recipe", cached_calories_per_serving=slot_target)

        # Mark 'recent' as used in yesterday's lunch slot (-50 penalty)
        yesterday = date(PLAN_DATE.year, PLAN_DATE.month, PLAN_DATE.day - 1)
        MealPlanFactory(user=profile.user, plan_date=yesterday, lunch=recent)

        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == fresh

    def test_engine_protein_variety_penalty_nonveg(self) -> None:
        from apps.mealplans.tests.factories import MealPlanFactory

        profile = _profile(diet_pattern="non_vegetarian")
        slot_target = int((profile.target_calories or 2000) * 0.40)

        chicken_prev = _recipe(
            slug="chicken-prev",
            diet_tags=[],
            protein_source="chicken",
            cached_calories_per_serving=slot_target,
        )
        _recipe(
            slug="chicken-today",
            diet_tags=[],
            protein_source="chicken",
            cached_calories_per_serving=slot_target,
        )
        mutton_today = _recipe(
            slug="mutton-today",
            diet_tags=[],
            protein_source="mutton",
            cached_calories_per_serving=slot_target,
        )

        yesterday = date(PLAN_DATE.year, PLAN_DATE.month, PLAN_DATE.day - 1)
        MealPlanFactory(user=profile.user, plan_date=yesterday, lunch=chicken_prev)

        # chicken recipes penalized -25; mutton_today should win
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == mutton_today

    def test_engine_cooking_frequency_daily_prefers_quick(self) -> None:
        profile = _profile(cooking_frequency="daily")
        slot_target = int((profile.target_calories or 2000) * 0.40)

        quick = _recipe(
            slug="quick-recipe",
            prep_time_min=10,
            cook_time_min=15,
            cached_calories_per_serving=slot_target,
        )
        _recipe(
            slug="slow-recipe2",
            prep_time_min=20,
            cook_time_min=40,
            cached_calories_per_serving=slot_target,
        )
        # quick: 10+15=25 ≤ 30 → +15; slow: 60 → no boost
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == quick

    def test_engine_cooking_frequency_rarely_prefers_batch(self) -> None:
        profile = _profile(cooking_frequency="rarely", max_prep_time_min=60)
        slot_target = int((profile.target_calories or 2000) * 0.40)

        batch = _recipe(
            slug="batch-recipe",
            servings=4,
            prep_time_min=30,
            cook_time_min=20,
            cached_calories_per_serving=slot_target,
        )
        _recipe(
            slug="small-recipe",
            servings=2,
            prep_time_min=30,
            cook_time_min=20,
            cached_calories_per_serving=slot_target,
        )
        # batch: servings=4 ≥ 4 → +10; small: no boost
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == batch

    def test_engine_eat_healthier_fiber_boost(self) -> None:
        profile = _profile(goal="eat_healthier")
        slot_target = int((profile.target_calories or 2000) * 0.40)

        high_fiber = _recipe(
            slug="high-fiber",
            cached_calories_per_serving=slot_target,
            cached_nutrition={
                "calories": slot_target,
                "protein_g": 20.0,
                "carbs_g": 60.0,
                "fat_g": 10.0,
                "fiber_g": 8.0,
            },
        )
        _recipe(
            slug="low-fiber",
            cached_calories_per_serving=slot_target,
            cached_nutrition={
                "calories": slot_target,
                "protein_g": 20.0,
                "carbs_g": 60.0,
                "fat_g": 10.0,
                "fiber_g": 1.0,
            },
        )
        # high_fiber: fiber=8 ≥ 5 → +15; low_fiber: no boost
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == high_fiber

    def test_engine_budget_scoring_prefers_cheaper(self) -> None:
        # Both pass strict filter; cheaper scores better (less overshoot penalty)
        # slot_budget = 300 * 0.40 = 120; strict = 138
        # cheap: 100/2=50 ≤ 138 → pass; less_cheap: 260/2=130 ≤ 138 → pass
        # budget score: cheap: +25-0=+25; less_cheap: +25-10=+15
        profile = _profile(daily_food_budget_inr=Decimal("300.00"))
        slot_target = int((profile.target_calories or 2000) * 0.40)

        cheap = _recipe(
            slug="cheap-budget",
            cached_cost_inr=Decimal("100.00"),
            cost_known=True,
            servings=2,
            cached_calories_per_serving=slot_target,
        )
        _recipe(
            slug="less-cheap-budget",
            cached_cost_inr=Decimal("260.00"),
            cost_known=True,
            servings=2,
            cached_calories_per_serving=slot_target,
        )
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == cheap

    def test_engine_deterministic_with_seed(self) -> None:
        profile = _profile()
        for n in range(5):
            _recipe(slug=f"det-recipe-{n}")

        rng1 = random.Random(0)
        rng2 = random.Random(0)
        result1 = select_recipe(profile, "lunch", PLAN_DATE, rng=rng1)
        result2 = select_recipe(profile, "lunch", PLAN_DATE, rng=rng2)
        assert result1 == result2


# ---------------------------------------------------------------------------
# Diet hierarchy tests (4)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDietHierarchy:
    def test_diet_hierarchy_vegan_gets_vegan_only(self) -> None:
        profile = _profile(diet_pattern="vegan")
        vegan = _recipe(slug="vegan-dh", diet_tags=["vegan"])
        _recipe(slug="veg-dh", diet_tags=["vegetarian"])
        _recipe(slug="egg-dh", diet_tags=["eggetarian"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == vegan

    def test_diet_hierarchy_vegetarian_gets_veg_plus_vegan(self) -> None:
        profile = _profile(diet_pattern="vegetarian")
        veg = _recipe(slug="veg-vh", diet_tags=["vegetarian"])
        vegan2 = _recipe(slug="vegan-vh", diet_tags=["vegan"])
        _recipe(slug="egg-vh", diet_tags=["eggetarian"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {veg, vegan2}

    def test_diet_hierarchy_eggetarian_gets_egg_veg_vegan(self) -> None:
        profile = _profile(diet_pattern="eggetarian")
        egg = _recipe(slug="egg-eh", diet_tags=["eggetarian"])
        veg2 = _recipe(slug="veg-eh", diet_tags=["vegetarian"])
        vegan3 = _recipe(slug="vegan-eh", diet_tags=["vegan"])
        _recipe(slug="none-eh", diet_tags=[])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {egg, veg2, vegan3}

    def test_diet_hierarchy_nonveg_gets_all(self) -> None:
        profile = _profile(diet_pattern="non_vegetarian")
        r_none = _recipe(slug="no-tag-nv", diet_tags=[])
        r_veg = _recipe(slug="veg-tag-nv", diet_tags=["vegetarian"])
        r_vegan = _recipe(slug="vegan-tag-nv", diet_tags=["vegan"])
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result in {r_none, r_veg, r_vegan}


# ---------------------------------------------------------------------------
# generate_week tests (3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGenerateWeek:
    def _week_recipes(self, cal_per_slot: dict[str, int]) -> None:
        """Create one recipe per slot covering the calorie windows for the given targets."""
        for slug_suffix, slot in (("bf", "breakfast"), ("lu", "lunch"), ("di", "dinner")):
            _recipe(
                slug=f"week-{slug_suffix}",
                meal_type=slot,
                diet_tags=["vegetarian"],
                cached_calories_per_serving=cal_per_slot[slot],
            )

    def test_generate_week_returns_7_days(self) -> None:
        profile = _profile()
        tc = profile.target_calories or 2000
        self._week_recipes(
            {
                "breakfast": int(tc * 0.25),
                "lunch": int(tc * 0.40),
                "dinner": int(tc * 0.35),
            }
        )
        result = generate_week(profile, date(2026, 6, 2), rng=_rng())
        assert len(result) == 7

    def test_generate_week_all_slots_populated(self) -> None:
        profile = _profile()
        tc = profile.target_calories or 2000
        self._week_recipes(
            {
                "breakfast": int(tc * 0.25),
                "lunch": int(tc * 0.40),
                "dinner": int(tc * 0.35),
            }
        )
        result = generate_week(profile, date(2026, 6, 2), rng=_rng())
        for day in result:
            assert "breakfast" in day and day["breakfast"] is not None
            assert "lunch" in day and day["lunch"] is not None
            assert "dinner" in day and day["dinner"] is not None

    def test_generate_week_propagates_no_suitable_recipe_error(self) -> None:
        # No recipes at all → NoSuitableRecipeError on first slot
        profile = _profile()
        with pytest.raises(NoSuitableRecipeError) as exc_info:
            generate_week(profile, date(2026, 6, 2), rng=_rng())
        assert exc_info.value.slot in ("breakfast", "lunch", "dinner")


# ---------------------------------------------------------------------------
# plan_service tests (8)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPlanService:
    """Tests for get_or_generate_plan, regenerate_slot, regenerate_plan."""

    def _make_profile_with_recipes(
        self, diet_pattern: str = "vegetarian"
    ):  # type: ignore[no-untyped-def]
        """Create a DietaryProfile and one recipe per slot that fits its calorie windows."""
        profile = _profile(diet_pattern=diet_pattern)
        tc = profile.target_calories or 2000
        slots = {
            "breakfast": int(tc * 0.25),
            "lunch": int(tc * 0.40),
            "dinner": int(tc * 0.35),
        }
        recipes = {}
        for slot, cal in slots.items():
            extra_tag: list[str] = ["vegetarian"] if diet_pattern != "non_vegetarian" else []
            r = _recipe(
                slug=f"ps-{diet_pattern}-{slot}",
                meal_type=slot,
                diet_tags=extra_tag,
                cached_calories_per_serving=cal,
            )
            recipes[slot] = r
        return profile, recipes

    def test_get_or_generate_creates_all_three_slots(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan

        profile, _ = self._make_profile_with_recipes()
        plan = get_or_generate_plan(profile.user, PLAN_DATE)
        assert plan.breakfast is not None
        assert plan.lunch is not None
        assert plan.dinner is not None

    def test_get_or_generate_is_idempotent(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan

        profile, _ = self._make_profile_with_recipes()
        plan1 = get_or_generate_plan(profile.user, PLAN_DATE)
        plan2 = get_or_generate_plan(profile.user, PLAN_DATE)
        assert plan1.id == plan2.id
        assert plan1.breakfast_id == plan2.breakfast_id

    def test_get_or_generate_requires_profile(self) -> None:
        from apps.accounts.tests.factories import UserFactory
        from apps.mealplans.services.plan_service import get_or_generate_plan
        from core.exceptions import NotFoundError

        user = UserFactory()
        with pytest.raises(NotFoundError):
            get_or_generate_plan(user, PLAN_DATE)

    def test_regenerate_slot_returns_different_recipe(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile = _profile()
        tc = profile.target_calories or 2000
        cal = int(tc * 0.40)
        r1 = _recipe(slug="regen-lunch-1", meal_type="lunch", cached_calories_per_serving=cal)
        r2 = _recipe(slug="regen-lunch-2", meal_type="lunch", cached_calories_per_serving=cal)
        # create breakast+dinner to satisfy get_or_generate
        _recipe(
            slug="regen-bf",
            meal_type="breakfast",
            cached_calories_per_serving=int(tc * 0.25),
        )
        _recipe(
            slug="regen-din",
            meal_type="dinner",
            cached_calories_per_serving=int(tc * 0.35),
        )

        plan = get_or_generate_plan(profile.user, PLAN_DATE)
        original_lunch_id = plan.lunch_id

        updated = regenerate_slot(profile.user, PLAN_DATE, "lunch")
        new_lunch_id = updated.lunch_id

        assert {r1.id, r2.id}.issuperset({original_lunch_id, new_lunch_id})
        assert original_lunch_id != new_lunch_id

    def test_regenerate_slot_increments_count(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile = _profile()
        tc = profile.target_calories or 2000
        cal = int(tc * 0.40)
        _recipe(slug="inc-lunch-1", meal_type="lunch", cached_calories_per_serving=cal)
        _recipe(slug="inc-lunch-2", meal_type="lunch", cached_calories_per_serving=cal)
        _recipe(
            slug="inc-bf",
            meal_type="breakfast",
            cached_calories_per_serving=int(tc * 0.25),
        )
        _recipe(
            slug="inc-din",
            meal_type="dinner",
            cached_calories_per_serving=int(tc * 0.35),
        )

        get_or_generate_plan(profile.user, PLAN_DATE)
        updated = regenerate_slot(profile.user, PLAN_DATE, "lunch")
        assert updated.regeneration_count["lunch"] == 1

    def test_regenerate_slot_rate_limited_after_3(self) -> None:
        from apps.mealplans.services.plan_service import regenerate_slot
        from apps.mealplans.tests.factories import MealPlanFactory
        from core.error_codes import REGENERATE_LIMIT
        from core.exceptions import RateLimitError

        profile = _profile()
        tc = profile.target_calories or 2000
        cal = int(tc * 0.40)
        r1 = _recipe(slug="rl-lunch-1", meal_type="lunch", cached_calories_per_serving=cal)
        r2 = _recipe(slug="rl-lunch-2", meal_type="lunch", cached_calories_per_serving=cal)

        plan = MealPlanFactory(
            user=profile.user,
            plan_date=PLAN_DATE,
            lunch=r1,
            regeneration_count={"breakfast": 0, "lunch": 3, "dinner": 0},
        )
        assert plan.regeneration_count["lunch"] == 3

        with pytest.raises(RateLimitError) as exc_info:
            regenerate_slot(profile.user, PLAN_DATE, "lunch")
        assert exc_info.value.code == REGENERATE_LIMIT
        assert r2.id is not None  # r2 exists in pool; rate limit fires before engine runs

    def _two_lunch_plan(self):  # type: ignore[no-untyped-def]
        """Build a profile + plan with two interchangeable lunch recipes."""
        profile = _profile()
        tc = profile.target_calories or 2000
        cal = int(tc * 0.40)
        r1 = _recipe(slug="pv-lunch-1", meal_type="lunch", cached_calories_per_serving=cal)
        r2 = _recipe(slug="pv-lunch-2", meal_type="lunch", cached_calories_per_serving=cal)
        _recipe(slug="pv-bf", meal_type="breakfast", cached_calories_per_serving=int(tc * 0.25))
        _recipe(slug="pv-din", meal_type="dinner", cached_calories_per_serving=int(tc * 0.35))
        return profile, r1, r2

    def test_regenerate_slot_preview_does_not_persist(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile, r1, r2 = self._two_lunch_plan()
        plan = get_or_generate_plan(profile.user, PLAN_DATE)
        original_lunch_id = plan.lunch_id

        result = regenerate_slot(profile.user, PLAN_DATE, "lunch", preview=True)

        # Returned (in-memory) plan shows a different candidate...
        assert result.lunch_id != original_lunch_id
        assert result.lunch_id in {r1.id, r2.id}
        # ...but the DB row is untouched and the counter did not move.
        plan.refresh_from_db()
        assert plan.lunch_id == original_lunch_id
        assert plan.regeneration_count.get("lunch", 0) == 0

    def test_regenerate_slot_preview_twice_no_count_change(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile, _, _ = self._two_lunch_plan()
        plan = get_or_generate_plan(profile.user, PLAN_DATE)
        original_lunch_id = plan.lunch_id

        regenerate_slot(profile.user, PLAN_DATE, "lunch", preview=True)
        regenerate_slot(profile.user, PLAN_DATE, "lunch", preview=True)

        plan.refresh_from_db()
        assert plan.lunch_id == original_lunch_id
        assert plan.regeneration_count.get("lunch", 0) == 0

    def test_regenerate_slot_commit_with_recipe_id_persists_that_recipe(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile, r1, r2 = self._two_lunch_plan()
        plan = get_or_generate_plan(profile.user, PLAN_DATE)
        target_id = r2.id if plan.lunch_id == r1.id else r1.id

        updated = regenerate_slot(profile.user, PLAN_DATE, "lunch", recipe_id=target_id)

        assert updated.lunch_id == target_id
        plan.refresh_from_db()
        assert plan.lunch_id == target_id
        assert plan.regeneration_count["lunch"] == 1

    def test_regenerate_slot_commit_invalid_recipe_id_raises(self) -> None:
        from apps.mealplans.services.engine import NoSuitableRecipeError
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_slot

        profile, _, _ = self._two_lunch_plan()
        # A breakfast recipe is not a valid choice for the lunch slot.
        wrong = _recipe(slug="pv-wrong", meal_type="breakfast", cached_calories_per_serving=500)
        get_or_generate_plan(profile.user, PLAN_DATE)

        with pytest.raises(NoSuitableRecipeError):
            regenerate_slot(profile.user, PLAN_DATE, "lunch", recipe_id=wrong.id)

    def test_regenerate_plan_creates_fresh_plan(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_plan

        profile, _ = self._make_profile_with_recipes()
        original = get_or_generate_plan(profile.user, PLAN_DATE)
        original_id = original.id

        fresh = regenerate_plan(profile.user, PLAN_DATE)
        assert fresh.id != original_id
        assert fresh.full_plan_regenerations == 1

    def test_regenerate_plan_rate_limited_after_3_per_week(self) -> None:
        from datetime import timedelta

        from apps.mealplans.services.plan_service import regenerate_plan
        from apps.mealplans.tests.factories import MealPlanFactory
        from core.error_codes import REGENERATE_LIMIT
        from core.exceptions import RateLimitError

        profile = _profile()
        # Seed 3 plans in the same ISO week, each with full_plan_regenerations=1 (total = 3)
        week_start = PLAN_DATE - timedelta(days=PLAN_DATE.weekday())
        for i in range(3):
            MealPlanFactory(
                user=profile.user,
                plan_date=week_start + timedelta(days=i),
                full_plan_regenerations=1,
            )

        with pytest.raises(RateLimitError) as exc_info:
            regenerate_plan(profile.user, PLAN_DATE)
        assert exc_info.value.code == REGENERATE_LIMIT

    def test_regenerate_plan_increments_full_plan_regenerations(self) -> None:
        from apps.mealplans.services.plan_service import get_or_generate_plan, regenerate_plan

        profile, _ = self._make_profile_with_recipes()
        get_or_generate_plan(profile.user, PLAN_DATE)

        plan_v2 = regenerate_plan(profile.user, PLAN_DATE)
        assert plan_v2.full_plan_regenerations == 1

        plan_v3 = regenerate_plan(profile.user, PLAN_DATE)
        assert plan_v3.full_plan_regenerations == 2

        plan_v4 = regenerate_plan(profile.user, PLAN_DATE)
        assert plan_v4.full_plan_regenerations == 3

    def test_regenerate_plan_allows_regeneration_in_new_week(self) -> None:
        from datetime import timedelta

        from apps.mealplans.services.plan_service import regenerate_plan
        from apps.mealplans.tests.factories import MealPlanFactory

        profile, _ = self._make_profile_with_recipes()

        # Exhaust the rate limit in the PREVIOUS ISO week
        prev_week_monday = PLAN_DATE - timedelta(days=PLAN_DATE.weekday() + 7)
        for i in range(3):
            MealPlanFactory(
                user=profile.user,
                plan_date=prev_week_monday + timedelta(days=i),
                full_plan_regenerations=1,
            )

        # Current week has 0 full regenerations → should succeed
        MealPlanFactory(user=profile.user, plan_date=PLAN_DATE)
        plan = regenerate_plan(profile.user, PLAN_DATE)
        assert plan.full_plan_regenerations == 1


# ---------------------------------------------------------------------------
# AI-generated recipe in engine pool (M7 test #20)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAiGeneratedRecipeInPool:
    """Policy: AI-generated recipes are "save but don't reuse" — the engine excludes them."""

    def test_ai_recipe_excluded_from_engine_candidate_pool(self) -> None:
        """A recipe with source='ai_generated' is NOT selectable by the engine."""
        from apps.recipes.models import RECIPE_SOURCE_AI

        profile = _profile()
        # Only recipe in the pool is AI-generated → no eligible candidate.
        _recipe(
            slug="ai-generated-dal-rice",
            source=RECIPE_SOURCE_AI,
        )
        with pytest.raises(NoSuitableRecipeError):
            select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())

    def test_non_ai_recipe_still_selectable(self) -> None:
        """A normal (non-AI) recipe in the same conditions is still selected."""
        profile = _profile()
        normal = _recipe(slug="curated-dal-rice")
        result = select_recipe(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == normal


# ---------------------------------------------------------------------------
# select_recipe_with_fallback (M7 test #26)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSelectRecipeWithFallback:
    """M7 acceptance: fallback hook returns None instead of raising."""

    def test_returns_recipe_when_pool_has_candidates(self) -> None:
        profile = _profile()
        recipe = _recipe(slug="fallback-has-recipe")
        result = select_recipe_with_fallback(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result == recipe

    def test_returns_none_when_no_suitable_recipe(self) -> None:
        """On NoSuitableRecipeError the fallback returns None (caller decides what to do)."""
        profile = _profile(allergies=["dairy"])
        _recipe(slug="dairy-only-fallback", allergen_tags=["dairy"])
        result = select_recipe_with_fallback(profile, "lunch", PLAN_DATE, rng=_rng())
        assert result is None


# Cells with < 3 candidates after steps 1–4 that are explicitly accepted.
# (diet_pattern, slot): human-readable reason
KNOWN_THIN_CELLS: dict[tuple[str, str], str] = {
    # After M4.5 expansion (151 recipes), vegan dinner in the [262,437] kcal window
    # still has only ~2 candidates — remaining vegan dinners land above 437 kcal.
    ("vegan", "dinner"): "only ~2 vegan dinner recipes in the [262,437] kcal window",
}

import logging as _logging  # noqa: E402

_inv_log = _logging.getLogger("apps.mealplans.tests.thin_cell_inventory")


@pytest.mark.django_db
def test_engine_thin_cell_inventory() -> None:
    """Regression guard: no previously-OK (diet_pattern, slot) cell should drop below 3 recipes."""
    from pathlib import Path

    from apps.mealplans.services.engine import (
        DIET_HIERARCHY,
        SLOT_CALORIE_WINDOW,
    )
    from apps.recipes.models import Recipe
    from apps.recipes.services.seed import seed_household_units, seed_ingredients, seed_recipes

    seed_dir = Path(__file__).resolve().parent.parent.parent / "recipes" / "seed_data"
    seed_ingredients(seed_dir / "ingredients.json")
    seed_household_units(seed_dir / "household_units.json")
    seed_recipes(seed_dir / "recipes.json")

    # 1000 kcal keeps slot windows within the seed recipes' actual calorie range
    # (seed recipes are light Indian portions: 138–575 kcal/serving).
    target_calories = 1000
    max_prep_time = 60
    slot_calorie_ratio = {"breakfast": 0.25, "lunch": 0.40, "dinner": 0.35}

    diet_patterns = ["vegan", "vegetarian", "eggetarian", "non_vegetarian"]
    slots = ["breakfast", "lunch", "dinner"]

    results: list[dict[str, object]] = []
    regressions: list[str] = []

    for diet_pattern in diet_patterns:
        for slot in slots:
            slot_target = int(target_calories * slot_calorie_ratio[slot])
            low_ratio, high_ratio = SLOT_CALORIE_WINDOW[slot]
            cal_low = int(slot_target * low_ratio)
            cal_high = int(slot_target * high_ratio)

            pool = Recipe.objects.filter(
                meal_type=slot,
                is_active=True,
                prep_time_min__lte=max_prep_time,
                cached_calories_per_serving__gte=cal_low,
                cached_calories_per_serving__lte=cal_high,
            )

            allowed_tags = DIET_HIERARCHY.get(diet_pattern, [])
            if allowed_tags:
                pool = pool.filter(diet_tags__overlap=allowed_tags)

            pool_size = pool.count()
            cell = (diet_pattern, slot)
            results.append({"diet_pattern": diet_pattern, "slot": slot, "pool_size": pool_size})

            if pool_size < 3 and cell not in KNOWN_THIN_CELLS:
                regressions.append(
                    f"REGRESSION: ({diet_pattern}, {slot}) has only {pool_size} candidates"
                )

    thin_cells = [r for r in results if r["pool_size"] < 3]  # type: ignore[operator]
    _inv_log.info(
        "event=thin_cell_inventory total_cells=%d thin_cells=%d details=%s",
        len(results),
        len(thin_cells),
        thin_cells,
    )

    assert not regressions, "\n".join(regressions)
