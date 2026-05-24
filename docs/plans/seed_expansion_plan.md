# M3.5 — Seed Expansion Sprint

**Author:** Antigravity Agent
**Date:** 2026-05-24
**Prerequisite:** M3 committed and passing
**Blocks:** M4 MealPlans — requires ≥140 recipes across all diet×goal cells

---

## 1. Current State

| Metric | Value |
|--------|-------|
| Total recipes | 93 |
| Total ingredients | 136 (105 IFCT + 30 USDA + 1 composed) |
| Meal types covered | breakfast (29), lunch (30), dinner (34) |
| Non-veg recipes | **6** (3 chicken, 1 egg, 1 fish-lunch, 1 fish-dinner) |
| Eggetarian recipes | **1** (Chettinad Egg Curry) |
| High-protein tagged | 26 (all lunch/dinner, zero breakfast) |
| Cuisines used | 10 of 17 available (missing: goan, sindhi, continental, chinese_indo, pan_asian, east_indian, west_indian) |

### Existing non-veg recipe inventory

| Recipe | Meal | Cuisine | Protein Source | Diet Tags |
|--------|------|---------|---------------|-----------|
| Chettinad Egg Curry | dinner | tamil | egg | eggetarian, high_protein |
| Homestyle Chicken Curry | dinner | north_indian | chicken_thigh | high_protein |
| Kerala Pepper Chicken Roast | dinner | kerala | chicken_thigh | high_protein |
| Spicy Andhra Chicken Curry | dinner | andhra | chicken_thigh | high_protein |
| Rohu Machher Jhol | lunch | bengali | rohu | pescatarian, high_protein |
| Pomfret Fish Curry | dinner | tamil | pomfret | pescatarian, high_protein |

**Critical gaps:**
- Zero non-veg breakfast recipes
- Zero non-veg lunch recipes (except 1 fish)
- Zero chicken lunch recipes
- Zero mutton recipes
- Zero prawn recipes
- Zero egg breakfast/lunch recipes
- Zero high-protein breakfast recipes of any diet

---

## 2. Scope Decisions

### Diets IN scope (v1)

| Profile `diet_pattern` | Recipe `diet_tags` mapping | Notes |
|------------------------|---------------------------|-------|
| `vegetarian` | `["vegetarian"]` | No eggs, no meat, no fish. May include dairy. |
| `vegan` | `["vegan", "vegetarian"]` | Subset of vegetarian. No dairy. |
| `eggetarian` | `["eggetarian"]` | Vegetarian + eggs. NOT tagged `vegetarian`. |
| `non_vegetarian` (chicken) | `[]` — identified by `protein_source` | Chicken-based non-veg |
| `non_vegetarian` (mutton/fish) | `[]` — identified by `protein_source` | Mutton, fish, prawn-based non-veg |

### Diets DEFERRED to v2

- `jain` — requires `no_onion_garlic` constraint + root vegetable restrictions, complex filtering
- `satvik` — minimal existing content, niche
- `mediterranean` — not India-first enough for v1
- `pescatarian` — absorbed into non_veg_mutton_fish (fish is a subcategory)

### Goals IN scope

The Recipe model does **not** have a `goal` field — and shouldn't. Goal suitability is determined at the M4 meal-plan engine level by **calorie windows**:

| Goal | Approx cal/serving target | Recipe design guidance |
|------|--------------------------|----------------------|
| `weight_loss` | 200–400 kcal/serving | Low oil, lean protein, high fiber, smaller portions |
| `maintain` | 350–600 kcal/serving | Balanced — covers most standard recipes |
| `muscle_gain` | 400–700 kcal/serving | High protein (≥20g/serving), adequate carbs |

> **Note:** `gain_weight_healthy` and `eat_healthier` map to `maintain` and `weight_loss` windows respectively for recipe selection purposes. They differ in macro ratios, which is handled by M4 engine.

### Cross-cutting category: Salads & High-Protein-Low-Cal

A set of ~8 recipes that work across all diets (veg + non-veg variants) for weight_loss and eat_healthier goals. These are tagged `["high_protein", "low_carb"]` and typically <350 kcal/serving.

---

## 3. Coverage Matrix — Current vs Target

### 3.1 Breakfast (current: 29, target: ~40)

| Diet Category | Current | Target | Gap | New recipes needed |
|---------------|---------|--------|-----|-------------------|
| Vegetarian (non-vegan) | 9 | 10 | 1 | +1 (high-protein veg breakfast) |
| Vegan | 20 | 20 | 0 | — (well-covered) |
| Eggetarian | 0 | **4** | 4 | +4 egg breakfasts |
| Non-veg chicken | 0 | **2** | 2 | +2 chicken breakfasts |
| Non-veg mutton/fish | 0 | **0** | 0 | — (not typical for Indian breakfast) |
| **Subtotal new** | | | | **+7** |

### 3.2 Lunch (current: 30, target: ~50)

| Diet Category | Current | Target | Gap | New recipes needed |
|---------------|---------|--------|-----|-------------------|
| Vegetarian (non-vegan) | 17 | 19 | 2 | +2 (weight_loss-friendly veg) |
| Vegan | 12 | 14 | 2 | +2 (high-protein vegan) |
| Eggetarian | 0 | **3** | 3 | +3 egg lunches |
| Non-veg chicken | 0 | **6** | 6 | +6 chicken lunches |
| Non-veg mutton/fish | 1 | **4** | 3 | +3 mutton/fish lunches |
| High-protein salads | 0 | **4** | 4 | +4 salads (cross-diet) |
| **Subtotal new** | | | | **+20** |

### 3.3 Dinner (current: 34, target: ~55)

