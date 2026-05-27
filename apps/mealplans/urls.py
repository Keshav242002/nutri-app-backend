from django.urls import path

from apps.mealplans.views import (
    DayMealPlanView,
    GroceryListRegenerateView,
    GroceryListView,
    RegeneratePlanView,
    RegenerateSlotView,
    TodayMealPlanView,
    WeeklyPlanGenerateView,
    WeekMealPlanView,
)

urlpatterns = [
    path("today/", TodayMealPlanView.as_view(), name="mealplan-today"),
    path("day/<str:plan_date>/", DayMealPlanView.as_view(), name="mealplan-day"),
    path("week/", WeekMealPlanView.as_view(), name="mealplan-week"),
    path("week/generate/", WeeklyPlanGenerateView.as_view(), name="mealplan-week-generate"),
    path(
        "week/<str:plan_date>/grocery/",
        GroceryListView.as_view(),
        name="mealplan-grocery",
    ),
    path(
        "week/<str:plan_date>/grocery/regenerate/",
        GroceryListRegenerateView.as_view(),
        name="mealplan-grocery-regenerate",
    ),
    path("regenerate-slot/", RegenerateSlotView.as_view(), name="mealplan-regenerate-slot"),
    path("regenerate/", RegeneratePlanView.as_view(), name="mealplan-regenerate"),
]
