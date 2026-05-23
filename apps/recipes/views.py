from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recipes.filters import RecipeFilter
from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeDetailSerializer, RecipeListSerializer
from core.pagination import StandardCursorPagination
from core.responses import success_response


class RecipeListView(ListAPIView[Recipe]):
    serializer_class = RecipeListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def get_queryset(self) -> QuerySet[Recipe]:
        return Recipe.objects.filter(is_active=True)

    def list(self, request: Request, *args: object, **kwargs: object) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_data = self.get_paginated_response(serializer.data).data
            return success_response(paginated_data, "Recipes retrieved.")
        serializer = self.get_serializer(queryset, many=True)
        return success_response({"results": serializer.data}, "Recipes retrieved.")


class RecipeDetailView(RetrieveAPIView[Recipe]):
    serializer_class = RecipeDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self) -> QuerySet[Recipe]:
        return Recipe.objects.filter(is_active=True).prefetch_related(
            "recipe_ingredients__ingredient",
            "recipe_ingredients__display_unit",
        )

    def retrieve(self, request: Request, *args: object, **kwargs: object) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response(serializer.data, "Recipe retrieved.")
