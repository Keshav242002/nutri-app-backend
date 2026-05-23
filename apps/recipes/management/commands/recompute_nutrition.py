from typing import Any

from django.core.management.base import BaseCommand

from apps.recipes.models import Recipe
from apps.recipes.services.nutrition import compute_recipe_nutrition


class Command(BaseCommand):
    help = "Recompute cached nutrition for all active recipes."

    def handle(self, *args: Any, **options: Any) -> None:
        recipes = list(Recipe.objects.filter(is_active=True))
        if not recipes:
            self.stdout.write("No active recipes found.")
            return

        calories_values: list[int] = []
        for recipe in recipes:
            nutrition = compute_recipe_nutrition(recipe)
            cal = nutrition.get("calories", 0)
            if isinstance(cal, int):
                calories_values.append(cal)

        processed = len(recipes)
        if calories_values:
            avg = sum(calories_values) / len(calories_values)
            self.stdout.write(
                f"Recomputed {processed} recipes. "
                f"Calories/serving: min={min(calories_values)}, "
                f"max={max(calories_values)}, "
                f"avg={avg:.0f}"
            )
        else:
            self.stdout.write(f"Recomputed {processed} recipes.")

        self.stdout.write(self.style.SUCCESS("Done."))
