from django.contrib import admin

from apps.mealplans.models import MealPlan


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ["user", "plan_date", "breakfast", "lunch", "dinner", "generated_by"]
    list_filter = ["generated_by", "plan_date"]
    search_fields = ["user__email"]
    raw_id_fields = ["user", "breakfast", "lunch", "dinner"]
    readonly_fields = ["generated_at", "regeneration_count"]
