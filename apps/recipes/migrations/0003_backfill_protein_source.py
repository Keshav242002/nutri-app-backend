"""Backfill protein_source for existing recipes based on their ingredients.

Rules (from M3.5 plan §7.4, applied in priority order):
  1. Uses chicken_breast_raw or chicken_thigh_raw → "chicken"
  2. Uses mutton_raw → "mutton"
  3. Uses any fish/prawn ingredient (catla, pomfret, prawns, rohu) → "fish"
  4. Uses egg_whole_raw → "egg"
  5. Uses paneer_raw → "paneer"
  6. Has "high_protein" diet_tag AND uses a pulse/legume ingredient → "dal_legume"
  7. Otherwise → "none"
"""

from typing import Any

from django.db import migrations

CHICKEN_IDS = {"chicken_breast_raw", "chicken_thigh_raw"}
MUTTON_IDS = {"mutton_raw"}
FISH_IDS = {"catla_raw", "pomfret_raw", "prawns_raw", "rohu_raw"}
EGG_IDS = {"egg_whole_raw"}
PANEER_IDS = {"paneer_raw"}
PULSE_IDS = {
    "besan_raw",
    "chana_dal_raw",
    "horse_gram_raw",
    "kabuli_chana_raw",
    "kala_chana_raw",
    "lobia_raw",
    "masoor_dal_raw",
    "matki_raw",
    "moong_dal_raw",
    "moong_sprouts_raw",
    "rajma_raw",
    "toor_dal_raw",
    "urad_dal_raw",
    "whole_moong_raw",
    "whole_urad_raw",
}


def backfill_protein_source(apps: Any, schema_editor: Any) -> None:
    Recipe = apps.get_model("recipes", "Recipe")
    RecipeIngredient = apps.get_model("recipes", "RecipeIngredient")

    for recipe in Recipe.objects.all():
        ingredient_app_ids = set(
            RecipeIngredient.objects.filter(recipe=recipe)
            .select_related("ingredient")
            .values_list("ingredient__app_id", flat=True)
        )

        if ingredient_app_ids & CHICKEN_IDS:
            protein_source = "chicken"
        elif ingredient_app_ids & MUTTON_IDS:
            protein_source = "mutton"
        elif ingredient_app_ids & FISH_IDS:
            protein_source = "fish"
        elif ingredient_app_ids & EGG_IDS:
            protein_source = "egg"
        elif ingredient_app_ids & PANEER_IDS:
            protein_source = "paneer"
        elif "high_protein" in (recipe.diet_tags or []) and (ingredient_app_ids & PULSE_IDS):
            protein_source = "dal_legume"
        else:
            protein_source = "none"

        if protein_source != "none":
            recipe.protein_source = protein_source
            recipe.save(update_fields=["protein_source"])


def reverse_backfill(apps: Any, schema_editor: Any) -> None:
    """Reset all protein_source values to 'none'."""
    Recipe = apps.get_model("recipes", "Recipe")
    Recipe.objects.all().update(protein_source="none")


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0002_recipe_protein_source"),
    ]

    operations = [
        migrations.RunPython(backfill_protein_source, reverse_backfill),
    ]
