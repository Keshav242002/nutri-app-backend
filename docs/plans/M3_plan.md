# M3 — Recipes: Implementation Plan

---

### Module purpose

M3 builds the **ingredient-level recipe database** — the foundational data layer that every downstream module depends on. It creates four models (Ingredient, HouseholdUnit, Recipe, RecipeIngredient), idempotent seed services that load ~136 ingredients, ~331 household units, and ~93 curated Indian recipes from production JSON files, a `compute_nutrition` service that sums ingredient-level nutrition into per-serving cached values on Recipe, and two read-only API endpoints for listing/filtering and detailing recipes. M3 sits after M2 (Profiles) and before M4 (MealPlans + Recommendation Engine) — M4 depends on having ≥93 seeded recipes with computed nutrition in the database. No external API calls happen at runtime in M3; all data is pre-baked from IFCT 2017 and USDA seed files.

---

### Prerequisite check (CLAUDE.md §4 M3)

**M2 acceptance criteria met:**
- [x] M2 completed 2026-05-20, commit `e193f2f`, 95 tests, 90% coverage
- [x] `POST /api/v1/profiles/onboarding`, `GET /api/v1/profiles/me`, `PATCH /api/v1/profiles/me` all working
- [x] Standard response envelope, budget derivation, validators — all verified in PROGRESS.md

**Seed data files exist:**
- [x] `apps/recipes/seed_data/ingredients.json` — 136 entries, 0 null `app_id`s, 0 duplicate `app_id`s
- [x] `apps/recipes/seed_data/household_units.json` — 331 entries, 0 null `unit_name`s
- [x] `apps/recipes/seed_data/recipes.json` — 93 entries, 0 null slugs, 0 duplicate slugs
- [x] All recipe `ingredient_app_id` references resolve to valid ingredient `app_id`s — **zero missing refs**
- [x] `apps/recipes/seed_data/mappings/ingredient_mapping.csv` — 136 rows (header + 135 data rows)
- [x] `apps/recipes/seed_data/BUILD_REPORT.md` — documents Phase 6 USDA fetch, 12 weak-confidence ingredients

**Sanity checks performed:**
- Ingredient sources: `{ifct: 105, composed: 1, usda: 30}` — matches BUILD_REPORT
- Confidence distribution: `{exact: 74, good: 45, approximate: 5, weak: 12}`
- Recipe meal types: `{breakfast: 29, lunch: 30, dinner: 34}`
- Recipe servings range: 2–4
- Ingredients with zero calories: **20** (6 IFCT oils/ghee with 0 enerc + 14 USDA items with missing/placeholder data)
- Ingredients with `data_status=missing_no_usda_match`: 12 (all weak-confidence USDA items)

> [!WARNING]
> **20 zero-calorie ingredients.** The 6 IFCT oils (ghee, coconut oil, groundnut oil, mustard oil, sesame oil, sunflower oil) have `fat_g=100` but `calories=0` because IFCT's `enerc` field is 0 kJ for pure fats. The seed service computes calories from macros as a fallback: `calories = protein×4 + carbs×4 + fat×9` when IFCT `enerc=0` but macros are non-zero. The 12 USDA weak-confidence items (corn flakes, garam masala, etc.) stay at zero — they are trace ingredients (spices, garnishes) used in small quantities; impact on recipe nutrition is negligible. Affected recipes are logged during seed. **No additional USDA fetch pass before M3.**

---

### Models and fields

#### 1. `Ingredient` (inherits `TimestampedModel`)

| Field | Type | Constraints | Index | Notes |
|-------|------|-------------|-------|-------|
| `id` | `AutoField` (PK) | — | PK | — |
| `app_id` | `CharField(max_length=80)` | `unique=True` | unique B-tree | Natural key for seed upsert. Maps to `app_id` in ingredients.json |
| `name` | `CharField(max_length=200)` | `unique=True` | unique B-tree | English name, e.g. "Basmati rice (raw)" |
| `name_hi` | `CharField(max_length=200, blank=True, default="")` | — | — | Hindi name, v1 optional |
| `category` | `CharField(max_length=20, choices=CATEGORY_CHOICES)` | — | B-tree | enum: grain, pulse, vegetable, fruit, dairy, meat, fish, egg, oil_fat, spice, nut_seed, sweetener, beverage, processed |
| `per_100g_nutrition` | `JSONField` | not null | — | Schema: `{calories, protein_g, carbs_g, fat_g, fiber_g, micronutrients: {iron_mg, calcium_mg, vit_c_mg, potassium_mg, sodium_mg, magnesium_mg, zinc_mg, vit_a_iu, folate_ug, vit_b12_ug}}` |
| `approximate_price_inr_per_kg` | `DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)` | — | — | null for items with no useful price (salt, spices) |
| `price_as_of_month` | `CharField(max_length=7, blank=True, default="")` | — | — | Format YYYY-MM |
| `allergen_tags` | `ArrayField(CharField(max_length=30), default=list, blank=True)` | — | **GIN** | Controlled vocab: dairy, eggs, gluten, peanuts, tree_nuts, soy, shellfish, fish, sesame, **mustard** |
| `is_active` | `BooleanField(default=True)` | — | — | Soft delete |
| `form` | `CharField(max_length=20, choices=FORM_CHOICES)` | not null | — | enum: raw, cooked, as_eaten |
| `cooked_yield_ratio` | `DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))` | `MinValue(0.1), MaxValue(10.0)` | — | Raw→cooked weight ratio |
| `source` | `CharField(max_length=20, choices=SOURCE_CHOICES)` | not null | — | enum: ifct, usda, manual, composed |
| `ifct_code` | `CharField(max_length=10, blank=True, default="")` | — | — | Populated when source=ifct |
| `ifct_name` | `CharField(max_length=200, blank=True, default="")` | — | — | IFCT food name |
| `ifct_regn` | `PositiveSmallIntegerField(null=True, blank=True)` | — | — | Regional sample count 1–6 |
| `usda_fdc_id` | `IntegerField(null=True, blank=True)` | — | — | USDA Foundation Food ID |
| `usda_description` | `CharField(max_length=200, blank=True, default="")` | — | — | USDA food description |
| `package_version` | `CharField(max_length=60, blank=True, default="")` | — | — | e.g. `@ifct2017/compositions@2.0.11` |
| `extracted_at` | `DateField(null=True, blank=True)` | — | — | When seed value was extracted |
| `confidence` | `CharField(max_length=20, choices=CONFIDENCE_CHOICES)` | — | — | enum: exact, good, approximate, weak |
| `overlays` | `JSONField(null=True, blank=True)` | — | — | For B12-from-USDA-overlaid-on-IFCT |
| `created_at` | via `TimestampedModel` | — | — | — |
| `updated_at` | via `TimestampedModel` | — | — | — |

