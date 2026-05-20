"""
NutriPlan nutrition mathematics — M2 implementation.

All constants are defined at module top. `date.today()` is NEVER cached at
module load time; it is called at runtime inside compute_age() to prevent
year-staleness bugs when the server runs across midnight or across a new year.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.profiles.models import DietaryProfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOAL_CALORIE_DELTA: dict[str, int] = {
    "lose_weight": -500,
    "maintain": 0,
    "gain_muscle": 300,
    "gain_weight_healthy": 500,
    "eat_healthier": 0,
}

# [protein_pct, carbs_pct, fat_pct]
MACRO_SPLITS: dict[str, list[float]] = {
    "lose_weight": [0.35, 0.40, 0.25],
    "maintain": [0.25, 0.50, 0.25],
    "gain_muscle": [0.30, 0.45, 0.25],
    "gain_weight_healthy": [0.25, 0.50, 0.25],
    "eat_healthier": [0.25, 0.50, 0.25],
}

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very": 1.725,
    "athlete": 1.9,
}

# eat_healthier uses 18g/1000 kcal to emphasise micronutrient density.
# All other goals use 14g/1000 kcal.
# In M4, eat_healthier profiles will also receive a +15 scoring boost for
# recipes with high fiber-per-100-kcal — that boost is deferred; this target
# is the only M2 signal.
FIBER_TARGET_PER_1000_KCAL: dict[str, float] = {
    "default": 14.0,
    "eat_healthier": 18.0,
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def compute_age(dob: date, today: date | None = None) -> int:
    """
    Return age in whole years derived from date_of_birth.

    Pass `today` explicitly in tests (or use freezegun) to pin the current date.
    Do NOT call date.today() at module import time — that would cache an
    incorrect value across year boundaries.
    """
    if today is None:
        today = date.today()
    years = today.year - dob.year
    # Subtract 1 if the birthday hasn't occurred yet this year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def compute_targets(profile: DietaryProfile) -> None:
    """
    Compute BMR, TDEE, and macro targets for a DietaryProfile and mutate
    the profile's target_* fields in place.

    Algorithm (Mifflin-St Jeor):
      1. age = compute_age(date_of_birth)
      2. bmr_base = 10 * weight_kg + 6.25 * height_cm - 5 * age
      3. Sex offset:
           male                → bmr = bmr_base + 5
           female              → bmr = bmr_base - 161
           other / prefer_not_to_say → bmr = bmr_base - 78
             (average of male offset +5 and female offset -161:
              ((bmr_base + 5) + (bmr_base - 161)) / 2 = bmr_base - 78)
      4. tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]
      5. target_calories = max(1200, round(tdee + GOAL_CALORIE_DELTA[goal]))
      6. Macros derived from target_calories × MACRO_SPLITS percentages:
           protein_g  = calories * protein_pct / 4   (protein has 4 kcal/g)
           carbs_g    = calories * carbs_pct   / 4   (carbs have 4 kcal/g)
           fat_g      = calories * fat_pct     / 9   (fat has 9 kcal/g)
      7. fiber_g = calories / 1000 * FIBER_TARGET_PER_1000_KCAL[goal or default]

    This function is called from DietaryProfile.save() and has no network calls.
    """
    age = compute_age(profile.date_of_birth)

    weight = float(profile.weight_kg)
    height = float(profile.height_cm)

    bmr_base = 10.0 * weight + 6.25 * height - 5.0 * age

    sex = profile.sex
    if sex == "male":
        bmr = bmr_base + 5.0
    elif sex == "female":
        bmr = bmr_base - 161.0
    else:
        # "other" and "prefer_not_to_say" use the average of male and female:
        # ((bmr_base + 5) + (bmr_base - 161)) / 2 = bmr_base - 78
        bmr = bmr_base - 78.0

    tdee = bmr * ACTIVITY_MULTIPLIERS[profile.activity_level]
    delta = GOAL_CALORIE_DELTA[profile.goal]
    target_calories = max(1200, round(tdee + delta))

    split = MACRO_SPLITS[profile.goal]
    target_protein_g = round(target_calories * split[0] / 4, 1)
    target_carbs_g = round(target_calories * split[1] / 4, 1)
    target_fat_g = round(target_calories * split[2] / 9, 1)

    fiber_rate = FIBER_TARGET_PER_1000_KCAL.get(profile.goal, FIBER_TARGET_PER_1000_KCAL["default"])
    target_fiber_g = round(target_calories / 1000 * fiber_rate, 1)

    profile.target_calories = target_calories
    profile.target_protein_g = Decimal(str(round(target_protein_g, 1)))
    profile.target_carbs_g = Decimal(str(round(target_carbs_g, 1)))
    profile.target_fat_g = Decimal(str(round(target_fat_g, 1)))
    profile.target_fiber_g = Decimal(str(round(target_fiber_g, 1)))