| Diet Category | Current | Target | Gap | New recipes needed |
|---------------|---------|--------|-----|-------------------|
| Vegetarian (non-vegan) | 11 | 13 | 2 | +2 (weight_loss veg dinners) |
| Vegan | 18 | 19 | 1 | +1 (high-protein vegan dinner) |
| Eggetarian | 1 | **3** | 2 | +2 egg dinners |
| Non-veg chicken | 3 | **7** | 4 | +4 chicken dinners |
| Non-veg mutton/fish | 1 | **5** | 4 | +4 mutton/fish dinners |
| High-protein salads | 0 | **4** | 4 | +4 salads (cross-diet) |
| **Subtotal new** | | | | **+17** |

### 3.4 Cross-cutting salads/high-protein-low-cal

| Recipe | Meal | Diet | Approx kcal | Protein source |
|--------|------|------|-------------|---------------|
| Sprouted Moong Chaat | lunch | vegan | ~180 | moong_sprouts |
| Paneer Tikka Salad | lunch | vegetarian | ~280 | paneer |
| Chicken Tikka Salad | lunch | non-veg | ~250 | chicken_breast |
| Egg White Bhurji Bowl | lunch | eggetarian | ~200 | egg |
| Cucumber Raita Bowl | dinner | vegetarian | ~150 | curd |
| Grilled Chicken and Veggie Bowl | dinner | non-veg | ~300 | chicken_breast |
| Tandoori Fish Tikka Salad | dinner | non-veg | ~260 | pomfret/rohu |
| Masala Egg Salad | dinner | eggetarian | ~220 | egg |

> Salad recipes counted in their respective meal_type sections above.

---

## 4. New Recipe List — By Batch

### Batch 1: Egg Breakfasts & Lunches (9 recipes)

| # | Recipe Name | Meal | Cuisine | Goal Fit | ~kcal | Key Ingredients |
|---|------------|------|---------|----------|-------|----------------|
| 1 | Masala Omelette | breakfast | north_indian | maintain | 280 | egg_whole_raw, onion, tomato, green_chilli |
| 2 | Egg Paratha | breakfast | punjabi | maintain, muscle_gain | 420 | egg_whole_raw, whole_wheat_flour, onion |
| 3 | Egg Bhurji | breakfast | north_indian | weight_loss, maintain | 250 | egg_whole_raw, onion, tomato, green_chilli |
| 4 | Egg Dosa | breakfast | south_indian | maintain | 350 | egg_whole_raw, idli_rava, onion |
| 5 | Egg Curry Rice Bowl | lunch | south_indian | maintain | 480 | egg_whole_raw, sona_masoori_rice, tomato, coconut_oil |
| 6 | Anda Biryani | lunch | north_indian | muscle_gain | 520 | egg_whole_raw, basmati_rice, onion, curd |
| 7 | Egg Fried Rice | lunch | chinese_indo | maintain | 450 | egg_whole_raw, basmati_rice, capsicum, carrot |
| 8 | Egg White Bhurji Bowl | lunch | north_indian | weight_loss | 200 | egg_whole_raw, spinach, tomato |
| 9 | Egg Drop Rasam | dinner | tamil | weight_loss | 180 | egg_whole_raw, tomato, tamarind_pulp |

**Egg dinner additions:**
| 10 | Masala Egg Curry | dinner | maharashtrian | maintain | 320 | egg_whole_raw, onion, tomato, coconut |
| 11 | Masala Egg Salad | dinner | continental | weight_loss | 220 | egg_whole_raw, onion, cucumber (use cabbage_raw as proxy) |

### Batch 2: Chicken Recipes (12 recipes)

| # | Recipe Name | Meal | Cuisine | Goal Fit | ~kcal | Key Ingredients |
|---|------------|------|---------|----------|-------|----------------|
| 1 | Chicken Keema Paratha | breakfast | punjabi | muscle_gain | 450 | chicken_breast_raw (minced), whole_wheat_flour, onion |
| 2 | Chicken Poha | breakfast | maharashtrian | maintain | 380 | chicken_breast_raw, poha_raw, onion, peanut |
| 3 | Chicken Curry with Rice | lunch | north_indian | maintain | 550 | chicken_thigh_raw, basmati_rice, onion, tomato |
| 4 | Chicken Biryani | lunch | south_indian | muscle_gain | 600 | chicken_thigh_raw, basmati_rice, onion, curd |
| 5 | Butter Chicken (Lite) | lunch | punjabi | maintain | 480 | chicken_breast_raw, butter, tomato, fresh_cream |
| 6 | Chicken Tikka Salad | lunch | north_indian | weight_loss | 250 | chicken_breast_raw, onion, capsicum, curd |
| 7 | Chicken Fried Rice | lunch | chinese_indo | maintain | 500 | chicken_breast_raw, basmati_rice, capsicum, carrot |
| 8 | Chicken Chettinad | lunch | tamil | muscle_gain | 420 | chicken_thigh_raw, onion, tomato, coconut_oil |
| 9 | Grilled Chicken and Veggie Bowl | dinner | continental | weight_loss | 300 | chicken_breast_raw, capsicum, carrot, spinach |
| 10 | Chicken Saagwala | dinner | north_indian | maintain | 380 | chicken_thigh_raw, spinach_raw, onion, tomato |
| 11 | Chicken Shorba | dinner | north_indian | weight_loss | 200 | chicken_breast_raw, onion, carrot, ginger |
| 12 | Tandoori Chicken | dinner | punjabi | muscle_gain | 350 | chicken_thigh_raw, curd, capsicum, onion |

### Batch 3: Mutton & Fish Recipes (7 recipes)