**Indexes:** GIN on `allergen_tags`. B-tree on `category`.

**`__str__`:** `f"{self.name} ({self.app_id})"`

**Note on `per_100g_nutrition` JSONField shape:** Spec says top-level macros (`calories, protein_g, carbs_g, fat_g, fiber_g`) plus nested `micronutrients` dict. The seed data already uses this exact shape. We store it as-is — no flattening.

---

#### 2. `HouseholdUnit` (inherits `TimestampedModel`)

| Field | Type | Constraints | Index | Notes |
|-------|------|-------------|-------|-------|
| `id` | `AutoField` (PK) | — | PK | — |
| `name` | `CharField(max_length=50)` | not null | — | e.g. "katori", "roti", "cup", "tbsp" |
| `ingredient` | `ForeignKey(Ingredient, null=True, blank=True, on_delete=CASCADE, related_name="household_units_set")` | — | B-tree (FK) | `null` = generic unit; set = ingredient-specific |
| `grams` | `DecimalField(max_digits=7, decimal_places=2)` | `MinValue(0.01)` | — | Weight in grams of 1 unit |
| `created_at` | via `TimestampedModel` | — | — | — |
| `updated_at` | via `TimestampedModel` | — | — | — |

**Constraints:** `unique_together = [("name", "ingredient")]`

**`on_delete=CASCADE` justification:** If an ingredient is deleted, its specific household unit conversions become meaningless — "1 katori dal" without a dal ingredient is nonsensical. Generic units (ingredient=null) are unaffected.

**`__str__`:** `f"1 {self.name} = {self.grams}g" + (f" ({self.ingredient.name})" if self.ingredient else "")`

---

#### 3. `Recipe` (inherits `TimestampedModel`)

| Field | Type | Constraints | Index | Notes |
|-------|------|-------------|-------|-------|
| `id` | `AutoField` (PK) | — | PK | — |
| `name` | `CharField(max_length=200)` | not null | — | — |
| `name_alt` | `CharField(max_length=200, blank=True, default="")` | — | — | Alternate/English name, e.g. "Mashed potato rice" for "Aloo bhate bhat" |
| `slug` | `SlugField(max_length=220)` | `unique=True` | unique B-tree | URL-safe slug, upsert key |
| `meal_type` | `CharField(max_length=20, choices=MEAL_TYPE_CHOICES)` | not null | B-tree | enum: breakfast, lunch, dinner |
| `cuisine` | `CharField(max_length=30, choices=CUISINE_CHOICES)` | not null | B-tree | Controlled vocab from spec |
| `diet_tags` | `ArrayField(CharField(max_length=30), default=list, blank=True)` | — | **GIN** | Controlled vocab |
| `allergen_tags` | `ArrayField(CharField(max_length=30), default=list, blank=True)` | — | **GIN** | Controlled vocab (includes mustard) |
| `prep_time_min` | `PositiveSmallIntegerField(default=0)` | — | B-tree | For max_prep_time filter |
| `cook_time_min` | `PositiveSmallIntegerField(default=0)` | — | — | — |
| `servings` | `PositiveSmallIntegerField(default=1)` | `MinValue(1), MaxValue(20)` | — | — |
| `estimated_difficulty` | `CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="intermediate")` | — | B-tree | enum: beginner, intermediate, advanced |
| `spice_level` | `CharField(max_length=20, choices=SPICE_LEVEL_CHOICES, default="medium")` | — | B-tree | enum: mild, medium, hot, very_hot |
| `instructions` | `JSONField(default=list)` | not null | — | List of step strings |
| `image_url` | `URLField(blank=True, default="")` | — | — | Recipe image, v1 can be empty |
| `is_active` | `BooleanField(default=True)` | — | — | Soft delete |
| `source` | `CharField(max_length=20, choices=SOURCE_CHOICES)` | not null, default="seed" | — | enum: seed, ai_generated, user_custom |
| `cached_nutrition` | `JSONField(null=True, blank=True)` | — | — | Per-serving nutrition; schema: `{calories, protein_g, carbs_g, fat_g, fiber_g, micronutrients: {...}, computed_at: iso8601}` |
| `cached_calories_per_serving` | `PositiveIntegerField(null=True, blank=True)` | — | **B-tree** | Denormalized from cached_nutrition.calories for SQL filtering in M4 engine calorie window |
| `cached_cost_inr` | `DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)` | — | — | Total cost for full recipe (sum of ingredient×quantity prices) |
| `cost_known` | `BooleanField(default=False)` | — | — | True when ≥80% ingredient weight has non-null price |
| `created_at` | via `TimestampedModel` | — | — | — |
| `updated_at` | via `TimestampedModel` | — | — | — |

