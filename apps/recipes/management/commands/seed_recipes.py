from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.recipes.services.seed import seed_household_units, seed_ingredients, seed_recipes

_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "seed_data"


class Command(BaseCommand):
    help = "Seed ingredients, household units, and recipes from JSON files (idempotent)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--ingredients-path",
            type=Path,
            default=_SEED_DIR / "ingredients.json",
            help="Path to ingredients.json seed file.",
        )
        parser.add_argument(
            "--household-units-path",
            type=Path,
            default=_SEED_DIR / "household_units.json",
            help="Path to household_units.json seed file.",
        )
        parser.add_argument(
            "--recipes-path",
            type=Path,
            default=_SEED_DIR / "recipes.json",
            help="Path to recipes.json seed file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        ingredients_path: Path = options["ingredients_path"]
        household_units_path: Path = options["household_units_path"]
        recipes_path: Path = options["recipes_path"]

        with transaction.atomic():
            ing_created, ing_updated = seed_ingredients(ingredients_path)
            self.stdout.write(
                f"Ingredients: {ing_created} created, {ing_updated} updated "
                f"(total {ing_created + ing_updated})"
            )

            hu_created, hu_updated = seed_household_units(household_units_path)
            self.stdout.write(
                f"Household units: {hu_created} created, {hu_updated} updated "
                f"(total {hu_created + hu_updated})"
            )

            r_created, r_updated = seed_recipes(recipes_path)
            self.stdout.write(
                f"Recipes: {r_created} created, {r_updated} updated "
                f"(total {r_created + r_updated})"
            )

        self.stdout.write(self.style.SUCCESS("Seed completed successfully."))
