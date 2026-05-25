from datetime import date

import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.mealplans.models import GEN_BY_RULES, MealPlan


class MealPlanFactory(DjangoModelFactory):
    class Meta:
        model = MealPlan
        django_get_or_create = ("user", "plan_date")

    user = factory.SubFactory(UserFactory)
    plan_date = factory.LazyFunction(lambda: date(2026, 5, 26))
    breakfast = None
    lunch = None
    dinner = None
    generated_by = GEN_BY_RULES
    regeneration_count = factory.LazyAttribute(lambda _: {"breakfast": 0, "lunch": 0, "dinner": 0})
    full_plan_regenerations = 0
