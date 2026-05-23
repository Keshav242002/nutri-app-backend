import django_filters
from django.db.models import DecimalField, ExpressionWrapper, F, Q, QuerySet

from apps.recipes.models import Recipe


class RecipeFilter(django_filters.FilterSet):  # type: ignore[misc]
    meal_type = django_filters.CharFilter(field_name="meal_type", lookup_expr="exact")
    cuisine = django_filters.CharFilter(field_name="cuisine", lookup_expr="exact")
    estimated_difficulty = django_filters.CharFilter(
        field_name="estimated_difficulty", lookup_expr="exact"
    )
    spice_level = django_filters.CharFilter(field_name="spice_level", lookup_expr="exact")
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

    def filter_diet_tags(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        tags = [t.strip() for t in value.split(",") if t.strip()]
        if tags:
            queryset = queryset.filter(diet_tags__contains=tags)
        return queryset

    def filter_exclude_allergens(
        self, queryset: QuerySet[Recipe], name: str, value: str
    ) -> QuerySet[Recipe]:
        allergens = [a.strip() for a in value.split(",") if a.strip()]
        if allergens:
            queryset = queryset.exclude(allergen_tags__overlap=allergens)
        return queryset

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
