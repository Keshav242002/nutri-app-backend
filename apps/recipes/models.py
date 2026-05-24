from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.mixins import TimestampedModel

# ---------------------------------------------------------------------------
# Ingredient choice constants
# ---------------------------------------------------------------------------

CATEGORY_GRAIN = "grain"
CATEGORY_PULSE = "pulse"
CATEGORY_VEGETABLE = "vegetable"
CATEGORY_FRUIT = "fruit"
CATEGORY_DAIRY = "dairy"
CATEGORY_MEAT = "meat"
CATEGORY_FISH = "fish"
CATEGORY_EGG = "egg"
CATEGORY_OIL_FAT = "oil_fat"
CATEGORY_SPICE = "spice"
CATEGORY_NUT_SEED = "nut_seed"
CATEGORY_SWEETENER = "sweetener"
CATEGORY_BEVERAGE = "beverage"
CATEGORY_PROCESSED = "processed"

CATEGORY_CHOICES = [
    (CATEGORY_GRAIN, "Grain"),
    (CATEGORY_PULSE, "Pulse"),
    (CATEGORY_VEGETABLE, "Vegetable"),
    (CATEGORY_FRUIT, "Fruit"),
    (CATEGORY_DAIRY, "Dairy"),
    (CATEGORY_MEAT, "Meat"),
    (CATEGORY_FISH, "Fish"),
    (CATEGORY_EGG, "Egg"),
    (CATEGORY_OIL_FAT, "Oil / Fat"),
    (CATEGORY_SPICE, "Spice"),
    (CATEGORY_NUT_SEED, "Nut / Seed"),
    (CATEGORY_SWEETENER, "Sweetener"),
    (CATEGORY_BEVERAGE, "Beverage"),
    (CATEGORY_PROCESSED, "Processed"),
]

FORM_RAW = "raw"
FORM_COOKED = "cooked"
FORM_AS_EATEN = "as_eaten"

FORM_CHOICES = [
    (FORM_RAW, "Raw"),
    (FORM_COOKED, "Cooked"),
    (FORM_AS_EATEN, "As Eaten"),
]

SOURCE_IFCT = "ifct"
SOURCE_USDA = "usda"
SOURCE_MANUAL = "manual"
SOURCE_COMPOSED = "composed"

SOURCE_CHOICES = [
    (SOURCE_IFCT, "IFCT 2017"),
    (SOURCE_USDA, "USDA FDC"),
    (SOURCE_MANUAL, "Manual"),
    (SOURCE_COMPOSED, "Composed"),
]

CONFIDENCE_EXACT = "exact"
CONFIDENCE_GOOD = "good"
CONFIDENCE_APPROXIMATE = "approximate"
CONFIDENCE_WEAK = "weak"

CONFIDENCE_CHOICES = [
    (CONFIDENCE_EXACT, "Exact"),
    (CONFIDENCE_GOOD, "Good"),
    (CONFIDENCE_APPROXIMATE, "Approximate"),
    (CONFIDENCE_WEAK, "Weak"),
]

ALLERGEN_DAIRY = "dairy"
ALLERGEN_EGGS = "eggs"
ALLERGEN_GLUTEN = "gluten"
ALLERGEN_PEANUTS = "peanuts"
ALLERGEN_TREE_NUTS = "tree_nuts"
ALLERGEN_SOY = "soy"
ALLERGEN_SHELLFISH = "shellfish"
ALLERGEN_FISH = "fish"
ALLERGEN_SESAME = "sesame"
ALLERGEN_MUSTARD = "mustard"

ALLERGEN_CHOICES = [
    (ALLERGEN_DAIRY, "Dairy"),
    (ALLERGEN_EGGS, "Eggs"),
    (ALLERGEN_GLUTEN, "Gluten"),
    (ALLERGEN_PEANUTS, "Peanuts"),
    (ALLERGEN_TREE_NUTS, "Tree Nuts"),
    (ALLERGEN_SOY, "Soy"),
    (ALLERGEN_SHELLFISH, "Shellfish"),
    (ALLERGEN_FISH, "Fish"),
    (ALLERGEN_SESAME, "Sesame"),
    (ALLERGEN_MUSTARD, "Mustard"),
]

VALID_ALLERGEN_TAGS = frozenset(tag for tag, _ in ALLERGEN_CHOICES)

# ---------------------------------------------------------------------------
# Recipe choice constants
# ---------------------------------------------------------------------------

MEAL_TYPE_BREAKFAST = "breakfast"
MEAL_TYPE_LUNCH = "lunch"
MEAL_TYPE_DINNER = "dinner"

MEAL_TYPE_CHOICES = [
    (MEAL_TYPE_BREAKFAST, "Breakfast"),
    (MEAL_TYPE_LUNCH, "Lunch"),
    (MEAL_TYPE_DINNER, "Dinner"),
]

