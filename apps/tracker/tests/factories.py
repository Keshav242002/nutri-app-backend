import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.tracker.models import (
    STATUS_PLANNED,
    DailyNutritionSummary,
    MealLog,
)


class MealLogFactory(DjangoModelFactory):
    class Meta:
        model = MealLog
        django_get_or_create = ("user", "log_date", "slot")

    user = factory.SubFactory(UserFactory)
    log_date = factory.LazyFunction(lambda: __import__("datetime").date(2026, 5, 30))
    slot = "lunch"
    status = STATUS_PLANNED
    servings_eaten = "1.00"


class DailyNutritionSummaryFactory(DjangoModelFactory):
    class Meta:
        model = DailyNutritionSummary
        django_get_or_create = ("user", "summary_date")

    user = factory.SubFactory(UserFactory)
    summary_date = factory.LazyFunction(lambda: __import__("datetime").date(2026, 5, 30))
    calories = 0
    protein_g = "0.00"
    carbs_g = "0.00"
    fat_g = "0.00"
    fiber_g = "0.00"
    micronutrients = factory.LazyAttribute(lambda _: {})
    meals_eaten = 0
    meals_skipped = 0