| # | Recipe Name | Meal | Cuisine | Goal Fit | ~kcal | Key Ingredients |
|---|------------|------|---------|----------|-------|----------------|
| 1 | Mutton Keema | lunch | north_indian | muscle_gain | 480 | mutton_raw, onion, tomato, green_peas |
| 2 | Mutton Rogan Josh | lunch | north_indian | muscle_gain | 520 | mutton_raw, onion, curd, ginger |
| 3 | Prawn Masala | lunch | goan | maintain | 350 | prawns_raw, onion, tomato, coconut_oil |
| 4 | Mutton Curry | dinner | north_indian | muscle_gain | 450 | mutton_raw, onion, tomato, ginger |
| 5 | Fish Fry (Tawa) | dinner | goan | maintain | 300 | pomfret_raw, onion, turmeric, lemon_juice |
| 6 | Prawn Curry | dinner | south_indian | maintain | 320 | prawns_raw, tomato, coconut_oil, curry_leaves |
| 7 | Tandoori Fish Tikka Salad | dinner | north_indian | weight_loss | 260 | rohu_raw, curd, capsicum, onion |

### Batch 4: High-Protein Vegetarian & Vegan Gap-Fillers (10 recipes)

| # | Recipe Name | Meal | Cuisine | Goal Fit | ~kcal | Key Ingredients |
|---|------------|------|---------|----------|-------|----------------|
| 1 | Paneer Dosa | breakfast | south_indian | muscle_gain | 380 | paneer_raw, idli_rava, urad_dal |
| 2 | Sprouted Moong Poha | breakfast | maharashtrian | weight_loss | 280 | moong_sprouts_raw, poha_raw, peanut_raw |
| 3 | Sprouted Moong Chaat | lunch | north_indian | weight_loss | 180 | moong_sprouts_raw, onion, tomato, lemon_juice |
| 4 | Paneer Tikka Salad | lunch | north_indian | weight_loss | 280 | paneer_raw, capsicum, onion, curd |
| 5 | Tofu Bhurji | lunch | north_indian | weight_loss | 220 | paneer_raw (proxy for tofu), onion, tomato |
| 6 | Rajma Rice Bowl | lunch | punjabi | muscle_gain | 520 | rajma_raw, basmati_rice, onion, tomato |
| 7 | Cucumber Raita Bowl | dinner | north_indian | weight_loss | 150 | curd_raw, onion, cucumber (cabbage_raw proxy) |
| 8 | Chana Masala (Dry) | dinner | punjabi | muscle_gain | 380 | kabuli_chana_raw, onion, tomato, ginger |
| 9 | Palak Dal | dinner | north_indian | weight_loss | 250 | masoor_dal_raw, spinach_raw, onion, tomato |
| 10 | Moong Dal Cheela | breakfast | north_indian | weight_loss | 220 | moong_dal_raw, onion, green_chilli |

### Batch 5: Cuisine Diversity & Additional Gap-Fillers (5 recipes)

| # | Recipe Name | Meal | Cuisine | Goal Fit | ~kcal | Key Ingredients |
|---|------------|------|---------|----------|-------|----------------|
| 1 | Goan Vegetable Xacuti | dinner | goan | maintain | 350 | potato_raw, cauliflower, coconut_oil, poppy_seeds |
| 2 | Indo-Chinese Veg Fried Rice | lunch | chinese_indo | maintain | 420 | basmati_rice, capsicum, carrot, cabbage, soy (trace) |
| 3 | Sindhi Kadhi | lunch | sindhi | maintain | 300 | besan_raw, onion, tomato, tamarind_pulp |
| 4 | Continental Veg Stir Fry | dinner | continental | weight_loss | 200 | capsicum, carrot, french_beans, cabbage, sesame_oil |
| 5 | Egg Appam | breakfast | kerala | maintain | 320 | egg_whole_raw, parboiled_rice_raw, coconut_oil |

---

### Summary: New Recipe Count

| Batch | Description | Count |
|-------|------------|-------|
| 1 | Egg recipes (breakfast/lunch/dinner) | 11 |
| 2 | Chicken recipes (breakfast/lunch/dinner) | 12 |
| 3 | Mutton & fish recipes (lunch/dinner) | 7 |
| 4 | High-protein veg/vegan gap-fillers | 10 |
| 5 | Cuisine diversity & miscellaneous | 5 |
| **Total new** | | **45** |

**Projected totals:** 93 + 45 = **138** (if 5 more added during generation, target is ~145)

---

## 5. Coverage Matrix — Post-Expansion Projection

### 5.1 By Goal × Diet × Meal Type

Recipes don't carry a `goal` field — they're assigned by the M4 engine based on calorie windows. The table below shows how many recipes **fit** each goal window.

#### Weight Loss (200–400 kcal/serving)

| Diet | Breakfast | Lunch | Dinner | Total |
|------|-----------|-------|--------|-------|
| Vegetarian | ~8 | ~6 | ~8 | ~22 |
| Vegan | ~15 | ~5 | ~10 | ~30 |
| Eggetarian | 3 | 2 | 3 | 8 |
| Non-veg (chicken) | 0 | 2 | 3 | 5 |
| Non-veg (mutton/fish) | 0 | 1 | 3 | 4 |
| **Column total** | **~26** | **~16** | **~27** | **~69** |

#### Maintenance (350–600 kcal/serving)

| Diet | Breakfast | Lunch | Dinner | Total |
|------|-----------|-------|--------|-------|
| Vegetarian | ~9 | ~14 | ~10 | ~33 |
| Vegan | ~15 | ~10 | ~14 | ~39 |
| Eggetarian | 4 | 3 | 3 | 10 |
| Non-veg (chicken) | 2 | 6 | 4 | 12 |
| Non-veg (mutton/fish) | 0 | 3 | 3 | 6 |
| **Column total** | **~30** | **~36** | **~34** | **~100** |