CUISINE_NORTH_INDIAN = "north_indian"
CUISINE_SOUTH_INDIAN = "south_indian"
CUISINE_EAST_INDIAN = "east_indian"
CUISINE_WEST_INDIAN = "west_indian"
CUISINE_PUNJABI = "punjabi"
CUISINE_GUJARATI = "gujarati"
CUISINE_MAHARASHTRIAN = "maharashtrian"
CUISINE_BENGALI = "bengali"
CUISINE_TAMIL = "tamil"
CUISINE_KERALA = "kerala"
CUISINE_ANDHRA = "andhra"
CUISINE_RAJASTHANI = "rajasthani"
CUISINE_GOAN = "goan"
CUISINE_SINDHI = "sindhi"
CUISINE_CONTINENTAL = "continental"
CUISINE_CHINESE_INDO = "chinese_indo"
CUISINE_PAN_ASIAN = "pan_asian"

CUISINE_CHOICES = [
    (CUISINE_NORTH_INDIAN, "North Indian"),
    (CUISINE_SOUTH_INDIAN, "South Indian"),
    (CUISINE_EAST_INDIAN, "East Indian"),
    (CUISINE_WEST_INDIAN, "West Indian"),
    (CUISINE_PUNJABI, "Punjabi"),
    (CUISINE_GUJARATI, "Gujarati"),
    (CUISINE_MAHARASHTRIAN, "Maharashtrian"),
    (CUISINE_BENGALI, "Bengali"),
    (CUISINE_TAMIL, "Tamil"),
    (CUISINE_KERALA, "Kerala"),
    (CUISINE_ANDHRA, "Andhra"),
    (CUISINE_RAJASTHANI, "Rajasthani"),
    (CUISINE_GOAN, "Goan"),
    (CUISINE_SINDHI, "Sindhi"),
    (CUISINE_CONTINENTAL, "Continental"),
    (CUISINE_CHINESE_INDO, "Indo-Chinese"),
    (CUISINE_PAN_ASIAN, "Pan-Asian"),
]

DIET_TAG_CHOICES = [
    ("vegan", "Vegan"),
    ("vegetarian", "Vegetarian"),
    ("pescatarian", "Pescatarian"),
    ("eggetarian", "Eggetarian"),
    ("gluten_free", "Gluten-Free"),
    ("dairy_free", "Dairy-Free"),
    ("nut_free", "Nut-Free"),
    ("low_carb", "Low Carb"),
    ("high_protein", "High Protein"),
    ("jain", "Jain"),
    ("satvik", "Satvik"),
    ("keto", "Keto"),
    ("mediterranean", "Mediterranean"),
]

VALID_DIET_TAGS = frozenset(tag for tag, _ in DIET_TAG_CHOICES)

RECIPE_SOURCE_SEED = "seed"
RECIPE_SOURCE_AI = "ai_generated"
RECIPE_SOURCE_USER = "user_custom"

RECIPE_SOURCE_CHOICES = [
    (RECIPE_SOURCE_SEED, "Seed"),
    (RECIPE_SOURCE_AI, "AI Generated"),
    (RECIPE_SOURCE_USER, "User Custom"),
]

DIFFICULTY_BEGINNER = "beginner"
DIFFICULTY_INTERMEDIATE = "intermediate"
DIFFICULTY_ADVANCED = "advanced"

DIFFICULTY_CHOICES = [
    (DIFFICULTY_BEGINNER, "Beginner"),
    (DIFFICULTY_INTERMEDIATE, "Intermediate"),
    (DIFFICULTY_ADVANCED, "Advanced"),
]

SPICE_MILD = "mild"
SPICE_MEDIUM = "medium"
SPICE_HOT = "hot"
SPICE_VERY_HOT = "very_hot"

SPICE_LEVEL_CHOICES = [
    (SPICE_MILD, "Mild"),
    (SPICE_MEDIUM, "Medium"),
    (SPICE_HOT, "Hot"),
    (SPICE_VERY_HOT, "Very Hot"),
]

PROTEIN_SOURCE_PANEER = "paneer"
PROTEIN_SOURCE_DAL = "dal_legume"
PROTEIN_SOURCE_EGG = "egg"
PROTEIN_SOURCE_CHICKEN = "chicken"
PROTEIN_SOURCE_MUTTON = "mutton"
PROTEIN_SOURCE_FISH = "fish"
PROTEIN_SOURCE_SOY = "soy"
PROTEIN_SOURCE_NONE = "none"

