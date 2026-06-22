from __future__ import annotations

from rest_framework import serializers

from apps.mealplans.models import SLOT_CHOICES, GroceryList, MealPlan
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
    # When True, return a candidate recipe for the slot WITHOUT persisting it.
    preview = serializers.BooleanField(default=False)
    # On a commit, the id of the previously-previewed recipe to persist. When
    # omitted, the slot is re-rolled and persisted (legacy single-shot behavior).
    recipe_id = serializers.IntegerField(required=False)


class RegeneratePlanSerializer(serializers.Serializer[None]):
    date = serializers.DateField()


class WeeklyPlanGenerateSerializer(serializers.Serializer[None]):
    date = serializers.DateField(required=False)


class GroceryItemSerializer(serializers.Serializer[None]):
    ingredient_app_id = serializers.CharField()
    ingredient_name = serializers.CharField()
    total_grams = serializers.FloatField()
    display_quantity = serializers.CharField()
    display_quantity_value = serializers.FloatField()
    display_unit = serializers.CharField()
    estimated_cost_inr = serializers.FloatField(allow_null=True)
    recipe_count = serializers.IntegerField()
    pantry_staple = serializers.BooleanField()
    notes = serializers.CharField()


class GroceryCategorySerializer(serializers.Serializer[None]):
    category = serializers.CharField()
    category_display = serializers.CharField()
    items = GroceryItemSerializer(many=True)


class GroceryListSerializer(serializers.ModelSerializer[GroceryList]):
    categories = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()

    class Meta:
        model = GroceryList
        fields = [
            "id",
            "week_start_date",
            "categories",
            "summary",
            "estimated_cost_inr",
            "generated_at",
        ]

    def get_categories(self, obj: GroceryList) -> list[dict]:  # type: ignore[type-arg]
        return obj.items.get("categories", [])  # type: ignore[no-any-return]

    def get_summary(self, obj: GroceryList) -> dict:  # type: ignore[type-arg]
        return obj.items.get("summary", {})  # type: ignore[no-any-return]