#### Muscle Gain (400–700 kcal/serving)

| Diet | Breakfast | Lunch | Dinner | Total |
|------|-----------|-------|--------|-------|
| Vegetarian | ~4 | ~10 | ~5 | ~19 |
| Vegan | ~8 | ~7 | ~5 | ~20 |
| Eggetarian | 2 | 2 | 2 | 6 |
| Non-veg (chicken) | 2 | 5 | 3 | 10 |
| Non-veg (mutton/fish) | 0 | 3 | 2 | 5 |
| **Column total** | **~16** | **~27** | **~17** | **~60** |

> **Minimum viable cell target:** ≥2 recipes per diet×meal_type combination. The only cell that remains at 0 is mutton/fish × breakfast, which is acceptable (no Indian culture has mutton/fish for breakfast).

### 5.2 By Cuisine (post-expansion)

| Cuisine | Current | +New | Projected |
|---------|---------|------|-----------|
| south_indian | 23 | +5 | 28 |
| north_indian | 18 | +12 | 30 |
| punjabi | 8 | +5 | 13 |
| bengali | 10 | 0 | 10 |
| maharashtrian | 9 | +3 | 12 |
| gujarati | 8 | 0 | 8 |
| tamil | 7 | +2 | 9 |
| rajasthani | 5 | 0 | 5 |
| andhra | 4 | 0 | 4 |
| kerala | 1 | +1 | 2 |
| **goan** | 0 | +3 | 3 |
| **chinese_indo** | 0 | +3 | 3 |
| **continental** | 0 | +3 | 3 |
| **sindhi** | 0 | +1 | 1 |
| east_indian | 0 | 0 | 0 (defer v2) |
| pan_asian | 0 | 0 | 0 (defer v2) |

---

## 6. Ingredient Expansion — New Ingredients Needed

### 6.1 Assessment of existing non-veg ingredients

| app_id | Name | Category | Has IFCT? | Has USDA? | Status |
|--------|------|----------|-----------|-----------|--------|
| `chicken_breast_raw` | Chicken breast | meat | ❌ | ✅ | ✅ Ready |
| `chicken_thigh_raw` | Chicken thigh | meat | ❌ | ✅ | ✅ Ready |
| `mutton_raw` | Mutton (goat) | meat | ✅ | ✅ | ✅ Ready |
| `egg_whole_raw` | Egg | egg | ✅ | ✅ | ✅ Ready |
| `catla_raw` | Catla | fish | ✅ | ❌ | ✅ Ready |
| `pomfret_raw` | Pomfret | fish | ✅ (note: S006 discrepancy) | ❌ | ⚠️ Usable |
| `prawns_raw` | Prawns | fish | ✅ | ❌ | ✅ Ready |
| `rohu_raw` | Rohu | fish | ✅ | ❌ | ✅ Ready |

### 6.2 New ingredients required

**None required!** The existing 8 meat/fish/egg ingredients are sufficient for all 45 planned recipes. Each recipe in the batch list above uses only existing `app_id`s.

### 6.3 Ingredients that would be NICE to add (optional, v2)

These would improve recipe quality but are NOT blockers:

| Proposed app_id | Name | Category | Why | Priority |
|----------------|------|----------|-----|----------|
| `cucumber_raw` | Cucumber | vegetable | Used in raita/salads; currently proxied via `cabbage_raw` | Medium |
| `coconut_fresh_raw` | Fresh coconut (grated) | nut_seed | Common in South Indian & Goan cooking; different from `coconut_oil` | Medium |
| `mint_leaves_raw` | Mint leaves | spice | Used in chutneys, biryanis — currently absent | Low |
| `tofu_raw` | Tofu | processed | For genuine vegan high-protein; currently proxied via paneer | Low |
| `boneless_fish_raw` | Boneless fish fillet | fish | Generic fish for recipes where species doesn't matter | Low |

> **Decision:** Skip optional ingredients for M3.5. Use existing app_ids with `notes` field for specificity (e.g., `notes: "minced"` on chicken_breast_raw). Add cucumber/coconut/mint in a future ingredient batch when building v2 recipes.

---

## 7. `protein_source` Field — Recommendation

### Recommendation: **YES — add `protein_source` to Recipe model now**

**Why:** The M4 meal-plan engine needs to match `profile.diet_pattern` to suitable recipes. Current `diet_tags` are insufficient for non-veg differentiation:

- A `non_vegetarian` user who prefers chicken needs recipes tagged differently from mutton/fish recipes
- `diet_tags` has no `non_veg_chicken` or `non_veg_mutton` value — and it shouldn't, because `diet_tags` describes recipe dietary *classification* (vegan/vegetarian/etc.), not protein source
- The engine would have to inspect `RecipeIngredient.ingredient.category` at query time — expensive and architecturally wrong

### Proposed implementation

```python
# In apps/recipes/models.py

PROTEIN_SOURCE_PANEER = "paneer"
PROTEIN_SOURCE_DAL = "dal_legume"
PROTEIN_SOURCE_EGG = "egg"
PROTEIN_SOURCE_CHICKEN = "chicken"
PROTEIN_SOURCE_MUTTON = "mutton"
PROTEIN_SOURCE_FISH = "fish"
PROTEIN_SOURCE_SOY = "soy"
PROTEIN_SOURCE_NONE = "none"  # for carb-dominant sides like plain rice

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

class Recipe(TimestampedModel):
    # ... existing fields ...
    protein_source = models.CharField(
        max_length=20,
        choices=PROTEIN_SOURCE_CHOICES,
        default=PROTEIN_SOURCE_NONE,
        db_index=True,
    )
```

