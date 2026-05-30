from django.contrib import admin

from apps.tracker.models import DailyNutritionSummary, MealLog


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["user", "log_date", "slot", "status", "logged_at"]
    list_filter = ["slot", "status", "log_date"]
    search_fields = ["user__email"]
    ordering = ["-log_date"]


@admin.register(DailyNutritionSummary)
class DailyNutritionSummaryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["user", "summary_date", "calories", "meals_eaten", "meals_skipped"]
    list_filter = ["summary_date"]
    search_fields = ["user__email"]
    ordering = ["-summary_date"]
