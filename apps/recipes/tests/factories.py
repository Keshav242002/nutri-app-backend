import factory
from factory.django import DjangoModelFactory

from apps.recipes.models import (
    CATEGORY_GRAIN,
    CONFIDENCE_EXACT,
    CUISINE_NORTH_INDIAN,
    DIFFICULTY_INTERMEDIATE,
    FORM_RAW,
    MEAL_TYPE_LUNCH,
    PROTEIN_SOURCE_NONE,
    RECIPE_SOURCE_SEED,
    SOURCE_IFCT,
    SPICE_MEDIUM,
    HouseholdUnit,
    Ingredient,
    Recipe,
    RecipeIngredient,
)


class IngredientFactory(DjangoModelFactory):
    class Meta:
        model = Ingredient
        django_get_or_create = ("app_id",)

    app_id = factory.Sequence(lambda n: f"ingredient_{n}_raw")
    name = factory.Sequence(lambda n: f"Ingredient {n}")
    category = CATEGORY_GRAIN
    form = FORM_RAW
    cooked_yield_ratio = "1.00"
    source = SOURCE_IFCT
    confidence = CONFIDENCE_EXACT
    per_100g_nutrition = factory.LazyAttribute(
        lambda _: {
            "calories": 350,
            "protein_g": 7.0,
            "carbs_g": 76.0,
            "fat_g": 1.0,
            "fiber_g": 2.8,
            "micronutrients": {
                "iron_mg": 0.7,
                "calcium_mg": 10.0,
                "vit_c_mg": 0.0,
                "potassium_mg": 115.0,
                "sodium_mg": 5.0,
                "magnesium_mg": 25.0,
                "zinc_mg": 1.1,
                "vit_a_iu": 0.0,
                "folate_ug": 8.0,
                "vit_b12_ug": None,
            },
        }
    )


class HouseholdUnitFactory(DjangoModelFactory):
    class Meta:
        model = HouseholdUnit
        django_get_or_create = ("name", "ingredient")

    name = factory.Sequence(lambda n: f"unit_{n}")
    ingredient = factory.SubFactory(IngredientFactory)
    grams = "150.00"


class RecipeFactory(DjangoModelFactory):
    class Meta:
        model = Recipe
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Recipe {n}")
    slug = factory.Sequence(lambda n: f"recipe-{n}")
    meal_type = MEAL_TYPE_LUNCH
    cuisine = CUISINE_NORTH_INDIAN
    source = RECIPE_SOURCE_SEED
    servings = 2
    prep_time_min = 10
    cook_time_min = 20
    estimated_difficulty = DIFFICULTY_INTERMEDIATE
    spice_level = SPICE_MEDIUM
    protein_source = PROTEIN_SOURCE_NONE
    instructions = factory.LazyAttribute(lambda _: ["Step 1", "Step 2"])
    diet_tags = factory.LazyAttribute(lambda _: ["vegetarian"])
    allergen_tags = factory.LazyAttribute(lambda _: [])


class RecipeIngredientFactory(DjangoModelFactory):
    class Meta:
        model = RecipeIngredient
        django_get_or_create = ("recipe", "ingredient")

    recipe = factory.SubFactory(RecipeFactory)
    ingredient = factory.SubFactory(IngredientFactory)
    order = factory.Sequence(lambda n: n)
    quantity_grams = "100.00"
