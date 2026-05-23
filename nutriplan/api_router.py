from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
    path("profiles/", include("apps.profiles.urls")),
    path("recipes/", include("apps.recipes.urls")),
]
