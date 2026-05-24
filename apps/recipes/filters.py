import django_filters
from django.db.models import DecimalField, ExpressionWrapper, F, Q, QuerySet

from apps.recipes.models import (
    CUISINE_CHOICES,
    DIFFICULTY_CHOICES,
    MEAL_TYPE_CHOICES,
    PROTEIN_SOURCE_CHOICES,
    SPICE_LEVEL_CHOICES,
    VALID_ALLERGEN_TAGS,
    VALID_DIET_TAGS,
    Recipe,
)
from core.error_codes import INVALID_FILTER_VALUE
from core.exceptions import AppValidationError


def _validate_csv_values(value: str, allowed: frozenset[str], field_name: str) -> list[str]:
    """Split a comma-separated string and validate each value against the allowed set."""
    values = [v.strip() for v in value.split(",") if v.strip()]
    invalid = [v for v in values if v not in allowed]
    if invalid:
        raise AppValidationError(
            message=f"Invalid {field_name} value(s): {', '.join(invalid)}",
            code=INVALID_FILTER_VALUE,
            details={
                "field": field_name,
                "invalid_values": invalid,
                "allowed_values": sorted(allowed),
            },
        )
    return values


def _validate_choice_value(value: str, choices: list[tuple[str, str]], field_name: str) -> str:
    """Validate a single value against a choices list."""
    allowed = frozenset(k for k, _ in choices)
    if value not in allowed:
        raise AppValidationError(
            message=f"Invalid {field_name} value: {value}",
            code=INVALID_FILTER_VALUE,
            details={
                "field": field_name,
                "invalid_values": [value],
                "allowed_values": sorted(allowed),
            },
        )
    return value


class RecipeFilter(django_filters.FilterSet):  # type: ignore[misc]
    meal_type = django_filters.CharFilter(method="filter_meal_type")
    cuisine = django_filters.CharFilter(method="filter_cuisine")
    estimated_difficulty = django_filters.CharFilter(method="filter_estimated_difficulty")
    spice_level = django_filters.CharFilter(method="filter_spice_level")
    protein_source = django_filters.CharFilter(method="filter_protein_source")
    max_prep_time = django_filters.NumberFilter(field_name="prep_time_min", lookup_expr="lte")

    diet_tags = django_filters.CharFilter(method="filter_diet_tags")
    exclude_allergens = django_filters.CharFilter(method="filter_exclude_allergens")
    search = django_filters.CharFilter(method="filter_search")
    max_cost_per_serving_inr = django_filters.NumberFilter(method="filter_max_cost")
    includes_ingredients = django_filters.CharFilter(method="filter_includes_ingredients")
    excludes_ingredients = django_filters.CharFilter(method="filter_excludes_ingredients")

    class Meta:
        model = Recipe
        fields: list[str] = []

    # ------------------------------------------------------------------
    # Choice-validated single-value filters
    # ------------------------------------------------------------------

    def filter_meal_type(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        _validate_choice_value(value, MEAL_TYPE_CHOICES, "meal_type")
        return queryset.filter(meal_type=value)

    def filter_cuisine(self, queryset: QuerySet[Recipe], name: str, value: str) -> QuerySet[Recipe]:
        _validate_choice_value(value, CUISINE_CHOICES, "cuisine")
        return queryset.filter(cuisine=value)

    def filter_estimated_difficulty(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        _validate_choice_value(value, DIFFICULTY_CHOICES, "estimated_difficulty")
        return queryset.filter(estimated_difficulty=value)

    def filter_spice_level(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        _validate_choice_value(value, SPICE_LEVEL_CHOICES, "spice_level")
        return queryset.filter(spice_level=value)

    def filter_protein_source(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        _validate_choice_value(value, PROTEIN_SOURCE_CHOICES, "protein_source")
        return queryset.filter(protein_source=value)

    # ------------------------------------------------------------------
    # Vocab-validated comma-separated filters
    # ------------------------------------------------------------------

    def filter_diet_tags(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        tags = _validate_csv_values(value, VALID_DIET_TAGS, "diet_tags")
        if tags:
            queryset = queryset.filter(diet_tags__contains=tags)
        return queryset

    def filter_exclude_allergens(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        allergens = _validate_csv_values(value, VALID_ALLERGEN_TAGS, "exclude_allergens")
        if allergens:
            queryset = queryset.exclude(allergen_tags__overlap=allergens)
        return queryset

    # ------------------------------------------------------------------
    # Non-vocab filters (no validation needed beyond type)
    # ------------------------------------------------------------------

    def filter_search(self, queryset: QuerySet[Recipe], name: str, value: str) -> QuerySet[Recipe]:
        return queryset.filter(Q(name__icontains=value) | Q(name_alt__icontains=value))

    def filter_max_cost(
        self, queryset: QuerySet[Recipe], name: str, value: float
    ) -> QuerySet[Recipe]:
        return (
            queryset.filter(cost_known=True)
            .annotate(
                cost_per_serving=ExpressionWrapper(
                    F("cached_cost_inr") / F("servings"),
                    output_field=DecimalField(),
                )
            )
            .filter(cost_per_serving__lte=value)
        )

    def filter_includes_ingredients(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        app_ids = [a.strip() for a in value.split(",") if a.strip()]
        for app_id in app_ids:
            queryset = queryset.filter(recipe_ingredients__ingredient__app_id=app_id)
        return queryset.distinct()

    def filter_excludes_ingredients(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        app_ids = [a.strip() for a in value.split(",") if a.strip()]
        if app_ids:
            queryset = queryset.exclude(recipe_ingredients__ingredient__app_id__in=app_ids)
        return queryset