PROTEIN_SOURCE_CHOICES = [
    (PROTEIN_SOURCE_PANEER, "Paneer"),
    (PROTEIN_SOURCE_DAL, "Dal / Legume"),
    (PROTEIN_SOURCE_EGG, "Egg"),
    (PROTEIN_SOURCE_CHICKEN, "Chicken"),
    (PROTEIN_SOURCE_MUTTON, "Mutton"),
    (PROTEIN_SOURCE_FISH, "Fish / Seafood"),
    (PROTEIN_SOURCE_SOY, "Soy / Tofu"),
    (PROTEIN_SOURCE_NONE, "None"),
]

VALID_PROTEIN_SOURCES = frozenset(tag for tag, _ in PROTEIN_SOURCE_CHOICES)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Ingredient(TimestampedModel):
    """A single food ingredient with IFCT/USDA nutritional data per 100g raw weight."""

    app_id = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200, unique=True)
    name_hi = models.CharField(max_length=200, blank=True, default="")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    per_100g_nutrition = models.JSONField()
    approximate_price_inr_per_kg = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    price_as_of_month = models.CharField(max_length=7, blank=True, default="")
    allergen_tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    is_active = models.BooleanField(default=True)
    form = models.CharField(max_length=20, choices=FORM_CHOICES)
    cooked_yield_ratio = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.10")), MaxValueValidator(Decimal("10.00"))],
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    ifct_code = models.CharField(max_length=10, blank=True, default="")
    ifct_name = models.CharField(max_length=200, blank=True, default="")
    ifct_regn = models.PositiveSmallIntegerField(null=True, blank=True)
    usda_fdc_id = models.IntegerField(null=True, blank=True)
    usda_description = models.CharField(max_length=200, blank=True, default="")
    package_version = models.CharField(max_length=60, blank=True, default="")
    extracted_at = models.DateField(null=True, blank=True)
    confidence = models.CharField(max_length=20, choices=CONFIDENCE_CHOICES, blank=True, default="")
    overlays = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["category"]),
            GinIndex(fields=["allergen_tags"], name="ingredient_allergen_gin"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.app_id})"


class HouseholdUnit(TimestampedModel):
    """Maps a named household measure (katori, roti, tbsp) to a gram weight for an ingredient."""

    name = models.CharField(max_length=50)
    ingredient = models.ForeignKey(
        Ingredient,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="household_units_set",
    )
    grams = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        unique_together = [("name", "ingredient")]

    def __str__(self) -> str:
        ing = self.ingredient
        suffix = f" ({ing.name})" if ing is not None else ""
        return f"1 {self.name} = {self.grams}g{suffix}"


class Recipe(TimestampedModel):
    """A curated, seeded, or AI-generated recipe with cached per-serving nutrition."""

    name = models.CharField(max_length=200)
    name_alt = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES)
    cuisine = models.CharField(max_length=30, choices=CUISINE_CHOICES)
    diet_tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    allergen_tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    prep_time_min = models.PositiveSmallIntegerField(default=0)
    cook_time_min = models.PositiveSmallIntegerField(default=0)
    servings = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    estimated_difficulty = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_INTERMEDIATE
    )
    spice_level = models.CharField(max_length=20, choices=SPICE_LEVEL_CHOICES, default=SPICE_MEDIUM)
    protein_source = models.CharField(
        max_length=20,
        choices=PROTEIN_SOURCE_CHOICES,
        default=PROTEIN_SOURCE_NONE,
        db_index=True,
    )
    instructions = models.JSONField(default=list)
    image_url = models.URLField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    source = models.CharField(
        max_length=20, choices=RECIPE_SOURCE_CHOICES, default=RECIPE_SOURCE_SEED
    )
    cached_nutrition = models.JSONField(null=True, blank=True)
    cached_calories_per_serving = models.PositiveIntegerField(null=True, blank=True)
    cached_cost_inr = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    cost_known = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["meal_type"]),
            models.Index(fields=["cuisine"]),
            models.Index(fields=["prep_time_min"]),
            models.Index(fields=["estimated_difficulty"]),
            models.Index(fields=["spice_level"]),
            models.Index(fields=["cached_calories_per_serving"]),
            GinIndex(fields=["diet_tags"], name="recipe_diet_tags_gin"),
            GinIndex(fields=["allergen_tags"], name="recipe_allergen_gin"),
        ]

    def __str__(self) -> str:
        return self.name


class RecipeIngredient(TimestampedModel):
    """Ordered ingredient line in a recipe with canonical raw-weight quantity."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="recipe_ingredients")
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="recipe_usages"
    )
    order = models.PositiveSmallIntegerField(default=0)
    quantity_grams = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    display_quantity = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    display_unit = models.ForeignKey(
        HouseholdUnit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        unique_together = [("recipe", "ingredient")]
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.quantity_grams}g {self.ingredient.name} in {self.recipe.name}"
