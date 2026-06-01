from django.contrib import admin

from apps.profiles.models import DietaryProfile


@admin.register(DietaryProfile)
class DietaryProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "user",
        "goal",
        "diet_pattern",
        "primary_cuisine_region",
        "activity_level",
        "target_calories",
        "timezone",
        "created_at",
    ]
    list_filter = ["goal", "diet_pattern", "primary_cuisine_region", "sex", "activity_level"]
    search_fields = ["user__email", "user__display_name"]
    raw_id_fields = ["user"]
    date_hierarchy = "created_at"
    readonly_fields = [
        "target_calories",
        "target_protein_g",
        "target_carbs_g",
        "target_fat_g",
        "target_fiber_g",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        ("Biometrics", {"fields": ("user", "sex", "date_of_birth", "height_cm", "weight_kg")}),
        ("Goals", {"fields": ("goal", "activity_level", "diet_pattern")}),
        (
            "Budget",
            {
                "fields": (
                    "daily_food_budget_inr",
                    "weekly_food_budget_inr",
                )
            },
        ),
        (
            "Computed Targets",
            {
                "fields": (
                    "target_calories",
                    "target_protein_g",
                    "target_carbs_g",
                    "target_fat_g",
                    "target_fiber_g",
                )
            },
        ),
        ("Timestamps", {"fields": ("timezone", "created_at", "updated_at")}),
    )
