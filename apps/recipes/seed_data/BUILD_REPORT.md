# Seed Data Build Report

**Build date:** 2026-05-23
**Script:** `scripts/build_seed_data.py`

---

## Counts

### Ingredients by source

| Source | Count |
|--------|-------|
| composed | 1 |
| ifct | 105 |
| usda | 30 |
| **Total** | **136** |

### Household units: 331 entries

### Recipes by meal_type

| Meal Type | Count |
|-----------|-------|
| breakfast | 29 |
| dinner | 34 |
| lunch | 30 |
| **Total** | **93** |

### Recipes by cuisine

| Cuisine | Count |
|---------|-------|
| andhra | 4 |
| bengali | 10 |
| gujarati | 8 |
| kerala | 1 |
| maharashtrian | 9 |
| north_indian | 18 |
| punjabi | 8 |
| rajasthani | 5 |
| south_indian | 23 |
| tamil | 7 |

---

## Weak confidence ingredients

These ingredients have `confidence=weak` and need future improvement:

- **corn_flakes_raw** (Corn flakes) — source: usda, notes: IFCT no entry. FDC 173220 SR Legacy Kellogg's branded; generic equivalent 173752 'Cereals ready-to-eat, corn flakes, low sodium'. Branded entry chosen as closer to Indian retail. form=as_eaten (RTE). User verify.
- **curry_powder_raw** (Curry powder) — source: usda, notes: IFCT no entry. FDC 170925 SR Legacy. Note: 'curry powder' is largely a British/export concept — Indian cooking uses individual masalas. Same recompose option as garam masala if used heavily. User verify.
- **garam_masala_raw** (Garam masala) — source: usda, notes: IFCT has no blend entry. FDC 171324 SR Legacy garam masala. Blends vary widely by region/brand; consider recomposing as source=composed from G023 cloves + G020 green cardamom + G021 black cardamom + G031 black pepper + G025 cumin + G024 coriander + cinnamon (USDA) in v2 if accuracy matters. User verify FDC ID.
- **kasuri_methi_raw** (Dried fenugreek leaves) — source: usda, notes: No USDA entry for dried fenugreek leaves (kasuri methi). IFCT C020 is fresh fenugreek leaves — distinct from dried form (~10x nutrient density due to moisture loss). FDC 173470 'Spices, fenugreek seed' used as closest available USDA proxy for a dried fenugreek product, though seeds differ from leaves. Consider source=composed (dry C020 values × 10) for v2 accuracy.
- **melon_seeds_raw** (Melon seeds) — source: usda, notes: IFCT no entry. 'Magaz/char magaz' in Indian cooking is typically a mix of watermelon, muskmelon, pumpkin, and cucumber seed kernels — FDC 170556 watermelon seed kernels is closest single proxy. If brand specifies char magaz blend, build as source=composed. User verify.
- **moong_sprouts_raw** (Moong sprouts) — source: usda, notes: IFCT has no sprouted moong entry; B011 (whole green gram) is the unsprouted base but sprouting changes vitamin C and digestibility substantially. USDA FDC 169260 (SR Legacy) is the standard reference for raw mung sprouts. USER MUST VERIFY FDC ID.
- **papad_raw** (Papad) — source: usda, notes: IFCT no entry. FDC 169743 SR Legacy papad. Note: huge variation by base (urad/moong/rice/sago) and seasoning — FDC entry is generic urad-style. For specific papad types consider source=composed. User verify. cooked_yield_ratio=1.00 since fried/roasted papad loses moisture but gains oil ~ even out per piece basis.
- **rice_sevai_raw** (Rice sevai) — source: usda, notes: IFCT no entry (A023/A024 are wheat vermicelli, distinct). FDC 168879 SR Legacy rice noodles. User verify. Distinguish in app from wheat vermicelli — different gluten profile and culinary use.
- **rose_water_raw** (Rose water) — source: usda, notes: Rose water is ~99% water with trace flavoring compounds. Plain water (FDC 174831) used as nutrition proxy; contribution to recipe macros is negligible.
- **saffron_raw** (Saffron) — source: usda, notes: IFCT no entry. FDC 171323 SR Legacy. Used in such tiny quantities that nutrition contribution is negligible. User verify.
- **star_anise_raw** (Star anise) — source: usda, notes: Used in trace quantities; nutritional contribution negligible. No exact FDC match for Illicium verum; FDC 170915 anise seed retained as closest available proxy.
- **tea_leaves_raw** (Tea leaves) — source: usda, notes: Dry-leaf basis. Instant tea powder used as closest dry-basis USDA equivalent. Per-cup brewing uses 2g leaves; nutrition per cup brewed is negligible vs leaves.