### Implementation scope (small follow-up to M3)

1. Add `protein_source` field + migration (1 file)
2. Backfill existing 93 recipes via a data migration or `seed_recipes` update
3. Add `protein_source` to recipe JSON schema
4. Add `protein_source` filter to `RecipeFilterSet` (1 line)
5. Add `protein_source` to `RecipeListSerializer` (1 line)
6. ~5 new tests

**Effort:** ~1 hour. Should be done BEFORE the seed expansion so new recipes include `protein_source` from the start.

### Backfill rules for existing recipes

| Condition | `protein_source` value |
|-----------|----------------------|
| Uses `chicken_breast_raw` or `chicken_thigh_raw` | `chicken` |
| Uses `mutton_raw` | `mutton` |
| Uses `egg_whole_raw` | `egg` |
| Uses any fish/prawn ingredient | `fish` |
| Uses `paneer_raw` | `paneer` |
| Has `high_protein` tag + uses dal/legume ingredients | `dal_legume` |
| None of the above | `none` |

---

## 8. Gemini Prompt Template

### 8.1 System prompt (shared across all batches)

```
You are a nutritionist and Indian recipe author. Generate recipes for a meal-planning app.

RULES:
1. Every recipe MUST use ONLY ingredients from the ALLOWED INGREDIENT LIST below.
2. Use the exact `app_id` values from the list. Do NOT invent new ingredient app_ids.
3. All quantities must be in raw weight grams (quantity_grams). Also provide display_quantity and display_unit for user-friendly display.
4. Valid display_unit values: "katori", "roti", "piece", "cup", "tbsp", "tsp", "glass", "bowl", "slice", "small", "medium", "large", "handful", "pinch"
5. Every recipe must have 4-8 instruction steps. Steps should be concise, actionable, and specific.
6. Calorie estimates per serving should be realistic for Indian portions.
7. Each recipe serves 2 people unless otherwise specified.
8. Use realistic Indian cooking techniques and flavor profiles for the specified cuisine.
9. diet_tags must be accurate:
   - "vegan" = no dairy, no eggs, no meat, no fish, no honey
   - "vegetarian" = no eggs, no meat, no fish (dairy OK)
   - "eggetarian" = uses eggs, no meat, no fish
   - Do NOT tag non-veg recipes as "vegetarian" or "vegan"
   - Tag "high_protein" if protein ≥ 15g per serving
   - Tag "gluten_free" if no wheat/maida/semolina/oats
   - Tag "dairy_free" if no milk/curd/paneer/butter/ghee/cream/cheese
   - Tag "nut_free" if no almonds/cashews/pistachios/walnuts/peanuts
10. allergen_tags must list all applicable: "dairy", "eggs", "gluten", "peanuts", "tree_nuts", "soy", "shellfish", "fish", "sesame", "mustard"
11. protein_source must be one of: "paneer", "dal_legume", "egg", "chicken", "mutton", "fish", "soy", "none"

OUTPUT FORMAT: Return a JSON array of recipe objects with this exact schema:
{
  "name": "Recipe Name",
  "name_alt": "Hindi/regional name (optional)",
  "slug": "recipe-name-lowercase-hyphenated",
  "meal_type": "breakfast|lunch|dinner",
  "cuisine": "<from allowed list>",
  "diet_tags": ["tag1", "tag2"],
  "allergen_tags": ["tag1"],
  "prep_time_min": 10,
  "cook_time_min": 20,
  "servings": 2,
  "estimated_difficulty": "beginner|intermediate|advanced",
  "spice_level": "mild|medium|hot|very_hot",
  "protein_source": "chicken|egg|paneer|dal_legume|mutton|fish|soy|none",
  "ingredients": [
    {
      "ingredient_app_id": "exact_app_id",
      "quantity_grams": 150.0,
      "display_quantity": 1.0,
      "display_unit": "katori",
      "notes": "optional prep note"
    }
  ],
  "instructions": [
    "Step 1 text",
    "Step 2 text"
  ],
  "source": "seed"
}

ALLOWED CUISINES: north_indian, south_indian, east_indian, west_indian, punjabi, gujarati, maharashtrian, bengali, tamil, kerala, andhra, rajasthani, goan, sindhi, continental, chinese_indo, pan_asian

ALLOWED INGREDIENT LIST (app_id — name — category):
<INGREDIENT_LIST_PLACEHOLDER>
```

### 8.2 Per-batch user prompts

#### Batch 1 prompt (Egg recipes)

```
Generate 11 egg-based Indian recipes:

BREAKFAST (4 recipes):
1. Masala Omelette — north_indian, ~280 kcal, medium spice
2. Egg Paratha — punjabi, ~420 kcal, medium spice
3. Egg Bhurji — north_indian, ~250 kcal, hot spice
4. Egg Dosa — south_indian, ~350 kcal, mild spice

LUNCH (4 recipes):
5. Egg Curry Rice Bowl — south_indian, ~480 kcal, medium spice
6. Anda Biryani — north_indian, ~520 kcal, hot spice
7. Egg Fried Rice — chinese_indo, ~450 kcal, mild spice
8. Egg White Bhurji Bowl — north_indian, ~200 kcal, mild spice (weight_loss friendly, use only egg whites by using 4 eggs but reducing oil)

DINNER (3 recipes):
9. Egg Drop Rasam — tamil, ~180 kcal, hot spice (weight_loss friendly)
10. Masala Egg Curry — maharashtrian, ~320 kcal, medium spice
11. Masala Egg Salad — continental, ~220 kcal, mild spice

All recipes must use egg_whole_raw as the primary protein. Tag all as "eggetarian". Tag HIGH_PROTEIN if protein ≥ 15g/serving. Set protein_source="egg" for all.
```

