from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("recipes/", include("apps.recipes.urls")),
    path("mealplans/", include("apps.mealplans.urls")),
    path("tracker/", include("apps.tracker.urls")),
    path("nutrition/", include("apps.tracker.nutrition_urls")),
]