## Missing USDA match ingredients

These ingredients have `data_status=missing_no_usda_match` and need USDA fetch in a future phase:

- **corn_flakes_raw** (Corn flakes) — notes: IFCT no entry. FDC 173220 SR Legacy Kellogg's branded; generic equivalent 173752 'Cereals ready-to-eat, corn flakes, low sodium'. Branded entry chosen as closer to Indian retail. form=as_eaten (RTE). User verify.
- **curry_powder_raw** (Curry powder) — notes: IFCT no entry. FDC 170925 SR Legacy. Note: 'curry powder' is largely a British/export concept — Indian cooking uses individual masalas. Same recompose option as garam masala if used heavily. User verify.
- **garam_masala_raw** (Garam masala) — notes: IFCT has no blend entry. FDC 171324 SR Legacy garam masala. Blends vary widely by region/brand; consider recomposing as source=composed from G023 cloves + G020 green cardamom + G021 black cardamom + G031 black pepper + G025 cumin + G024 coriander + cinnamon (USDA) in v2 if accuracy matters. User verify FDC ID.
- **kasuri_methi_raw** (Dried fenugreek leaves) — notes: No USDA entry for dried fenugreek leaves (kasuri methi). IFCT C020 is fresh fenugreek leaves — distinct from dried form (~10x nutrient density due to moisture loss). FDC 173470 'Spices, fenugreek seed' used as closest available USDA proxy for a dried fenugreek product, though seeds differ from leaves. Consider source=composed (dry C020 values × 10) for v2 accuracy.
- **melon_seeds_raw** (Melon seeds) — notes: IFCT no entry. 'Magaz/char magaz' in Indian cooking is typically a mix of watermelon, muskmelon, pumpkin, and cucumber seed kernels — FDC 170556 watermelon seed kernels is closest single proxy. If brand specifies char magaz blend, build as source=composed. User verify.
- **moong_sprouts_raw** (Moong sprouts) — notes: IFCT has no sprouted moong entry; B011 (whole green gram) is the unsprouted base but sprouting changes vitamin C and digestibility substantially. USDA FDC 169260 (SR Legacy) is the standard reference for raw mung sprouts. USER MUST VERIFY FDC ID.
- **papad_raw** (Papad) — notes: IFCT no entry. FDC 169743 SR Legacy papad. Note: huge variation by base (urad/moong/rice/sago) and seasoning — FDC entry is generic urad-style. For specific papad types consider source=composed. User verify. cooked_yield_ratio=1.00 since fried/roasted papad loses moisture but gains oil ~ even out per piece basis.
- **rice_sevai_raw** (Rice sevai) — notes: IFCT no entry (A023/A024 are wheat vermicelli, distinct). FDC 168879 SR Legacy rice noodles. User verify. Distinguish in app from wheat vermicelli — different gluten profile and culinary use.
- **rose_water_raw** (Rose water) — notes: Rose water is ~99% water with trace flavoring compounds. Plain water (FDC 174831) used as nutrition proxy; contribution to recipe macros is negligible.
- **saffron_raw** (Saffron) — notes: IFCT no entry. FDC 171323 SR Legacy. Used in such tiny quantities that nutrition contribution is negligible. User verify.
- **star_anise_raw** (Star anise) — notes: Used in trace quantities; nutritional contribution negligible. No exact FDC match for Illicium verum; FDC 170915 anise seed retained as closest available proxy.
- **tea_leaves_raw** (Tea leaves) — notes: Dry-leaf basis. Instant tea powder used as closest dry-basis USDA equivalent. Per-cup brewing uses 2g leaves; nutrition per cup brewed is negligible vs leaves.

---

## Output files

| File | Size | SHA-256 |
|------|------|---------|
| household_units.json | 32,193 bytes (31.4 KB) | `c764b4ef77771f2b...` |
| ingredients.json | 182,150 bytes (177.9 KB) | `4edad0bfa06bc15c...` |
| recipes.json | 333,607 bytes (325.8 KB) | `d8c66675a8cfa3f5...` |

