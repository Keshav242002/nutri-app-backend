from typing import Any

from rest_framework import serializers

from apps.recipes.models import Recipe, RecipeIngredient


class RecipeIngredientSerializer(serializers.ModelSerializer[RecipeIngredient]):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    ingredient_app_id = serializers.CharField(source="ingredient.app_id", read_only=True)
    display_unit_name = serializers.SerializerMethodField()
    display_unit_grams = serializers.SerializerMethodField()

    class Meta:
        model = RecipeIngredient
        fields = [
            "ingredient_name",
            "ingredient_app_id",
            "quantity_grams",
            "display_quantity",
            "display_unit_name",
            "display_unit_grams",
            "notes",
            "order",
        ]

    def get_display_unit_name(self, obj: RecipeIngredient) -> str | None:
        return obj.display_unit.name if obj.display_unit else None

    def get_display_unit_grams(self, obj: RecipeIngredient) -> float | None:
        return float(obj.display_unit.grams) if obj.display_unit else None


class RecipeListSerializer(serializers.ModelSerializer[Recipe]):
    cached_nutrition_summary = serializers.SerializerMethodField()
    cached_cost_per_serving_inr = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "name",
            "name_alt",
            "slug",
            "meal_type",
            "cuisine",
            "diet_tags",
            "allergen_tags",
            "prep_time_min",
            "cook_time_min",
            "servings",
            "estimated_difficulty",
            "spice_level",
            "image_url",
            "source",
            "cached_nutrition_summary",
            "cached_cost_per_serving_inr",
            "cost_known",
        ]

    def get_cached_nutrition_summary(self, obj: Recipe) -> dict[str, Any] | None:
        n = obj.cached_nutrition
        if not n:
            return None
        return {
            "calories": n.get("calories"),
            "protein_g": n.get("protein_g"),
            "carbs_g": n.get("carbs_g"),
            "fat_g": n.get("fat_g"),
            "fiber_g": n.get("fiber_g"),
        }

    def get_cached_cost_per_serving_inr(self, obj: Recipe) -> float | None:
        if obj.cached_cost_inr is None:
            return None
        servings = max(obj.servings, 1)
        return round(float(obj.cached_cost_inr) / servings, 2)


class RecipeDetailSerializer(RecipeListSerializer):
    ingredients = RecipeIngredientSerializer(source="recipe_ingredients", many=True, read_only=True)

    class Meta(RecipeListSerializer.Meta):
        fields = RecipeListSerializer.Meta.fields + [
            "ingredients",
            "instructions",
            "cached_nutrition",
            "cached_cost_inr",
        ]
