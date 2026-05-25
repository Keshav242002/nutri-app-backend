import pytest
from django.db import IntegrityError

from apps.mealplans.models import MealPlan
from apps.mealplans.tests.factories import MealPlanFactory
from apps.recipes.tests.factories import RecipeFactory


@pytest.mark.django_db
class TestMealPlanStr:
    def test_mealplan_str_representation(self) -> None:
        plan = MealPlanFactory()
        assert str(plan) == f"MealPlan({plan.user_id}, {plan.plan_date})"


@pytest.mark.django_db
class TestMealPlanUniqueConstraint:
    def test_mealplan_unique_together_user_plan_date(self) -> None:
        plan = MealPlanFactory()
        with pytest.raises(IntegrityError):
            MealPlan.objects.create(user=plan.user, plan_date=plan.plan_date)


@pytest.mark.django_db
class TestMealPlanOnDelete:
    def test_mealplan_set_null_on_recipe_delete(self) -> None:
        recipe = RecipeFactory()
        plan = MealPlanFactory(breakfast=recipe)
        recipe.delete()
        plan.refresh_from_db()
        assert plan.breakfast is None

    def test_mealplan_cascade_on_user_delete(self) -> None:
        plan = MealPlanFactory()
        user_id = plan.user_id
        plan.user.delete()
        assert not MealPlan.objects.filter(user_id=user_id).exists()


@pytest.mark.django_db
class TestMealPlanDefaults:
    def test_mealplan_regeneration_count_default(self) -> None:
        plan = MealPlanFactory(regeneration_count={"breakfast": 0, "lunch": 0, "dinner": 0})
        assert plan.regeneration_count == {"breakfast": 0, "lunch": 0, "dinner": 0}

    def test_mealplan_full_plan_regenerations_default_zero(self) -> None:
        plan = MealPlanFactory()
        assert plan.full_plan_regenerations == 0
