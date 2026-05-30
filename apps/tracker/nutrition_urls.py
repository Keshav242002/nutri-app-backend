from django.urls import path

from apps.tracker import views

urlpatterns = [
    path("daily/", views.DailyNutritionView.as_view(), name="nutrition-daily"),
    path("weekly/", views.WeeklyNutritionView.as_view(), name="nutrition-weekly"),
]
