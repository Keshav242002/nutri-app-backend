from django.urls import path

from apps.mealplans.views import (
    DayMealPlanView,
    RegeneratePlanView,
    RegenerateSlotView,
    TodayMealPlanView,
    WeekMealPlanView,
)

urlpatterns = [
    path("today/", TodayMealPlanView.as_view(), name="mealplan-today"),
    path("day/<str:plan_date>/", DayMealPlanView.as_view(), name="mealplan-day"),
    path("week/", WeekMealPlanView.as_view(), name="mealplan-week"),
    path("regenerate-slot/", RegenerateSlotView.as_view(), name="mealplan-regenerate-slot"),
    path("regenerate/", RegeneratePlanView.as_view(), name="mealplan-regenerate"),
]
