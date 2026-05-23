from django.urls import path

from apps.recipes.views import RecipeDetailView, RecipeListView

urlpatterns = [
    path("", RecipeListView.as_view(), name="recipe-list"),
    path("<slug:slug>/", RecipeDetailView.as_view(), name="recipe-detail"),
]