#### Batch 2 prompt (Chicken recipes)

```
Generate 12 chicken-based Indian recipes:

BREAKFAST (2 recipes):
1. Chicken Keema Paratha — punjabi, ~450 kcal, hot spice, use chicken_breast_raw with notes "minced"
2. Chicken Poha — maharashtrian, ~380 kcal, medium spice

LUNCH (6 recipes):
3. Chicken Curry with Rice — north_indian, ~550 kcal, medium spice, chicken_thigh_raw
4. Chicken Biryani — south_indian, ~600 kcal, hot spice, chicken_thigh_raw
5. Butter Chicken (Lite) — punjabi, ~480 kcal, mild spice, chicken_breast_raw, use less butter/cream than traditional
6. Chicken Tikka Salad — north_indian, ~250 kcal, medium spice, chicken_breast_raw (weight_loss friendly)
7. Chicken Fried Rice — chinese_indo, ~500 kcal, mild spice, chicken_breast_raw
8. Chicken Chettinad — tamil, ~420 kcal, very_hot spice, chicken_thigh_raw

DINNER (4 recipes):
9. Grilled Chicken and Veggie Bowl — continental, ~300 kcal, mild spice, chicken_breast_raw (weight_loss friendly)
10. Chicken Saagwala — north_indian, ~380 kcal, medium spice, chicken_thigh_raw
11. Chicken Shorba — north_indian, ~200 kcal, mild spice, chicken_breast_raw (weight_loss friendly, soup)
12. Tandoori Chicken — punjabi, ~350 kcal, hot spice, chicken_thigh_raw

All are non-vegetarian. Do NOT tag as vegetarian/vegan/eggetarian. Tag "high_protein" for all. Set protein_source="chicken" for all. Tag "dairy_free" where no dairy is used.
```

#### Batch 3 prompt (Mutton & Fish recipes)

```
Generate 7 mutton and fish/prawn-based Indian recipes:

MUTTON (3 recipes):
1. Mutton Keema — north_indian, lunch, ~480 kcal, hot spice, mutton_raw with notes "minced"
2. Mutton Rogan Josh — north_indian, lunch, ~520 kcal, hot spice, mutton_raw
3. Mutton Curry — north_indian, dinner, ~450 kcal, medium spice, mutton_raw

FISH / SEAFOOD (4 recipes):
4. Prawn Masala — goan, lunch, ~350 kcal, hot spice, prawns_raw
5. Fish Fry (Tawa) — goan, dinner, ~300 kcal, medium spice, pomfret_raw
6. Prawn Curry — south_indian, dinner, ~320 kcal, medium spice, prawns_raw
7. Tandoori Fish Tikka Salad — north_indian, dinner, ~260 kcal, medium spice, rohu_raw (weight_loss friendly)

Set protein_source="mutton" for 1-3, protein_source="fish" for 4-7. Tag "high_protein" for all. Do NOT tag as vegetarian/vegan/eggetarian. Tag allergen "fish" for fish recipes.
```

#### Batch 4 prompt (High-protein veg/vegan gap-fillers)

```
Generate 10 high-protein vegetarian/vegan Indian recipes:

BREAKFAST (3 recipes):
1. Paneer Dosa — south_indian, ~380 kcal, mild spice, paneer_raw, protein_source=paneer, diet_tags=["vegetarian"]
2. Sprouted Moong Poha — maharashtrian, ~280 kcal, medium spice, moong_sprouts_raw, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"]
3. Moong Dal Cheela — north_indian, ~220 kcal, medium spice, moong_dal_raw, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"]

LUNCH (4 recipes):
4. Sprouted Moong Chaat — north_indian, ~180 kcal, medium spice, moong_sprouts_raw, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"] (weight_loss)
5. Paneer Tikka Salad — north_indian, ~280 kcal, medium spice, paneer_raw, protein_source=paneer, diet_tags=["vegetarian"] (weight_loss)
6. Tofu Bhurji — north_indian, ~220 kcal, medium spice, use paneer_raw with notes="tofu substitute", protein_source=soy, diet_tags=["vegan", "vegetarian"]
7. Rajma Rice Bowl — punjabi, ~520 kcal, medium spice, rajma_raw + basmati_rice, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"]

DINNER (3 recipes):
8. Cucumber Raita Bowl — north_indian, ~150 kcal, mild spice, curd_raw, use cabbage_raw with notes="substitute for cucumber", protein_source=paneer, diet_tags=["vegetarian"] (weight_loss)
9. Chana Masala (Dry) — punjabi, ~380 kcal, hot spice, kabuli_chana_raw, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"]
10. Palak Dal — north_indian, ~250 kcal, medium spice, masoor_dal_raw + spinach_raw, protein_source=dal_legume, diet_tags=["vegan", "vegetarian"] (weight_loss)

Tag "high_protein" for all. Tag "gluten_free" where appropriate.
```

#### Batch 5 prompt (Cuisine diversity)

