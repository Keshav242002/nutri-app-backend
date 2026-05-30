from django.conf import settings
from django.db import models

from core.mixins import TimestampedModel

# ---------------------------------------------------------------------------
# Choice constants
# ---------------------------------------------------------------------------

SLOT_BREAKFAST = "breakfast"
SLOT_LUNCH = "lunch"
SLOT_DINNER = "dinner"

SLOT_CHOICES = [
    (SLOT_BREAKFAST, "Breakfast"),
    (SLOT_LUNCH, "Lunch"),
    (SLOT_DINNER, "Dinner"),
]

STATUS_PLANNED = "planned"
STATUS_ATE_PLANNED = "ate_planned"
STATUS_ATE_SUBSTITUTED = "ate_substituted"
STATUS_ATE_CUSTOM = "ate_custom"
STATUS_SKIPPED = "skipped"

STATUS_CHOICES = [
    (STATUS_PLANNED, "Planned"),
    (STATUS_ATE_PLANNED, "Ate Planned"),
    (STATUS_ATE_SUBSTITUTED, "Ate Substituted"),
    (STATUS_ATE_CUSTOM, "Ate Custom"),
    (STATUS_SKIPPED, "Skipped"),
]

# Statuses that contribute calories to the daily summary
EATING_STATUSES = {STATUS_ATE_PLANNED, STATUS_ATE_SUBSTITUTED, STATUS_ATE_CUSTOM}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class MealLog(TimestampedModel):
    """One meal slot logged per day per user. Upserted by (user, log_date, slot)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meal_logs",
        db_index=True,
    )
    log_date = models.DateField(db_index=True)
    slot = models.CharField(max_length=10, choices=SLOT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)

    # Recipe references — nullable because custom and skipped logs have none
    planned_recipe = models.ForeignKey(
        "recipes.Recipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actual_recipe = models.ForeignKey(
        "recipes.Recipe",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Fractional servings — relevant for ate_planned and ate_substituted
    servings_eaten = models.DecimalField(max_digits=4, decimal_places=2, default=1)

    # Custom meal fields — required when status=ate_custom
    custom_description = models.CharField(max_length=200, null=True, blank=True)
    custom_calories = models.PositiveIntegerField(null=True, blank=True)
    custom_protein_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    custom_carbs_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    custom_fat_g = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    notes = models.CharField(max_length=500, blank=True, default="")
    logged_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "log_date", "slot")]
        indexes = [
            models.Index(fields=["user", "log_date"], name="meallog_user_date_idx"),
        ]

    def __str__(self) -> str:
        return f"MealLog({self.user_id}, {self.log_date}, {self.slot}, {self.status})"


class DailyNutritionSummary(TimestampedModel):
    """Aggregated nutrition for a user on a single date. Recomputed on every MealLog write."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_nutrition_summaries",
    )
    summary_date = models.DateField()

    calories = models.PositiveIntegerField(default=0)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Merged micronutrients from recipe cached_nutrition — custom logs contribute nothing
    micronutrients = models.JSONField(default=dict)

    meals_eaten = models.PositiveSmallIntegerField(default=0)
    meals_skipped = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = [("user", "summary_date")]
        indexes = [
            models.Index(fields=["user", "summary_date"], name="dailynutrition_user_date_idx"),
        ]

    def __str__(self) -> str:
        return f"DailyNutritionSummary({self.user_id}, {self.summary_date}, {self.calories} kcal)"