**Indexes:** GIN on `diet_tags`, GIN on `allergen_tags`. B-tree on `meal_type`, `cuisine`, `prep_time_min`, `estimated_difficulty`, `spice_level`, `cached_calories_per_serving`.

**`__str__`:** `self.name`

**Note:** `cached_nutrition` stores **per-serving** values (full JSONField with micronutrients). `cached_calories_per_serving` is a denormalized integer copy of `cached_nutrition.calories` for SQL `WHERE` filtering in the M4 engine calorie window. Both are populated together by `compute_recipe_nutrition()`. `cached_cost_inr` stores **total recipe cost** (divide by servings for per-serving cost). This matches spec: `max_cost_per_serving_inr` filter divides `cached_cost_inr / servings`.

---

#### 4. `RecipeIngredient` (inherits `TimestampedModel`)

| Field | Type | Constraints | Index | Notes |
|-------|------|-------------|-------|-------|
| `id` | `AutoField` (PK) | — | PK | — |
| `recipe` | `ForeignKey(Recipe, on_delete=CASCADE, related_name="recipe_ingredients")` | not null | B-tree (FK) | — |
| `ingredient` | `ForeignKey(Ingredient, on_delete=PROTECT, related_name="recipe_usages")` | not null | B-tree (FK) | — |
| `order` | `PositiveSmallIntegerField(default=0)` | — | — | Display order |
| `quantity_grams` | `DecimalField(max_digits=7, decimal_places=2)` | `MinValue(0.01)` | — | Canonical raw weight |
| `display_quantity` | `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)` | — | — | UI display, e.g. 1.5 |
| `display_unit` | `ForeignKey(HouseholdUnit, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | — | B-tree (FK) | null = show grams |
| `notes` | `CharField(max_length=200, blank=True, default="")` | — | — | e.g. "finely chopped" |
| `created_at` | via `TimestampedModel` | — | — | — |
| `updated_at` | via `TimestampedModel` | — | — | — |

**`on_delete` justifications:**

| FK | on_delete | Reason |
|----|-----------|--------|
| `recipe` | `CASCADE` | Deleting a recipe removes its ingredient list — orphan RecipeIngredient rows are meaningless |
| `ingredient` | `PROTECT` | **Critical safety**: deleting an ingredient used in recipes would silently break nutrition computation. Force explicit cleanup first. |
| `display_unit` | `SET_NULL` | If a household unit is deleted, the display reverts to showing raw grams — the recipe remains usable |

**Constraints:** `unique_together = [("recipe", "ingredient")]` — a recipe cannot list the same ingredient twice (combine quantities instead). `ordering = ["order"]` in Meta.

**`__str__`:** `f"{self.quantity_grams}g {self.ingredient.name} in {self.recipe.name}"`

---

### Services

All services live in `apps/recipes/services/`.

---

#### `apps/recipes/services/seed.py`

##### `seed_ingredients(path: Path) -> tuple[int, int]`

- **What:** Idempotent upsert of ingredients from `ingredients.json` into the Ingredient model.
- **Logic:**
  1. Load JSON file, validate structure.
  2. For each entry, `update_or_create` by `app_id`.
  3. Map seed JSON fields to model fields:
     - `app_id`, `name`, `category`, `form`, `cooked_yield_ratio` → direct
     - `per_100g_nutrition` → JSONField
     - `provenance.source` → `source`, `provenance.ifct_code` → `ifct_code`, etc.
     - `allergen_tags` → ArrayField (controlled vocab now includes `mustard`)
     - `diet_tags` are on the seed JSON but NOT on the Ingredient model — they are for recipe filtering only; **do not store on Ingredient**
     - `household_units` from seed JSON are NOT loaded here — `seed_household_units` handles them
  4. **Calorie fallback (CONFIRMED):** If `per_100g_nutrition.calories == 0` and macros are non-zero, compute `calories = round(protein_g * 4 + carbs_g * 4 + fat_g * 9)`. This fixes 6 IFCT oils (ghee→900 kcal, coconut oil→900, etc.). Log at WARNING with `event=calorie_fallback_computed`. The 12 weak USDA items stay at zero — they are trace ingredients.
  5. Call `full_clean()` before `save()`.
- **Returns:** `(created_count, updated_count)`
- **Exceptions:**
  - `FileNotFoundError` — if path doesn't exist
  - `AppValidationError` — if JSON structure is invalid or a required field is missing
- **Logging:**
  - INFO: `event=seed_ingredients_started`, `event=seed_ingredients_completed` with counts
  - WARNING: `event=calorie_fallback_computed` for zero-enerc items with macros (list app_ids)
  - WARNING: `event=zero_nutrition_ingredient` for items where everything is 0 (the 12 weak USDA items)

##### `seed_household_units(path: Path) -> tuple[int, int]`

- **What:** Idempotent upsert of household units from `household_units.json`.
- **Logic:**
  1. Load JSON file.
  2. For each entry, resolve `ingredient_app_id` to an `Ingredient` instance (must exist — fail loudly if not).
  3. `update_or_create` by `(name, ingredient)`.
  4. `full_clean()` before `save()`.
- **Returns:** `(created_count, updated_count)`
- **Exceptions:**
  - `FileNotFoundError`
  - `AppValidationError` if ingredient reference not found
- **Logging:** INFO start/complete with counts.

##### `seed_recipes(path: Path) -> tuple[int, int]`

- **What:** Idempotent upsert of recipes from `recipes.json` with allowlist validation.
- **Logic:**
  1. Load JSON file.
  2. **Allowlist validation:** For each recipe, verify every `ingredient_app_id` exists in the Ingredient table. Collect all missing refs and fail loudly with the full list.
  3. For each recipe:
     a. `update_or_create` Recipe by `slug`. Include `name_alt`, `estimated_difficulty`, `spice_level` from seed JSON.
     b. Delete existing `RecipeIngredient` rows for this recipe (idempotent re-seed).
     c. For each ingredient entry:
        - Resolve `ingredient_app_id` → Ingredient instance
        - Resolve `display_unit` → HouseholdUnit instance (look up by `(unit_name, ingredient)`, fall back to `(unit_name, None)` for generic units; null if not found)
        - Create `RecipeIngredient` with `order` based on list position
        - Log WARNING if `quantity_grams` vs `display_quantity × display_unit.grams` differs by >5% (per spec: soft warning, not error)
     d. Call `compute_recipe_nutrition(recipe)` immediately after loading ingredients.
  4. **Calorie range validation:** After computing nutrition, check `50 ≤ cached_nutrition.calories ≤ 1200` per serving. Log WARNING for out-of-range recipes but do NOT block the write (flag for manual review).
  5. `full_clean()` before `save()`.
- **Returns:** `(created_count, updated_count)`
- **Exceptions:**
  - `FileNotFoundError`
  - `AppValidationError` — if unknown ingredients found (hard fail with full list)
- **Logging:**
  - INFO: start/complete with counts
  - WARNING: `event=display_unit_mismatch` for quantity_grams discrepancy
  - WARNING: `event=recipe_calorie_out_of_range` with recipe slug and calorie value
  - WARNING: `event=recipe_uses_zero_nutrition_ingredient` listing affected recipe slugs and trace ingredient app_ids

---

#### `apps/recipes/services/nutrition.py`

##### `compute_recipe_nutrition(recipe: Recipe) -> dict[str, Any]`

- **What:** Sums ingredient-level nutrition × quantities into per-serving cached values.
- **Logic:**
  1. Fetch all `RecipeIngredient` entries for the recipe with `select_related("ingredient")`.
  2. For each RecipeIngredient:
     - `weight_fraction = quantity_grams / 100`
     - Add `ingredient.per_100g_nutrition.calories × weight_fraction` to running totals
     - Same for protein_g, carbs_g, fat_g, fiber_g
     - Same for each micronutrient (treat null as 0)
  3. Divide all totals by `recipe.servings` → per-serving values.
  4. Round: calories to int, macros to 2 decimals, micros to 2 decimals.
  5. Add `computed_at: datetime.now(UTC).isoformat()`.
  6. Compute cost:
     - For each RecipeIngredient where `ingredient.approximate_price_inr_per_kg` is not null:
       `ingredient_cost = (quantity_grams / 1000) × approximate_price_inr_per_kg`
     - Sum all ingredient costs → `cached_cost_inr` (total recipe cost, NOT per serving)
     - Compute priced weight fraction: `sum(quantity_grams for priced ingredients) / sum(all quantity_grams)`
     - If priced weight fraction ≥ 0.80: `cost_known = True`, else `cost_known = False`
  7. Write `recipe.cached_nutrition`, `recipe.cached_calories_per_serving`, `recipe.cached_cost_inr`, `recipe.cost_known`.
     - `cached_calories_per_serving` = the integer calories value from step 4 (same as `cached_nutrition["calories"]`)
  8. `recipe.save(update_fields=["cached_nutrition", "cached_calories_per_serving", "cached_cost_inr", "cost_known", "updated_at"])`.
- **Returns:** The computed nutrition dict (same as what's stored in `cached_nutrition`).
- **Exceptions:** None raised — logs errors for invalid data but always writes what it can.
- **Logging:**
  - DEBUG: `event=compute_recipe_nutrition`, recipe_slug, calorie total
  - WARNING: `event=zero_calorie_recipe` if computed calories/serving < 1

##### `recompute_recipes_using_ingredient(ingredient_id: int) -> int`

- **What:** Finds all recipes that use a given ingredient and recomputes their nutrition.
- **Logic:**
  1. `Recipe.objects.filter(recipe_ingredients__ingredient_id=ingredient_id, is_active=True).distinct()`
  2. For each recipe, call `compute_recipe_nutrition(recipe)`.
- **Returns:** Count of recipes recomputed.
- **Logging:** INFO: `event=recompute_triggered`, ingredient_id, recipe_count.

---

### Management commands

#### `python manage.py seed_recipes`

- **Location:** `apps/recipes/management/commands/seed_recipes.py`
- **What:** Wraps all three seed services in a `transaction.atomic()` block.
- **Logic:**
  1. Determine paths (default: `apps/recipes/seed_data/ingredients.json`, etc.).
  2. Allow `--ingredients-path`, `--household-units-path`, `--recipes-path` overrides.
  3. Inside `transaction.atomic()`:
     a. `seed_ingredients(ingredients_path)` → print counts
     b. `seed_household_units(household_units_path)` → print counts
     c. `seed_recipes(recipes_path)` → print counts (includes nutrition computation)
  4. Print summary: total ingredients, household units, recipes, computed nutrition stats.
- **Idempotent:** Safe to run multiple times.
- **Error handling:** If any seed function raises, the entire transaction rolls back.

#### `python manage.py recompute_nutrition`

- **Location:** `apps/recipes/management/commands/recompute_nutrition.py`
- **What:** Recomputes cached nutrition for all active recipes.
- **Logic:**
  1. Fetch all `Recipe.objects.filter(is_active=True)`.
  2. For each, call `compute_recipe_nutrition(recipe)`.
  3. Print summary: recipes processed, min/max/avg calories per serving.
- **Use case:** Ad-hoc rerun when ingredient data changes outside the seed flow.

---

### Serializers and views

#### Serializers

##### `RecipeListSerializer`

Slim representation for list endpoint:

```
{
  "name": str,
  "name_alt": str,
  "slug": str,
  "meal_type": str,
  "cuisine": str,
  "diet_tags": [str],
  "allergen_tags": [str],
  "prep_time_min": int,
  "cook_time_min": int,
  "servings": int,
  "estimated_difficulty": str,
  "spice_level": str,
  "image_url": str,
  "source": str,
  "cached_nutrition_summary": {
    "calories": int,
    "protein_g": float,
    "carbs_g": float,
    "fat_g": float,
    "fiber_g": float
  },
  "cached_cost_per_serving_inr": float | null,
  "cost_known": bool
}
```

- `cached_nutrition_summary` is a `SerializerMethodField` that extracts the top-level macros from `cached_nutrition` (excludes micronutrients for list performance).
- `cached_cost_per_serving_inr` is `SerializerMethodField`: `cached_cost_inr / servings` if `cached_cost_inr` is not null, else null.

##### `RecipeIngredientSerializer`

```
{
  "ingredient_name": str,
  "ingredient_app_id": str,
  "quantity_grams": float,
  "display_quantity": float | null,
  "display_unit_name": str | null,
  "display_unit_grams": float | null,
  "notes": str,
  "order": int
}
```

##### `RecipeDetailSerializer`

Full representation for detail endpoint (extends list):

```
{
  ... all fields from RecipeListSerializer ...,
  "ingredients": [RecipeIngredientSerializer],
  "instructions": [str],
  "cached_nutrition": {
    "calories": int,
    "protein_g": float,
    "carbs_g": float,
    "fat_g": float,
    "fiber_g": float,
    "micronutrients": {
      "iron_mg": float | null,
      "calcium_mg": float | null,
      "vit_c_mg": float | null,
      "potassium_mg": float | null,
      "sodium_mg": float | null,
      "magnesium_mg": float | null,
      "zinc_mg": float | null,
      "vit_a_iu": float | null,
      "folate_ug": float | null,
      "vit_b12_ug": float | null
    },
    "computed_at": str (ISO 8601)
  },
  "cached_cost_inr": float | null
}
```

---

#### Views

##### `GET /api/v1/recipes/` — Recipe List

- **View:** `RecipeListView(ListAPIView)`
- **Auth:** Required (IsAuthenticated) — per spec, all endpoints require auth
- **Serializer:** `RecipeListSerializer`
- **Pagination:** `StandardCursorPagination` (cursor, page_size=20, ordering=`-created_at`)
- **Filter:** `django_filters.FilterSet` with:

| Query Param | Filter Logic |
|-------------|-------------|
| `meal_type` | `exact` match |
| `cuisine` | `exact` match |
| `diet_tags` | comma-separated; `diet_tags__contains` (all must match via GIN) |
| `exclude_allergens` | comma-separated; exclude recipes where `allergen_tags` overlaps ANY of the given values |
| `max_prep_time` | `prep_time_min__lte` |
| `estimated_difficulty` | `exact` match |
| `spice_level` | `exact` match |
| `search` | `Q(name__icontains=...) | Q(name_alt__icontains=...)` — searches both primary and alternate name |
| `max_cost_per_serving_inr` | annotate `cost_per_serving = cached_cost_inr / servings`, filter `cost_per_serving__lte`. Only include recipes where `cost_known=True` for this filter. |
| `includes_ingredients` | comma-separated ingredient names (app_id); recipe must contain ALL |
| `excludes_ingredients` | comma-separated ingredient names (app_id); recipe must contain NONE |

- **Base queryset:** `Recipe.objects.filter(is_active=True)`
- **Response envelope:** Wrapped in `{status: "success", message: "Recipes retrieved", data: {next, previous, results: [...]}}` — pagination result is the `data` value.

> [!IMPORTANT]
> `includes_ingredients` and `excludes_ingredients` filter by `ingredient__app_id` on related RecipeIngredient rows. For `includes_ingredients`, we need a subquery that returns recipes containing ALL specified ingredients. For `excludes_ingredients`, exclude recipes containing ANY specified ingredient.

##### `GET /api/v1/recipes/<slug>/` — Recipe Detail

- **View:** `RecipeDetailView(RetrieveAPIView)`
- **Auth:** Required (IsAuthenticated)
- **Serializer:** `RecipeDetailSerializer`
- **Lookup field:** `slug`
- **Base queryset:** `Recipe.objects.filter(is_active=True).prefetch_related("recipe_ingredients__ingredient", "recipe_ingredients__display_unit")`
- **404:** Returns standard error envelope with code `NOT_FOUND`
- **Response envelope:** `{status: "success", message: "Recipe retrieved", data: {...}}`

---

### Migrations

**Migration plan: 1 migration.**

**`0001_initial.py`** — Creates all four models with all indexes.

No data backfill migration needed — seed data is loaded via `manage.py seed_recipes` which runs AFTER migrations. The order is: `migrate` → `seed_recipes`.

**Migration ordering:**
```
make migrate        # creates tables
make seed           # python manage.py seed_recipes — populates data + computes nutrition
```

#### Index inventory (created in `0001_initial`)

| Model | Field(s) | Index Type | Purpose |
|-------|----------|------------|---------|
| Ingredient | `app_id` | unique B-tree | Seed upsert key, lookups |
| Ingredient | `name` | unique B-tree | Unique constraint enforcement |
| Ingredient | `category` | B-tree | Category filter queries |
| Ingredient | `allergen_tags` | GIN | ArrayField containment queries (`__contains`, `__overlap`) |
| HouseholdUnit | `(name, ingredient)` | unique B-tree | unique_together constraint |
| HouseholdUnit | `ingredient_id` | B-tree | FK index (auto-created by Django) |
| Recipe | `slug` | unique B-tree | URL lookup, upsert key |
| Recipe | `meal_type` | B-tree | Engine hard filter |
| Recipe | `cuisine` | B-tree | Engine scoring + list filter |
| Recipe | `prep_time_min` | B-tree | max_prep_time filter |
| Recipe | `estimated_difficulty` | B-tree | Difficulty filter |
| Recipe | `spice_level` | B-tree | Spice level filter |
| Recipe | `cached_calories_per_serving` | B-tree | M4 engine calorie window SQL filter |
| Recipe | `diet_tags` | GIN | ArrayField containment queries |
| Recipe | `allergen_tags` | GIN | ArrayField overlap exclusion queries |
| RecipeIngredient | `(recipe, ingredient)` | unique B-tree | unique_together constraint |
| RecipeIngredient | `recipe_id` | B-tree | FK index (auto-created) |
| RecipeIngredient | `ingredient_id` | B-tree | FK index (auto-created) |

---

### Tests to write

**Target: ~93 tests, ≥80% coverage on `apps/recipes/services/`.**

#### Model tests (~14 tests)

1. `test_ingredient_str_representation`
2. `test_ingredient_unique_app_id_constraint`
3. `test_ingredient_unique_name_constraint`
4. `test_ingredient_category_choices_validation`
5. `test_ingredient_form_choices_validation`
6. `test_ingredient_cooked_yield_ratio_min_max_validation`
7. `test_household_unit_str_representation`
8. `test_household_unit_unique_together_constraint`
9. `test_household_unit_cascade_on_ingredient_delete`
10. `test_recipe_str_representation`
11. `test_recipe_unique_slug_constraint`
12. `test_recipe_ingredient_protect_on_ingredient_delete`
13. `test_recipe_ingredient_cascade_on_recipe_delete`
14. `test_recipe_ingredient_unique_together_constraint`

#### Service tests — seed (~24 tests)

15. `test_seed_ingredients_creates_all_entries`
16. `test_seed_ingredients_idempotent` — run twice, same counts
17. `test_seed_ingredients_updates_existing_on_rerun`
18. `test_seed_ingredients_calorie_fallback_for_zero_enerc` — oils with fat=100 get calories=900
19. `test_calorie_fallback_ghee_gets_900_kcal` — **specifically verify ghee (fat=100, protein=0, carbs=0) → calories=900** (regression guard for Q1 fallback logic)
20. `test_seed_ingredients_logs_zero_nutrition_warning`
21. `test_seed_ingredients_file_not_found`
22. `test_seed_ingredients_invalid_json`
23. `test_seed_household_units_creates_all_entries`
24. `test_seed_household_units_idempotent`
25. `test_seed_household_units_fails_on_missing_ingredient`
26. `test_seed_household_units_file_not_found`
27. `test_seed_recipes_creates_all_entries`
28. `test_seed_recipes_idempotent`
29. `test_seed_recipes_validates_ingredient_references` — rejects recipe with unknown ingredient
30. `test_seed_recipes_creates_recipe_ingredients_with_correct_order`
31. `test_seed_recipes_resolves_display_unit_to_household_unit`
32. `test_seed_recipes_display_unit_fallback_to_generic`
33. `test_seed_recipes_logs_quantity_grams_mismatch_warning`
34. `test_seed_recipes_flags_recipe_outside_calorie_range`
35. `test_seed_recipes_computes_nutrition_on_each_recipe`
36. `test_seed_recipes_loads_name_alt_estimated_difficulty_spice_level`
37. `test_mustard_allergen_accepted_in_seed` — **verify mustard allergen tag in seed data is accepted by model validation end-to-end** (regression guard for controlled vocab extension)
38. `test_seed_full_integration` — load all three files in order, verify DB state

#### Service tests — nutrition computation (~16 tests)

39. `test_compute_nutrition_sums_correctly_two_ingredients` — handcraft recipe with 100g rice + 50g dal, assert exact calories/macros
40. `test_compute_nutrition_divides_by_servings`
41. `test_compute_nutrition_handles_micronutrients`
42. `test_compute_nutrition_null_micronutrients_treated_as_zero`
43. `test_compute_nutrition_writes_computed_at_timestamp`
44. `test_compute_nutrition_computes_cost_from_ingredient_prices`
45. `test_compute_nutrition_sets_cost_known_true_when_priced_ingredients_dominate`
46. `test_compute_nutrition_sets_cost_known_false_when_most_weight_unpriced`
47. `test_compute_nutrition_cost_null_when_no_ingredients_have_price`
48. `test_compute_nutrition_handles_zero_calorie_ingredient`
49. `test_recompute_recipes_using_ingredient_updates_all_recipes`
50. `test_recompute_returns_correct_count`
51. `test_recompute_skips_inactive_recipes`
52. `test_compute_nutrition_per_serving_is_stored_on_recipe`
53. `test_compute_cost_is_total_recipe_not_per_serving`
54. `test_compute_nutrition_populates_cached_calories_per_serving` — verify the denormalized integer field matches `cached_nutrition["calories"]`

#### View tests — list endpoint (~27 tests)

55. `test_recipe_list_returns_200_with_recipes`
56. `test_recipe_list_requires_authentication`
57. `test_recipe_list_pagination_default_page_size`
58. `test_recipe_list_pagination_cursor_next`
59. `test_recipe_list_filter_by_meal_type`
60. `test_recipe_list_filter_by_cuisine`
61. `test_recipe_list_filter_by_diet_tags_single`
62. `test_recipe_list_filter_by_diet_tags_multiple_all_must_match`
63. `test_recipe_list_excludes_allergens_single`
64. `test_recipe_list_excludes_allergens_multiple`
65. `test_recipe_list_filter_by_max_prep_time`
66. `test_recipe_list_filter_by_estimated_difficulty`
67. `test_recipe_list_filter_by_spice_level`
68. `test_recipe_list_search_by_name`
69. `test_recipe_list_search_by_name_alt` — "kanda poha" finds "Onion poha" via name_alt
70. `test_recipe_list_search_case_insensitive`
71. `test_recipe_list_filter_by_max_cost_per_serving`
72. `test_recipe_list_cost_filter_only_includes_cost_known_recipes`
73. `test_recipe_list_filter_includes_ingredients_single`
74. `test_recipe_list_filter_includes_ingredients_multiple`
75. `test_recipe_list_filter_excludes_ingredients`
76. `test_recipe_list_combined_filters`
77. `test_recipe_list_response_envelope_shape`
78. `test_recipe_list_excludes_inactive_recipes`
79. `test_recipe_list_includes_cached_nutrition_summary`
80. `test_recipe_list_includes_cost_per_serving`
81. `test_recipe_list_empty_result`

#### View tests — detail endpoint (~8 tests)

82. `test_recipe_detail_returns_200_with_full_payload`
83. `test_recipe_detail_requires_authentication`
84. `test_recipe_detail_404_for_nonexistent_slug`
85. `test_recipe_detail_404_for_inactive_recipe`
86. `test_recipe_detail_includes_ingredients_list`
87. `test_recipe_detail_includes_full_micronutrients`
88. `test_recipe_detail_includes_instructions`
89. `test_recipe_detail_response_envelope_shape`

#### Integration tests (~6 tests)

90. `test_end_to_end_seed_and_query` — seed all three files, hit list endpoint, verify response
91. `test_end_to_end_seed_and_detail` — seed, hit detail endpoint, verify ingredient list
92. `test_recompute_nutrition_command` — run management command, verify recipes updated
93. `test_seed_recipes_command_idempotent` — run management command twice
94. `test_seed_recipes_command_rollback_on_bad_data`
95. `test_admin_registered` — verify Ingredient, Recipe, HouseholdUnit are in admin

**Total: ~95 tests**

---

### Acceptance criteria mapping

| Acceptance Criterion (from PROJECT_SPEC M3_recipes.tests_minimum) | Test(s) |
|---|---|
| `test_ingredient_seed_idempotent` | #16, #17 |
| `test_household_unit_seed_idempotent` | #24 |
| `test_recipe_seed_validates_ingredient_references` | #29 |
| `test_compute_nutrition_sums_correctly` | #39, #40 |
| `test_compute_nutrition_handles_micronutrients` | #41 |
| `test_recompute_on_ingredient_change_updates_all_recipes` | #49 |
| `test_cached_cost_computed_from_ingredient_prices` | #44 |
| `test_recipe_filter_by_max_cost_per_serving` | #71 |
| `test_recipe_filter_by_includes_excludes_ingredients` | #73, #74, #75 |
| `test_seed_rejects_recipe_with_unknown_ingredient` | #29 |
| `test_seed_flags_recipe_outside_calorie_range` | #34 |
| `test_recipe_list_filters_by_diet_tag` | #61, #62 |
| `test_recipe_list_excludes_allergens` | #63, #64 |
| `test_recipe_list_filters_by_max_prep_time` | #65 |
| `test_recipe_detail_returns_full_payload` | #82 |
| `test_recipe_list_pagination` | #57, #58 |
| `test_compute_nutrition_sets_cost_known_true_when_priced_ingredients_dominate` | #45 |
| `test_compute_nutrition_sets_cost_known_false_when_most_weight_unpriced` | #46 |

---

### Resolved decisions (formerly open questions)

All 8 questions resolved by user on 2026-05-23:

1. **Zero-calorie ingredients** — RESOLVED: Calorie fallback (`protein×4 + carbs×4 + fat×9`) applied at seed time for IFCT oils. 12 weak USDA items stay at zero. No additional USDA fetch pass. Affected recipes logged during seed.

2. **`cached_nutrition` storage** — RESOLVED: JSONField for full nutrition + denormalized `cached_calories_per_serving` (`PositiveIntegerField`, nullable, B-tree indexed) for M4 engine SQL calorie window filtering. Both populated together by `compute_recipe_nutrition()`.

3. **`cost_known` timing** — RESOLVED: Set by `compute_recipe_nutrition()` at seed time and on recomputation.

4. **Cost filter requires `cost_known=True`** — RESOLVED: Yes. `max_cost_per_serving_inr` filter adds `cost_known=True` to queryset.

5. **`diet_tags` not on Ingredient** — RESOLVED: Not stored on Ingredient model. Recipe-level `diet_tags` are sufficient.

6. **Mustard allergen** — RESOLVED: Controlled vocab expanded to include `mustard` (regulated allergen in EU/Canada, present in seed data). Updated in: (a) Ingredient.allergen_tags choices, (b) Recipe.allergen_tags choices, (c) PROJECT_SPEC.json `allergen_tags` controlled vocab. Documented in CLAUDE.md §13.

7. **`estimated_difficulty` and `spice_level`** — RESOLVED: Added to Recipe model. `estimated_difficulty`: CharField enum (beginner, intermediate, advanced), default "intermediate". `spice_level`: CharField enum (mild, medium, hot, very_hot), default "medium". Both filterable in list endpoint. B-tree indexes on both.

8. **`name_alt`** — RESOLVED: Added to Recipe model. `CharField(max_length=200, blank=True, default="")`. Included in both list and detail serializers. `search` filter queries `Q(name__icontains=...) | Q(name_alt__icontains=...)` so "kanda poha" finds "Onion poha".

---

### Spec patches to apply during M3 build

These patches are applied to `docs/PROJECT_SPEC.json` before implementation:

1. **allergen_tags vocab** — Add `"mustard"` to `M3_recipes.controlled_vocab.allergen_tags` array
2. **Recipe model additions** — Add `name_alt`, `estimated_difficulty`, `spice_level`, `cached_calories_per_serving` to `M3_recipes.models.Recipe`
3. **Endpoint search update** — Update `search` param description to `"search (icontains on name OR name_alt)"`
4. **Endpoint filter additions** — Add `estimated_difficulty` and `spice_level` to `query_params`
5. **CLAUDE.md §13** — One consolidated entry documenting all M3 planning decisions

---

### Estimated build order (locked sequence)

```
1.  spec patches  → docs/PROJECT_SPEC.json, CLAUDE.md §13 (mustard vocab, new fields)
2.  models        → apps/recipes/models.py (Ingredient, HouseholdUnit, Recipe, RecipeIngredient)
3.  migration     → apps/recipes/migrations/0001_initial.py (all indexes per inventory above)
4.  admin         → apps/recipes/admin.py (register all 4 models with search/filter)
5.  seed services → apps/recipes/services/seed.py (seed_ingredients, seed_household_units, seed_recipes)
6.  nutrition srv → apps/recipes/services/nutrition.py (compute_recipe_nutrition, recompute_recipes_using_ingredient)
7.  seed command  → apps/recipes/management/commands/seed_recipes.py
8.  recompute cmd → apps/recipes/management/commands/recompute_nutrition.py
9.  serializers   → apps/recipes/serializers.py (RecipeListSerializer, RecipeDetailSerializer, RecipeIngredientSerializer)
10. views         → apps/recipes/views.py (RecipeListView, RecipeDetailView)
11. urls          → apps/recipes/urls.py + update nutriplan/api_router.py
12. factories     → apps/recipes/tests/factories.py
13. tests         → apps/recipes/tests/test_models.py, test_services.py, test_views.py
14. run           → make test
15. fix           → iterate until all pass
16. lint          → make lint (ruff + black + mypy)
17. context       → update CLAUDE.md §3, PROGRESS.md, RUNBOOK.md, .env.example
18. commit        → feat(M3): recipes — ingredient DB, seed, nutrition compute, API
```