```
Generate 5 recipes to fill cuisine gaps:

1. Goan Vegetable Xacuti — goan, dinner, ~350 kcal, hot spice, vegetarian, protein_source=none, use potato_raw + cauliflower_raw + coconut_oil_raw + poppy_seeds_raw
2. Indo-Chinese Veg Fried Rice — chinese_indo, lunch, ~420 kcal, medium spice, vegan, protein_source=none, use basmati_rice_raw + capsicum_raw + carrot_raw + cabbage_raw
3. Sindhi Kadhi — sindhi, lunch, ~300 kcal, medium spice, vegetarian, protein_source=dal_legume, use besan_raw + onion_raw + tomato_raw + tamarind_pulp_raw
4. Continental Veg Stir Fry — continental, dinner, ~200 kcal, mild spice, vegan, protein_source=none, use capsicum_raw + carrot_raw + french_beans_raw + cabbage_raw + sesame_oil_raw
5. Egg Appam — kerala, breakfast, ~320 kcal, mild spice, eggetarian, protein_source=egg, use egg_whole_raw + parboiled_rice_raw + coconut_oil_raw
```

---

## 9. Execution Workflow

### Phase 1: Model Update (pre-requisite, ~1 hour)

1. Add `protein_source` field to `Recipe` model
2. Create migration `0002_recipe_protein_source`
3. Backfill existing 93 recipes in `seed_recipes()` logic (derive from ingredients)
4. Add `protein_source` to seed JSON schema
5. Update `RecipeFilterSet` + serializers
6. Run tests, lint

### Phase 2: Ingredient Audit (pre-requisite, ~30 min)

1. Verify all 8 non-veg ingredients have valid nutrition data
2. Confirm `chicken_breast_raw` and `chicken_thigh_raw` have USDA nutrition (not zero)
3. Verify `mutton_raw` has IFCT nutrition
4. Verify all fish ingredients have IFCT nutrition
5. Log any zero-nutrition issues

### Phase 3: Recipe Generation (5 Gemini batches, ~2 hours)

For each batch (1–5):
1. Construct prompt from template + ingredient allowlist
2. Send to Gemini API
3. Parse JSON response
4. Run validation (see §10)
5. Fix any issues manually
6. Append to `recipes.json`
7. Run `make seed` and verify

### Phase 4: Integration Testing (~1 hour)

1. `make seed` — verify all recipes load without errors
2. `make test` — all existing tests pass
3. Verify calorie-range warnings (should see ZERO for new recipes if generated correctly)
4. Verify `?diet_tags=eggetarian` returns ≥8 recipes
5. Verify `?protein_source=chicken` returns ≥12 recipes
6. Verify each cuisine has ≥1 recipe
7. Update `BUILD_REPORT.md` with new counts

---

## 10. Validation Criteria

Each generated recipe must pass ALL of the following before acceptance:

### 10.1 Schema validation

- [ ] All required fields present: `name`, `slug`, `meal_type`, `cuisine`, `diet_tags`, `allergen_tags`, `prep_time_min`, `cook_time_min`, `servings`, `estimated_difficulty`, `spice_level`, `protein_source`, `ingredients`, `instructions`, `source`
- [ ] `slug` is unique across all recipes (existing + new)
- [ ] `meal_type` ∈ `{breakfast, lunch, dinner}`
- [ ] `cuisine` ∈ allowed cuisine vocab
- [ ] All `diet_tags` values ∈ `VALID_DIET_TAGS`
- [ ] All `allergen_tags` values ∈ `VALID_ALLERGEN_TAGS`
- [ ] `protein_source` ∈ allowed vocab
- [ ] `estimated_difficulty` ∈ `{beginner, intermediate, advanced}`
- [ ] `spice_level` ∈ `{mild, medium, hot, very_hot}`
- [ ] `source` = `"seed"`

### 10.2 Ingredient validation

- [ ] Every `ingredient_app_id` exists in `ingredients.json`
- [ ] `quantity_grams` > 0 for all ingredients
- [ ] `display_quantity` > 0 for all ingredients
- [ ] `display_unit` is a recognized household unit
- [ ] 3–12 ingredients per recipe (no trivial or excessively complex recipes)
- [ ] No duplicate `ingredient_app_id` within a recipe

### 10.3 Nutritional plausibility

- [ ] Computed `cached_calories_per_serving` is in range 50–1200
- [ ] Weight-loss recipes: <400 kcal/serving
- [ ] Muscle-gain recipes: >400 kcal/serving
- [ ] High-protein tagged recipes: estimated protein ≥15g/serving
- [ ] No recipe has total raw weight per serving >800g (unrealistic portion)

### 10.4 Diet tag consistency

- [ ] Recipes using `egg_whole_raw` → NOT tagged `vegetarian` or `vegan`; MUST have `allergen_tags` include `"eggs"`
- [ ] Recipes using chicken/mutton → NOT tagged `vegetarian`, `vegan`, or `eggetarian`
- [ ] Recipes using fish/prawn → NOT tagged `vegetarian`, `vegan`, or `eggetarian`; MUST have `allergen_tags` include `"fish"` (or `"shellfish"` for prawns)
- [ ] Recipes with `dairy_free` tag → do NOT use `butter_raw`, `ghee_raw`, `milk_cow_whole`, `curd_raw`, `paneer_raw`, `fresh_cream_raw`, `buttermilk_raw`, `processed_cheese_raw`
- [ ] Recipes with `gluten_free` tag → do NOT use `whole_wheat_flour_raw`, `maida_raw`, `refined_wheat_flour_raw`, `semolina_raw`, `broken_wheat_raw`, `vermicelli_wheat_raw`, `bread_white_raw`, `rolled_oats_raw`
- [ ] Recipes with `nut_free` tag → do NOT use `almond_raw`, `cashew_raw`, `pistachio_raw`, `walnut_raw`, `peanut_raw`
- [ ] `protein_source` matches the actual primary protein ingredient in the recipe

### 10.5 Instruction quality

- [ ] 4–8 steps per recipe
- [ ] Steps are in logical cooking order
- [ ] No generic filler steps (e.g., "Serve hot" alone is not a valid instruction)
- [ ] No reference to ingredients not in the ingredient list

