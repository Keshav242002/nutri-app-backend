from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

from django.db.models import DecimalField, ExpressionWrapper, F, Q

from apps.profiles.models import DietaryProfile
from apps.recipes.models import Recipe

if TYPE_CHECKING:
    from apps.accounts.models import User

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slot ratios
# ---------------------------------------------------------------------------

SLOT_CALORIE_RATIO: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.40,
    "dinner": 0.35,
}

SLOT_BUDGET_RATIO: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.40,
    "dinner": 0.35,
}

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

SCORE_CUISINE_MATCH: int = 30
SCORE_MACRO_MATCH_MULTIPLIER: int = 20
SCORE_RECENT_PENALTY: int = -50
SCORE_RANDOM_TIEBREAKER_MAX: int = 5
SCORE_BUDGET_FIT_BASE: int = 25
SCORE_FIBER_BOOST: int = 15
SCORE_BATCH_COOKABLE_BOOST: int = 10
SCORE_QUICK_RECIPE_BOOST: int = 15
SCORE_PROTEIN_REPEAT_PENALTY: int = -25

# ---------------------------------------------------------------------------
# Budget / calorie window thresholds
# ---------------------------------------------------------------------------

BUDGET_STRICT_GRACE: float = 1.15
BUDGET_RELAXED_GRACE: float = 1.40

# Per-slot calorie windows. Breakfast is intentionally wider (50-150%) because
# Indian breakfast recipes are typically lighter than lunch/dinner — a single
# poha/upma serving is 200-300 kcal, while a 25% slot target for a 2500 kcal/day
# user is 625 kcal. This wider window is a known compromise pending v1.1
# fractional servings support (see M5 portion sizing).
SLOT_CALORIE_WINDOW: dict[str, tuple[float, float]] = {
    "breakfast": (0.50, 1.50),
    "lunch": (0.75, 1.25),
    "dinner": (0.75, 1.25),
}

VARIETY_LOOKBACK_DAYS: int = 7
CANDIDATE_POOL_CAP: int = 200

# ---------------------------------------------------------------------------
# Diet hierarchy: profile diet_pattern → acceptable recipe diet_tags
# ---------------------------------------------------------------------------

