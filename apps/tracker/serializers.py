from __future__ import annotations

from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.tracker.models import SLOT_CHOICES, STATUS_CHOICES, DailyNutritionSummary, MealLog


class SlimRecipeSerializer(serializers.Serializer[None]):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    cached_calories_per_serving = serializers.IntegerField()


class MealLogSerializer(serializers.Serializer[None]):
    """Input serializer for POST /api/v1/tracker/log/"""

    log_date = serializers.DateField()
    slot = serializers.ChoiceField(choices=SLOT_CHOICES)
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    planned_recipe_id = serializers.IntegerField(required=False, allow_null=True)
    actual_recipe_id = serializers.IntegerField(required=False, allow_null=True)
    servings_eaten = serializers.DecimalField(
        max_digits=4, decimal_places=2, required=False, allow_null=True, min_value=Decimal("0.01")
    )
    custom_description = serializers.CharField(max_length=200, required=False, allow_null=True)
    custom_calories = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    custom_protein_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    custom_carbs_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    custom_fat_g = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False, allow_null=True
    )
    notes = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)


class MealLogResponseSerializer(serializers.ModelSerializer[MealLog]):
    """Output serializer for MealLog with nested slim recipe info."""

    planned_recipe = SlimRecipeSerializer(read_only=True)
    actual_recipe = SlimRecipeSerializer(read_only=True)

    class Meta:
        model = MealLog
        fields = [
            "id",
            "log_date",
            "slot",
            "status",
            "planned_recipe",
            "actual_recipe",
            "servings_eaten",
            "custom_description",
            "custom_calories",
            "custom_protein_g",
            "custom_carbs_g",
            "custom_fat_g",
            "notes",
            "logged_at",
        ]


class DailyNutritionSerializer(serializers.ModelSerializer[DailyNutritionSummary]):
    """Output serializer with targets from profile and percentage_of_target computed."""

    totals = serializers.SerializerMethodField()
    targets = serializers.SerializerMethodField()
    percentage_of_target = serializers.SerializerMethodField()
    date = serializers.DateField(source="summary_date")

    class Meta:
        model = DailyNutritionSummary
        fields = [
            "date",
            "totals",
            "targets",
            "percentage_of_target",
            "meals_eaten",
            "meals_skipped",
        ]

    def get_totals(self, obj: DailyNutritionSummary) -> dict[str, Any]:
        return {
            "calories": obj.calories,
            "protein_g": float(obj.protein_g),
            "carbs_g": float(obj.carbs_g),
            "fat_g": float(obj.fat_g),
            "fiber_g": float(obj.fiber_g),
            "micronutrients": obj.micronutrients,
        }

    def get_targets(self, obj: DailyNutritionSummary) -> dict[str, Any] | None:
        profile = self.context.get("profile")
        if profile is None:
            return None
        return {
            "calories": profile.target_calories,
            "protein_g": float(profile.target_protein_g),
            "carbs_g": float(profile.target_carbs_g),
            "fat_g": float(profile.target_fat_g),
            "fiber_g": float(profile.target_fiber_g),
        }

    def get_percentage_of_target(self, obj: DailyNutritionSummary) -> dict[str, Any] | None:
        profile = self.context.get("profile")
        if profile is None:
            return None

        def _pct(actual: float, target: float) -> float:
            if target == 0:
                return 0.0
            return round(actual / target * 100, 1)

        return {
            "calories": _pct(obj.calories, profile.target_calories or 0),
            "protein_g": _pct(float(obj.protein_g), float(profile.target_protein_g or 0)),
            "carbs_g": _pct(float(obj.carbs_g), float(profile.target_carbs_g or 0)),
            "fat_g": _pct(float(obj.fat_g), float(profile.target_fat_g or 0)),
            "fiber_g": _pct(float(obj.fiber_g), float(profile.target_fiber_g or 0)),
        }


class WeeklyNutritionSerializer(serializers.Serializer[None]):
    """Output serializer for weekly summaries with computed averages."""

    days = serializers.SerializerMethodField()
    averages = serializers.SerializerMethodField()

    def __init__(self, summaries: list[DailyNutritionSummary], profile: Any, **kwargs: Any):
        super().__init__(instance=None, **kwargs)
        self._summaries = summaries
        self._profile = profile

    def get_days(self, obj: None) -> list[dict[str, Any]]:
        return [
            DailyNutritionSerializer(s, context={"profile": self._profile}).data
            for s in self._summaries
        ]

    def get_averages(self, obj: None) -> dict[str, Any]:
        if not self._summaries:
            return {}
        n = len(self._summaries)
        return {
            "calories": round(sum(s.calories for s in self._summaries) / n),
            "protein_g": round(sum(float(s.protein_g) for s in self._summaries) / n, 1),
            "carbs_g": round(sum(float(s.carbs_g) for s in self._summaries) / n, 1),
            "fat_g": round(sum(float(s.fat_g) for s in self._summaries) / n, 1),
            "fiber_g": round(sum(float(s.fiber_g) for s in self._summaries) / n, 1),
        }

    @property
    def data(self) -> dict[str, Any]:  # type: ignore[override]
        return {
            "days": self.get_days(None),
            "averages": self.get_averages(None),
        }