### Full SHA-256 hashes

- `household_units.json`: `c764b4ef77771f2bb37f25837a9b020f815c7a321d1b7218a8d742d4a860adbd`
- `ingredients.json`: `4edad0bfa06bc15c7f1ddec2e0a2cac5424cf7a93aa006f7c2f9efc7b9db84cf`
- `recipes.json`: `d8c66675a8cfa3f539dfb5d70f981ae11a88d99bed8d577bb9830a62874b5c57`

---

## Notes

- USDA-sourced ingredients use placeholder zero values. Run a USDA fetch 
  pass to populate real nutrition data.
- Vitamin B12 is always null for IFCT-sourced ingredients (IFCT does not 
  measure B12). A USDA B12 overlay should be applied for animal products.
- The `composed` source (amchur_powder_raw) uses a 9× multiplier on mango 
  (E036) IFCT values to approximate dried mango powder nutrition.
- Three recipe cuisines (`rajasthani`, `tamil`, `kerala`) extend the 
  PROJECT_SPEC controlled vocab. Update the spec to include these.
- Pomfret (pomfret_raw) has ifct_code=S006 in ingredient_mapping.csv which 
  maps to Rohu in IFCT. The mapping_notes reference P057 (white pomfret). 
  This is a data discrepancy in the input CSV that should be corrected.

---

## Phase 6 — USDA Nutrition Fetch

**Fetch date:** 2026-05-23
**Script:** `scripts/fetch_usda_nutrition.py`

### Fetch summary

- Fetched live from API: 0
- Served from cache: 18
- Errors: 0
- Total time: 0.0s

### Per-ingredient results

| app_id | FDC ID | kcal | B12 status |
|--------|--------|------|------------|
| watermelon_raw | 167765 | 30 | not in response |
| curd_raw | 171284 | 61 | 0.37 μg |
| butter_raw | 173410 | 717 | 0.17 μg |
| fresh_cream_raw | 170859 | 340 | 0.16 μg |
| buttermilk_raw | 170874 | 40 | 0.22 μg |
| processed_cheese_raw | 170853 | 366 | 1.5 μg |
| bay_leaf_raw | 170917 | 313 | not in response |
| salt_raw | 173468 | 0 | not in response |
| sugar_raw | 169655 | 387 | not in response |
| fennel_seeds_raw | 171323 | 345 | not in response |
| cinnamon_raw | 171320 | 247 | not in response |
| black_salt_raw | 746775 | 0 | not in response |
| honey_raw | 169640 | 304 | not in response |
| brown_sugar_raw | 168833 | 380 | not in response |
| instant_coffee_raw | 171893 | 353 | not in response |
| sabudana_raw | 169717 | 358 | not in response |
| bread_white_raw | 174924 | 266 | not in response |
| rolled_oats_raw | 173904 | 379 | not in response |

### Updated output file

- `ingredients.json` SHA-256: `caa08be12d9b9711fe65036296b71ac41a3285899f1eb517ab0f1b540fb1be4d`

### Notes

- Vitamin A conversion: μg RAE × 3.33 ≈ IU (rough retinol-equivalent approximation; actual conversion depends on source being retinol vs β-carotene)
- Missing USDA nutrients are set to 0.0 (not null)
- Vitamin B12 from USDA is the primary reason these dairy/animal items use USDA as the data source (IFCT does not measure B12)

---

## M3.5 — Gemini Batch Seed Expansion

**Expansion date:** 2026-05-25
**Source files:** `apps/recipes/seed_data/sources/gemini_batches/` (5 batch files)

### Summary

| Batch | Loaded | Accepted | Rejected |
|-------|--------|----------|----------|
| batch_1_eggs | 11 | 11 | 0 |
| batch_2_chicken | 12 | 12 | 0 |
| batch_3_fish | 7 | 7 | 0 |
| batch_4_protein | 10 | 8 | 2 |
| batch_5_cuisine | 5 | 5 | 0 |
| **Total** | **45** | **43** | **2** |

**Rejections:**
- `matki-usal` — slug already existed in original 93
- `paneer-rajma-rice-bowl` — invalid cuisine value `fusion`

### New recipe counts (total: 136)

#### By meal_type

| Meal Type | Count |
|-----------|-------|
| breakfast | 39 |
| lunch | 48 |
| dinner | 49 |
| **Total** | **136** |

