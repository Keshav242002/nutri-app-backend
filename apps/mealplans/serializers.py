from __future__ import annotations

from rest_framework import serializers

from apps.mealplans.models import SLOT_CHOICES, MealPlan
from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeListSerializer


class MealPlanRecipeSlimSerializer(serializers.ModelSerializer[Recipe]):
    class Meta:
        model = Recipe
        fields = [
            "id",
            "name",
            "slug",
            "meal_type",
            "cuisine",
            "prep_time_min",
            "cached_calories_per_serving",
            "image_url",
            "protein_source",
        ]


class MealPlanSerializer(serializers.ModelSerializer[MealPlan]):
    breakfast = MealPlanRecipeSlimSerializer(read_only=True)
    lunch = MealPlanRecipeSlimSerializer(read_only=True)
    dinner = MealPlanRecipeSlimSerializer(read_only=True)

    class Meta:
        model = MealPlan
        fields = [
            "id",
            "plan_date",
            "breakfast",
            "lunch",
            "dinner",
            "generated_by",
            "generated_at",
            "regeneration_count",
        ]


class MealPlanDayDetailSerializer(serializers.ModelSerializer[MealPlan]):
    breakfast = RecipeListSerializer(read_only=True)
    lunch = RecipeListSerializer(read_only=True)
    dinner = RecipeListSerializer(read_only=True)

    class Meta:
        model = MealPlan
        fields = [
            "id",
            "plan_date",
            "breakfast",
            "lunch",
            "dinner",
            "generated_by",
            "generated_at",
            "regeneration_count",
        ]


class RegenerateSlotSerializer(serializers.Serializer[None]):
    date = serializers.DateField()
    slot = serializers.ChoiceField(choices=SLOT_CHOICES)


class RegeneratePlanSerializer(serializers.Serializer[None]):
    date = serializers.DateField()