DIET_HIERARCHY: dict[str, list[str]] = {
    "vegan": ["vegan"],
    "vegetarian": ["vegetarian", "vegan"],
    "eggetarian": ["eggetarian", "vegetarian", "vegan"],
    "pescatarian": ["pescatarian", "vegetarian", "vegan"],
    "non_vegetarian": [],  # no filter — all recipes OK
    "jain": ["jain", "vegetarian", "vegan"],
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NoSuitableRecipeError(Exception):
    """Raised when the engine cannot find any recipe matching constraints."""

    def __init__(self, slot: str, plan_date: date, reason: str = "") -> None:
        self.slot = slot
        self.plan_date = plan_date
        self.reason = reason
        super().__init__(f"No suitable recipe for {slot} on {plan_date}: {reason}")


# ---------------------------------------------------------------------------
# Internal data holder for scored candidates
# ---------------------------------------------------------------------------


@dataclass
class _ScoredRecipe:
    recipe: Recipe
    score: float = field(default=0.0)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_cuisine_preferences(profile: DietaryProfile) -> set[str]:
    """Union of primary_cuisine_region and secondary_cuisine_preferences."""
    prefs: set[str] = {profile.primary_cuisine_region}
    prefs.update(profile.secondary_cuisine_preferences or [])
    return prefs


def _compute_slot_macro_targets(profile: DietaryProfile, slot: str) -> dict[str, float]:
    """Compute per-slot macro targets from profile daily totals scaled by slot ratio."""
    ratio = SLOT_CALORIE_RATIO[slot]
    return {
        "protein_g": float(profile.target_protein_g or 0) * ratio,
        "carbs_g": float(profile.target_carbs_g or 0) * ratio,
        "fat_g": float(profile.target_fat_g or 0) * ratio,
    }


def _compute_macro_match(recipe: Recipe, slot_macros: dict[str, float]) -> float:
    """Return 0.0–1.0 score: how closely recipe macros match slot targets."""
    nutrition = recipe.cached_nutrition or {}
    deviations = []
    for macro in ("protein_g", "carbs_g", "fat_g"):
        actual = float(nutrition.get(macro) or 0)
        target = slot_macros.get(macro, 0.0)
        if target > 0:
            deviation = abs(actual - target) / target
            deviations.append(min(deviation, 1.0))
        else:
            deviations.append(0.0)
    avg_deviation = sum(deviations) / len(deviations) if deviations else 0.0
    return max(0.0, 1.0 - avg_deviation)


def _get_recent_recipe_ids(user: User, slot: str, days: int, plan_date: date) -> set[int]:
    """Return Recipe IDs used in this slot during the last N days for this user."""
    from apps.mealplans.models import MealPlan

    cutoff = date.fromordinal(plan_date.toordinal() - days)
    slot_field = f"{slot}_id"
    qs = MealPlan.objects.filter(
        user=user,
        plan_date__gt=cutoff,
        plan_date__lt=plan_date,
    ).values_list(slot_field, flat=True)
    return {pk for pk in qs if pk is not None}


def _get_yesterday_protein_source(user: User, slot: str, plan_date: date) -> str | None:
    """Return protein_source of the recipe in this slot on the previous day, or None."""
    from apps.mealplans.models import MealPlan

    yesterday = date.fromordinal(plan_date.toordinal() - 1)
    try:
        plan = MealPlan.objects.select_related(slot).get(user=user, plan_date=yesterday)
    except MealPlan.DoesNotExist:
        return None
    recipe: Recipe | None = getattr(plan, slot)
    if recipe is None:
        return None
    return recipe.protein_source if recipe.protein_source else None


def _compute_budget_overshoot(recipe: Recipe, slot_budget: float) -> float:
    """Return a penalty proportional to how much cost_per_serving exceeds slot_budget.

    Returns 0 when within budget, positive value when over.
    """
    if recipe.cached_cost_inr is None or not recipe.cost_known:
        return 0.0
    servings = max(recipe.servings, 1)
    cost_per_serving = float(recipe.cached_cost_inr) / servings
    if cost_per_serving <= slot_budget:
        return 0.0
    return cost_per_serving - slot_budget


# ---------------------------------------------------------------------------
# Core engine function
# ---------------------------------------------------------------------------


def select_recipe(
    profile: DietaryProfile,
    slot: str,
    plan_date: date,
    exclude_recipe_ids: list[int] | None = None,
    rng: random.Random | None = None,
) -> Recipe:
    """Select the highest-scoring Recipe for a slot given a DietaryProfile.

    Pure read-only function: makes no DB writes. Raises NoSuitableRecipeError
    when no recipe survives all hard filters.
    """
    if rng is None:
        rng = random.Random()

    # ------------------------------------------------------------------
    # Step 1: Base pool — meal type, active, prep time
    # ------------------------------------------------------------------
    pool = Recipe.objects.filter(
        meal_type=slot,
        is_active=True,
        prep_time_min__lte=profile.max_prep_time_min,
    )

    # ------------------------------------------------------------------
    # Step 2: Diet filter
    # ------------------------------------------------------------------
    allowed_tags = DIET_HIERARCHY.get(profile.diet_pattern, [])
    if allowed_tags:
        pool = pool.filter(diet_tags__overlap=allowed_tags)

    # ------------------------------------------------------------------
    # Step 3: Allergen exclusion
    # ------------------------------------------------------------------
    if profile.allergies:
        pool = pool.exclude(allergen_tags__overlap=profile.allergies)

    # ------------------------------------------------------------------
    # Step 4: Calorie window (uses indexed cached_calories_per_serving)
    # ------------------------------------------------------------------
    slot_target_cal = int((profile.target_calories or 0) * SLOT_CALORIE_RATIO[slot])
    low_ratio, high_ratio = SLOT_CALORIE_WINDOW[slot]
    cal_low = int(slot_target_cal * low_ratio)
    cal_high = int(slot_target_cal * high_ratio)
    pool = pool.filter(
        cached_calories_per_serving__gte=cal_low,
        cached_calories_per_serving__lte=cal_high,
    )

    # ------------------------------------------------------------------
    # Step 5: Budget filter (two-stage with ExpressionWrapper)
    # ------------------------------------------------------------------
    if profile.daily_food_budget_inr:
        slot_budget = float(profile.daily_food_budget_inr) * SLOT_BUDGET_RATIO[slot]
        strict_limit = slot_budget * BUDGET_STRICT_GRACE

        cost_annotation = ExpressionWrapper(
            F("cached_cost_inr") / F("servings"),
            output_field=DecimalField(max_digits=7, decimal_places=2),
        )

        budget_pool = (
            pool.filter(cost_known=True)
            .annotate(cost_per_serving=cost_annotation)
            .filter(cost_per_serving__lte=strict_limit)
        )

        if budget_pool.exists():
            pool = budget_pool
        else:
            log.info(
                "event=budget_too_tight slot=%s strict_limit=%.2f",
                slot,
                strict_limit,
            )
            relaxed_limit = slot_budget * BUDGET_RELAXED_GRACE
            pool = pool.annotate(cost_per_serving=cost_annotation).filter(
                Q(cost_known=False) | Q(cost_known=True, cost_per_serving__lte=relaxed_limit)
            )
    else:
        slot_budget = 0.0

    # ------------------------------------------------------------------
    # Step 6: Explicit exclusions
    # ------------------------------------------------------------------
    if exclude_recipe_ids:
        pool = pool.exclude(id__in=exclude_recipe_ids)

    # ------------------------------------------------------------------
    # Step 7: Variety lookup (soft — penalise in scoring, not hard filter)
    # ------------------------------------------------------------------
    recent_recipe_ids = _get_recent_recipe_ids(
        user=profile.user,
        slot=slot,
        days=VARIETY_LOOKBACK_DAYS,
        plan_date=plan_date,
    )

    # ------------------------------------------------------------------
    # Step 8: Protein variety lookup (non-veg only, same-slot scope)
    # ------------------------------------------------------------------
    yesterday_protein: str | None = None
    if profile.diet_pattern == "non_vegetarian":
        yesterday_protein = _get_yesterday_protein_source(
            user=profile.user, slot=slot, plan_date=plan_date
        )

    # ------------------------------------------------------------------
    # Step 9: Score candidates
    # ------------------------------------------------------------------
    # Cap pool for performance; order_by("id") keeps ordering deterministic so
    # a seeded rng produces reproducible results in tests and reproducible picks
    # in production (randomness comes entirely from rng.uniform tiebreaker below).
    candidates_qs = pool.order_by("id")[:CANDIDATE_POOL_CAP]
    candidates = list(candidates_qs)

    if not candidates:
        raise NoSuitableRecipeError(slot=slot, plan_date=plan_date)

    cuisine_prefs = _get_cuisine_preferences(profile)
    slot_macros = _compute_slot_macro_targets(profile, slot)

    scored: list[_ScoredRecipe] = []
    for recipe in candidates:
        score = 0.0

        # Cuisine match
        if recipe.cuisine in cuisine_prefs:
            score += SCORE_CUISINE_MATCH

        # Macro match
        macro_score = _compute_macro_match(recipe, slot_macros)
        score += SCORE_MACRO_MATCH_MULTIPLIER * macro_score

        # Variety penalty
        if recipe.id in recent_recipe_ids:
            score += SCORE_RECENT_PENALTY

        # Budget scoring
        if profile.daily_food_budget_inr and recipe.cost_known:
            overshoot = _compute_budget_overshoot(recipe, slot_budget)
            score += SCORE_BUDGET_FIT_BASE - overshoot

        # Cooking frequency adjustment
        if profile.cooking_frequency == "daily":
            if (recipe.prep_time_min + recipe.cook_time_min) <= 30:
                score += SCORE_QUICK_RECIPE_BOOST
        elif profile.cooking_frequency in ("weekends_only", "rarely"):
            if recipe.servings >= 4:
                score += SCORE_BATCH_COOKABLE_BOOST

        # eat_healthier fiber boost
        if profile.goal == "eat_healthier":
            nutrition = recipe.cached_nutrition or {}
            if float(nutrition.get("fiber_g") or 0) >= 5:
                score += SCORE_FIBER_BOOST

        # Protein variety penalty (non-veg, same slot)
        if yesterday_protein and recipe.protein_source == yesterday_protein:
            if recipe.protein_source != "none":
                score += SCORE_PROTEIN_REPEAT_PENALTY

        # Random tiebreaker (seeded for deterministic tests)
        score += rng.uniform(0, SCORE_RANDOM_TIEBREAKER_MAX)

        scored.append(_ScoredRecipe(recipe=recipe, score=score))

    # ------------------------------------------------------------------
    # Step 10: Pick highest score
    # ------------------------------------------------------------------
    return max(scored, key=lambda c: c.score).recipe


# ---------------------------------------------------------------------------
# Week generation
# ---------------------------------------------------------------------------


def generate_week(
    profile: DietaryProfile,
    start_date: date,
    rng: random.Random | None = None,
) -> list[dict[str, object]]:
    """Generate 7 days of meal selections starting from start_date. Pure function, no DB writes."""
    if rng is None:
        rng = random.Random()

    plans: list[dict[str, object]] = []
    for day_offset in range(7):
        plan_date = start_date + timedelta(days=day_offset)
        day_plan: dict[str, object] = {"plan_date": plan_date}
        for slot in ("breakfast", "lunch", "dinner"):
            recipe = select_recipe(
                profile=profile,
                slot=slot,
                plan_date=plan_date,
                exclude_recipe_ids=None,
                rng=rng,
            )
            day_plan[slot] = recipe
        plans.append(day_plan)
    return plans


# ---------------------------------------------------------------------------
# Engine fallback hook (opt-in, not wired into views)
# Used by M7 AI layer when the engine pool is empty for a slot.
# ---------------------------------------------------------------------------


def select_recipe_with_fallback(
    profile: DietaryProfile,
    slot: str,
    plan_date: date,
    exclude_recipe_ids: list[int] | None = None,
    rng: random.Random | None = None,
) -> Recipe | None:
    """Call select_recipe; return None instead of raising NoSuitableRecipeError.

    The caller (AI fallback handler) is responsible for deciding what to do when
    None is returned — typically: trigger an AI recipe generation for the slot.
    """
    try:
        return select_recipe(
            profile=profile,
            slot=slot,
            plan_date=plan_date,
            exclude_recipe_ids=exclude_recipe_ids,
            rng=rng,
        )
    except NoSuitableRecipeError:
        log.warning(
            "engine_pool_empty_fallback",
            extra={
                "event": "engine_pool_empty_fallback",
                "slot": slot,
                "plan_date": str(plan_date),
            },
        )
        return None
