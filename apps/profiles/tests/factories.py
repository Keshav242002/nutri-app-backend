from datetime import date
from decimal import Decimal

import factory

from apps.accounts.tests.factories import UserFactory
from apps.profiles.models import DietaryProfile


class DietaryProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DietaryProfile

    user = factory.SubFactory(UserFactory)

    # Step 1 — Basics: 30-year-old male, 80kg, 180cm
    date_of_birth = factory.LazyFunction(lambda: date(1994, 6, 15))
    sex = "male"
    height_cm = 180
    weight_kg = Decimal("80.0")

    # Step 2 — Activity and goal
    activity_level = "moderate"
    goal = "maintain"

    # Step 3 — Cuisine and region
    primary_cuisine_region = "north_indian"
    secondary_cuisine_preferences = factory.LazyFunction(list)
    spice_tolerance = "medium"

    # Step 4 — Dietary pattern
    diet_pattern = "vegetarian"
    no_onion_garlic = False
    allergies = factory.LazyFunction(list)
    dislikes = factory.LazyFunction(list)

    # Step 5 — Budget and household
    daily_food_budget_inr = Decimal("150.00")
    weekly_food_budget_inr = Decimal("1050.00")
    household_size = 1
    cooking_frequency = "daily"

    # Step 6 — Cooking constraints
    max_prep_time_min = 30
    skill_level = "beginner"
