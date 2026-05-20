from django.contrib import admin

from apps.profiles.models import DietaryProfile


@admin.register(DietaryProfile)
class DietaryProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["user", "goal", "diet_pattern", "primary_cuisine_region", "created_at"]
    list_filter = ["goal", "diet_pattern", "primary_cuisine_region", "sex"]
    raw_id_fields = ["user"]
    readonly_fields = [
        "target_calories",
        "target_protein_g",
        "target_carbs_g",
        "target_fat_g",
        "target_fiber_g",
        "created_at",
        "updated_at",
    ]
