from django.contrib import admin

from apps.recipes.models import HouseholdUnit, Ingredient, Recipe, RecipeIngredient


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("app_id", "name", "category", "form", "source", "confidence", "is_active")
    list_filter = ("category", "form", "source", "confidence", "is_active")
    search_fields = ("app_id", "name", "name_hi", "ifct_code", "ifct_name")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("app_id",)


@admin.register(HouseholdUnit)
class HouseholdUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "ingredient", "grams")
    list_filter = ("name",)
    search_fields = ("name", "ingredient__name", "ingredient__app_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("ingredient", "display_unit")


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "name",
        "meal_type",
        "cuisine",
        "protein_source",
        "estimated_difficulty",
        "spice_level",
        "servings",
        "cached_calories_per_serving",
        "cost_known",
        "is_active",
        "source",
    )
    list_filter = (
        "meal_type",
        "cuisine",
        "protein_source",
        "estimated_difficulty",
        "spice_level",
        "source",
        "cost_known",
        "is_active",
    )
    search_fields = ("name", "name_alt", "slug")
    readonly_fields = (
        "cached_nutrition",
        "cached_calories_per_serving",
        "cached_cost_inr",
        "created_at",
        "updated_at",
    )
    inlines = [RecipeIngredientInline]
    ordering = ("slug",)
    date_hierarchy = "created_at"
    list_per_page = 50
    list_editable = ("is_active",)


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "quantity_grams", "order")
    search_fields = ("recipe__name", "ingredient__name", "ingredient__app_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("recipe__slug", "order")
