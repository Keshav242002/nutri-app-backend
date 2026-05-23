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
| ingredients.json | 181,600 bytes (177.3 KB) | `7a81776356b9d3b8...` |
| recipes.json | 333,607 bytes (325.8 KB) | `d8c66675a8cfa3f5...` |

### Full SHA-256 hashes

- `household_units.json`: `c764b4ef77771f2bb37f25837a9b020f815c7a321d1b7218a8d742d4a860adbd`
- `ingredients.json`: `7a81776356b9d3b86a625a428461a5f97529da7c26fa368c642f649a10369323`
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