#### By protein_source

| protein_source | Count |
|----------------|-------|
| none | 96 |
| egg | 12 |
| chicken | 12 |
| dal_legume | 7 |
| fish | 4 |
| mutton | 3 |
| paneer | 2 |

**Known gap:** fish=4 is below the M4 gate target of ≥5. At least 1 more fish recipe needed before M4 unblock.

#### Cuisines added/expanded

| Cuisine | Before | After |
|---------|--------|-------|
| north_indian | 18 | 34 |
| punjabi | 8 | 14 |
| south_indian | 23 | 28 |
| maharashtrian | 9 | 12 |
| tamil | 7 | 9 |
| chinese_indo | 0 | 3 |
| continental | 0 | 3 |
| goan | 0 | 3 |
| kerala | 1 | 2 |
| sindhi | 0 | 1 |

### Zero-nutrition warnings (pre-existing, unchanged)

Same 14 zero-nutrition ingredients as before (spices, salt, trace items). No new zero-nutrition ingredients introduced by the new recipes.

---

## M4.5 — Heavy-Portion Seed Expansion

**Expansion date:** 2026-05-27
**Source file:** `apps/recipes/seed_data/heavy_batch_gemini.json`

### Summary

| Metric | Value |
|--------|-------|
| Loaded from batch | 15 |
| Accepted | 15 |
| Rejected | 0 |
| Existing recipes quantity-fixed | 5 |
| New total recipes | **151** |

### New recipes (all 15 accepted)

| Slug | Meal Type | Cuisine | Diet | kcal/srv |
|------|-----------|---------|------|----------|
| rajma-chawal | lunch | north_indian | vegan | 516 |
| chole-bhature | lunch | punjabi | vegetarian | 615 |
| dal-chawal-tadka | dinner | north_indian | vegan | 463 |
| paneer-butter-masala-naan | dinner | punjabi | vegetarian | 589 |
| aloo-paratha-thali | lunch | punjabi | vegetarian | 525 |
| veg-biryani | dinner | north_indian | vegetarian | 491 |
| vegan-rajma-rice-bowl | dinner | north_indian | vegan | 497 |
| chana-masala-rice | lunch | north_indian | vegan | 542 |
| bisi-bele-bath-full | dinner | south_indian | vegan | 471 |
| egg-biryani-full | lunch | north_indian | eggetarian | 565 |
| egg-paratha-thali | dinner | punjabi | eggetarian | 505 |
| chicken-biryani-full | dinner | south_indian | non-veg | 624 |
| mutton-pulao | dinner | north_indian | non-veg | 601 |
| butter-chicken-rice | lunch | punjabi | non-veg | 634 |
| fish-curry-rice | dinner | bengali | pescatarian | 502 |

All 15 recipes calibrated to 400–650 kcal/serving after scaling calorie-dense ingredients.

### 5 existing recipe quantity fixes (per M4.5 plan §6.3)

| Slug | Fix | kcal/srv |
|------|-----|----------|
| lemon-rice | rice 200→400g, sesame oil 20→30g | 472 |
| curd-rice | rice 120→250g, curd 250→350g | 315 |
| panchmel-dal | 5 dals 30→50g each, ghee 28→40g | 324 |
| prawn-curry | prawns 500→600g, coconut oil 30→45g | 260 |
| rohu-machher-jhol | potato 150→250g, mustard oil 30→45g | 262 |

Servings unchanged on all 5 recipes (all remain servings=4).

### Updated recipe counts (total: 151)

#### By meal_type

| Meal Type | Before | After |
|-----------|--------|-------|
| breakfast | 39 | 39 |
| lunch | 48 | 55 |
| dinner | 49 | 57 |
| **Total** | **136** | **151** |

#### Engine coverage improvement (target_cal=1000)

| Cell | Before | After |
|------|--------|-------|
| Lunch 400-650 kcal | 7 | 14 |
| Dinner 400-650 kcal | 0 | 9 |
| Vegan lunch (thin cell) | 2 | 3 ✅ |
| Vegan dinner (thin cell) | 2 | 2 ⚠️ |

### Thin cell inventory update

- `(vegan, lunch)` removed from KNOWN_THIN_CELLS (now has 3 candidates)
- `(vegan, dinner)` remains as known thin cell (2 candidates)

