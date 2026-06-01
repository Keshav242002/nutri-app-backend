from django.contrib import admin

from apps.mealplans.models import GroceryList, MealPlan


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ["user", "plan_date", "breakfast", "lunch", "dinner", "generated_by"]
    list_filter = ["generated_by", "plan_date"]
    search_fields = ["user__email"]
    raw_id_fields = ["user", "breakfast", "lunch", "dinner"]
    readonly_fields = ["generated_at", "regeneration_count"]
    date_hierarchy = "plan_date"
    list_per_page = 50
    list_select_related = ["user", "breakfast", "lunch", "dinner"]


@admin.register(GroceryList)
class GroceryListAdmin(admin.ModelAdmin):
    list_display = ["user", "week_start_date", "estimated_cost_inr", "generated_at"]
    list_filter = ["week_start_date"]
    search_fields = ["user__email"]
    raw_id_fields = ["user"]
    readonly_fields = ["items", "generated_at"]
