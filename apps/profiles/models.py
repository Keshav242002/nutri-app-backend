from decimal import Decimal
from typing import Any

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import User
from core.mixins import TimestampedModel
from core.utils.nutrition_math import compute_targets

# ---------------------------------------------------------------------------
# Choice constants (module-level for mypy compliance)
# ---------------------------------------------------------------------------

SEX_MALE = "male"
SEX_FEMALE = "female"
SEX_OTHER = "other"
SEX_PREFER_NOT = "prefer_not_to_say"
SEX_CHOICES = [
    (SEX_MALE, "Male"),
    (SEX_FEMALE, "Female"),
    (SEX_OTHER, "Other"),
    (SEX_PREFER_NOT, "Prefer not to say"),
]

ACTIVITY_SEDENTARY = "sedentary"
ACTIVITY_LIGHT = "light"
ACTIVITY_MODERATE = "moderate"
ACTIVITY_VERY = "very"
ACTIVITY_ATHLETE = "athlete"
ACTIVITY_CHOICES = [
    (ACTIVITY_SEDENTARY, "Sedentary"),
    (ACTIVITY_LIGHT, "Light"),
    (ACTIVITY_MODERATE, "Moderate"),
    (ACTIVITY_VERY, "Very Active"),
    (ACTIVITY_ATHLETE, "Athlete"),
]

GOAL_LOSE = "lose_weight"
GOAL_MAINTAIN = "maintain"
GOAL_GAIN_MUSCLE = "gain_muscle"
GOAL_GAIN_HEALTHY = "gain_weight_healthy"
GOAL_EAT_HEALTHIER = "eat_healthier"
GOAL_CHOICES = [
    (GOAL_LOSE, "Lose Weight"),
    (GOAL_MAINTAIN, "Maintain"),
    (GOAL_GAIN_MUSCLE, "Gain Muscle"),
    (GOAL_GAIN_HEALTHY, "Gain Weight (Healthy)"),
    (GOAL_EAT_HEALTHIER, "Eat Healthier"),
]

REGION_NORTH = "north_indian"
REGION_SOUTH = "south_indian"
REGION_EAST = "east_indian"
REGION_WEST = "west_indian"
REGION_CHOICES = [
    (REGION_NORTH, "North Indian"),
    (REGION_SOUTH, "South Indian"),
    (REGION_EAST, "East Indian"),
    (REGION_WEST, "West Indian"),
]

SPICE_MILD = "mild"
SPICE_MEDIUM = "medium"
SPICE_HOT = "hot"
SPICE_VERY_HOT = "very_hot"
SPICE_CHOICES = [
    (SPICE_MILD, "Mild"),
    (SPICE_MEDIUM, "Medium"),
    (SPICE_HOT, "Hot"),
    (SPICE_VERY_HOT, "Very Hot"),
]

DIET_VEGETARIAN = "vegetarian"
DIET_EGGETARIAN = "eggetarian"
DIET_NON_VEG = "non_vegetarian"
DIET_PESCATARIAN = "pescatarian"
DIET_VEGAN = "vegan"
DIET_JAIN = "jain"
DIET_CHOICES = [
    (DIET_VEGETARIAN, "Vegetarian"),
    (DIET_EGGETARIAN, "Eggetarian"),
    (DIET_NON_VEG, "Non-Vegetarian"),
    (DIET_PESCATARIAN, "Pescatarian"),
    (DIET_VEGAN, "Vegan"),
    (DIET_JAIN, "Jain"),
]

COOKING_DAILY = "daily"
COOKING_WEEKENDS = "weekends_only"
COOKING_RARELY = "rarely"
COOKING_CHOICES = [
    (COOKING_DAILY, "Daily"),
    (COOKING_WEEKENDS, "Weekends Only"),
    (COOKING_RARELY, "Rarely"),
]

SKILL_BEGINNER = "beginner"
SKILL_INTERMEDIATE = "intermediate"
SKILL_ADVANCED = "advanced"
SKILL_CHOICES = [
    (SKILL_BEGINNER, "Beginner"),
    (SKILL_INTERMEDIATE, "Intermediate"),
    (SKILL_ADVANCED, "Advanced"),
]

SECONDARY_CUISINE_VOCAB = [
    "punjabi",
    "gujarati",
    "maharashtrian",
    "bengali",
    "tamil",
    "kerala",
    "andhra",
    "rajasthani",
    "goan",
    "sindhi",
    "continental",
    "chinese_indo",
    "pan_asian",
]

ALLERGY_VOCAB = [
    "dairy",
    "eggs",
    "gluten",
    "peanuts",
    "tree_nuts",
    "soy",
    "shellfish",
    "fish",
    "sesame",
    "mustard",
]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class DietaryProfile(TimestampedModel):
    """
    One record per user — captures biometrics, goal, dietary restrictions,
    cuisine preference, budget, and cooking constraints for Indian-first
    meal planning. Macro targets are recomputed on every save.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Step 1 — Basics
    date_of_birth = models.DateField()
    sex = models.CharField(max_length=20, choices=SEX_CHOICES)
    height_cm = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(100), MaxValueValidator(250)]
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(Decimal("30.0")), MaxValueValidator(Decimal("300.0"))],
    )

    # Step 2 — Activity and goal
    activity_level = models.CharField(max_length=10, choices=ACTIVITY_CHOICES)
    goal = models.CharField(max_length=20, choices=GOAL_CHOICES)

    # Step 3 — Cuisine and region
    primary_cuisine_region = models.CharField(max_length=20, choices=REGION_CHOICES)
    secondary_cuisine_preferences = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )
    spice_tolerance = models.CharField(max_length=10, choices=SPICE_CHOICES)

    # Step 4 — Dietary pattern
    diet_pattern = models.CharField(max_length=20, choices=DIET_CHOICES)
    no_onion_garlic = models.BooleanField(default=False)
    allergies = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )
    dislikes = ArrayField(
        models.CharField(max_length=64),
        default=list,
        blank=True,
    )

    # Step 5 — Budget and household
    daily_food_budget_inr = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("100")), MaxValueValidator(Decimal("3000"))],
    )
    weekly_food_budget_inr = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("700")), MaxValueValidator(Decimal("20000"))],
    )
    household_size = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    cooking_frequency = models.CharField(max_length=15, choices=COOKING_CHOICES)

    # Step 6 — Cooking constraints
    max_prep_time_min = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(10), MaxValueValidator(90)],
    )
    skill_level = models.CharField(max_length=15, choices=SKILL_CHOICES)

    # Computed targets — populated by compute_targets() called in save()
    target_calories = models.PositiveIntegerField(null=True, blank=True)
    target_protein_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    target_carbs_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    target_fat_g = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    target_fiber_g = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    class Meta:
        verbose_name = "Dietary Profile"
        verbose_name_plural = "Dietary Profiles"
        indexes = [
            models.Index(fields=["user"]),
            GinIndex(fields=["allergies"], name="profiles_allergies_gin"),
            GinIndex(
                fields=["secondary_cuisine_preferences"],
                name="profiles_secondary_cuisine_gin",
            ),
        ]

    def __str__(self) -> str:
        return f"DietaryProfile(user={self.user_id}, goal={self.goal})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Recompute macro targets on every save (no network calls — safe in save())."""
        compute_targets(self)
        super().save(*args, **kwargs)
