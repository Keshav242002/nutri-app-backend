from django.urls import path

from apps.tracker import views

urlpatterns = [
    path("log/", views.MealLogView.as_view(), name="tracker-log"),
    path("", views.TrackerListView.as_view(), name="tracker-list"),
    path("range/", views.TrackerRangeView.as_view(), name="tracker-range"),
]
