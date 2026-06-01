from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.recipes.filters import RecipeFilter
from apps.recipes.models import Recipe
from apps.recipes.serializers import RecipeDetailSerializer, RecipeListSerializer
from core.pagination import StandardCursorPagination
from core.responses import success_response
from core.schema import envelope_list_response, envelope_response, error_response


@extend_schema(
    summary="List recipes",
    description=(
        "Cursor-paginated recipe list with up to 10 filters: "
        "meal_type, cuisine, diet_tags, allergen_exclude, difficulty, spice_level, "
        "calorie_min/max, max_cost_inr, search (name + name_alt)."
    ),
    parameters=[
        OpenApiParameter(
            "meal_type", str, description="Filter by meal type (breakfast/lunch/dinner)."
        ),
        OpenApiParameter("cuisine", str, description="Filter by cuisine region."),
        OpenApiParameter(
            "diet_tags", str, description="Comma-separated diet tags (e.g. vegetarian,vegan)."
        ),
        OpenApiParameter(
            "allergen_exclude", str, description="Comma-separated allergens to exclude."
        ),
        OpenApiParameter("difficulty", str, description="beginner / intermediate / advanced"),
        OpenApiParameter("spice_level", str, description="mild / medium / hot / very_hot"),
        OpenApiParameter("calorie_min", int, description="Minimum calories per serving."),
        OpenApiParameter("calorie_max", int, description="Maximum calories per serving."),
        OpenApiParameter("max_cost_inr", float, description="Maximum cost in INR."),
        OpenApiParameter("search", str, description="Full-text search against name and alt name."),
    ],
    responses={
        200: envelope_list_response(RecipeListSerializer, "Paginated recipe list."),
        400: error_response("INVALID_FILTER_VALUE", "Invalid filter value."),
        401: error_response("NOT_AUTHENTICATED", "No valid token."),
    },
)
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


@extend_schema(
    summary="Get recipe detail",
    description="Full recipe detail including ingredient list, household units, and cached nutrition per serving.",
    responses={
        200: envelope_response(RecipeDetailSerializer, "Recipe detail."),
        401: error_response("NOT_AUTHENTICATED", "No valid token."),
        404: error_response("NOT_FOUND", "Recipe not found or inactive."),
    },
)
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