---

## 11. Acceptance Targets

| Metric | Target | Minimum Acceptable |
|--------|--------|--------------------|
| New recipes passing all validation | 45 | 40 |
| Total recipe count (existing + new) | ~145 | ≥138 |
| Egg recipes | 11 | ≥8 |
| Chicken recipes | 12 | ≥10 |
| Mutton recipes | 3 | ≥2 |
| Fish/prawn recipes | 4+2 existing = 6 | ≥5 total |
| High-protein veg additions | 10 | ≥7 |
| Cuisines with ≥1 recipe | 14 of 17 | ≥12 of 17 |
| Every diet×meal_type cell ≥2 recipes | yes | every cell ≥1 |
| Zero calorie-range warnings from `make seed` | yes | ≤3 warnings |
| `make test` passes | yes | yes (hard req) |

---

## 12. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Gemini generates invalid `ingredient_app_id` | Automated validation script cross-checks against `ingredients.json`; reject any recipe with unknown IDs |
| Calorie estimates from Gemini are inaccurate | Rely on `compute_recipe_nutrition()` from ingredient-level data, not Gemini's estimate. Gemini's calorie estimate is guidance only. |
| Duplicate slugs | Automated check for slug uniqueness before merge |
| Diet tag inconsistency (e.g., chicken recipe tagged vegan) | Automated cross-check of ingredient categories vs tags (see §10.4) |
| Gemini returns malformed JSON | Request JSON-only output mode; manual fix if needed |
| Too few recipes pass validation | Generate 20% more than target (54 instead of 45); trim to best 45 |

---

## 13. Timeline

| Phase | Duration | Depends on |
|-------|----------|-----------|
| `protein_source` field + migration + backfill | 1 hour | M3 committed ✅ |
| Ingredient audit | 30 min | — |
| Batch 1 (eggs) generation + validation | 30 min | ingredient audit |
| Batch 2 (chicken) generation + validation | 30 min | ingredient audit |
| Batch 3 (mutton/fish) generation + validation | 20 min | ingredient audit |
| Batch 4 (veg gap-fillers) generation + validation | 30 min | — |
| Batch 5 (cuisine diversity) generation + validation | 15 min | — |
| Integration testing + BUILD_REPORT update | 30 min | all batches |
| Update hardcoded test count (test_seed_ingredients) | 5 min | all batches |
| **Total** | **~4 hours** | |

---

## Appendix A: Existing Ingredient App IDs (for prompt injection)

```
grain: barnyard_millet_raw, basmati_rice_raw, broken_wheat_raw, finger_millet_flour_raw, flattened_rice_raw, idli_rava_raw, maida_raw, parboiled_rice_raw, pearl_millet_flour_raw, poha_raw, refined_wheat_flour_raw, rice_sevai_raw, rolled_oats_raw, sabudana_raw, semolina_raw, sona_masoori_rice_raw, sorghum_flour_raw, vermicelli_wheat_raw, whole_wheat_flour_raw

pulse: besan_raw, chana_dal_raw, horse_gram_raw, kabuli_chana_raw, kala_chana_raw, lobia_raw, masoor_dal_raw, matki_raw, moong_dal_raw, moong_sprouts_raw, rajma_raw, toor_dal_raw, urad_dal_raw, whole_moong_raw, whole_urad_raw

vegetable: ash_gourd_raw, beetroot_raw, bitter_gourd_raw, bottle_gourd_raw, brinjal_raw, cabbage_raw, capsicum_raw, carrot_raw, cauliflower_raw, coriander_leaves_raw, drumstick_raw, fenugreek_leaves_raw, french_beans_raw, green_chilli_raw, green_peas_raw, okra_raw, onion_raw, potato_raw, pumpkin_raw, radish_raw, ridge_gourd_raw, spinach_raw, sweet_potato_raw, tomato_raw

fruit: apple_raw, banana_raw, guava_raw, lemon_juice_raw, mango_raw, papaya_raw, pomegranate_raw, sweet_lime_raw, tamarind_pulp_raw, watermelon_raw

dairy: butter_raw, buttermilk_raw, curd_raw, fresh_cream_raw, milk_cow_whole, paneer_raw, processed_cheese_raw

meat: chicken_breast_raw, chicken_thigh_raw, mutton_raw

fish: catla_raw, pomfret_raw, prawns_raw, rohu_raw

egg: egg_whole_raw

oil_fat: coconut_oil_raw, ghee_raw, groundnut_oil_raw, mustard_oil_raw, sesame_oil_raw, sunflower_oil_raw

spice: ajwain_raw, amchur_powder_raw, asafoetida_raw, bay_leaf_raw, black_cardamom_raw, black_pepper_raw, black_salt_raw, cinnamon_raw, cloves_raw, coriander_seeds_raw, cumin_raw, curry_leaves_raw, curry_powder_raw, dried_red_chilli_raw, fennel_seeds_raw, fenugreek_seeds_raw, garam_masala_raw, garlic_raw, ginger_raw, green_cardamom_raw, kasuri_methi_raw, mace_raw, mustard_seeds_raw, nutmeg_raw, red_chilli_powder_raw, saffron_raw, salt_raw, star_anise_raw, turmeric_powder_raw

nut_seed: almond_raw, cashew_raw, melon_seeds_raw, peanut_raw, pistachio_raw, poppy_seeds_raw, sesame_seeds_raw, walnut_raw

sweetener: brown_sugar_raw, honey_raw, jaggery_raw, sugar_raw

beverage: instant_coffee_raw, rose_water_raw, tea_leaves_raw

processed: bread_white_raw, corn_flakes_raw, papad_raw
```
