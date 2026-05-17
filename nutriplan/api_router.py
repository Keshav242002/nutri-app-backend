from django.urls import include, path

urlpatterns = [
    path("auth/", include("apps.accounts.urls")),
]
