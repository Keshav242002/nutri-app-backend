# Corrected Output — Pre-ETL Audit Report

**Date:** 2026-05-23  
**Auditor:** Automated script  
**Scope:** All 14 batch files in `corrected_output/`  
**Purpose:** Catch silent failures before Phase 5 ETL ingestion

---

## What Was Checked

### 1. REJECTED Verdict Scan
Every recipe object across all 14 JSON files was inspected for a `"verdict": "REJECTED"` field.  
A rejected recipe would indicate the correction pipeline flagged it as unfixable — any such recipe must be excluded before ETL.

### 2. Ingredient Allowlist Validation
Every `ingredient_name` value inside every recipe's `ingredients[]` array was cross-referenced against the **136-item allowlist** at:

```
apps/recipes/seed_data/mappings/allowlist.txt
```

Any ingredient name not present in the allowlist would cause a **silent ETL failure** — the lookup would fail to resolve a nutritional profile, producing either a crash or silently missing nutrition data.

---

## Methodology

```
For each batch file (batch_1.json … batch_14.json):
  1. Parse JSON → extract "corrected_recipes" array
  2. For each recipe:
     a. Check if "verdict" field exists and equals "REJECTED"
     b. For each item in "ingredients[]":
        - Extract "ingredient_name"
        - Check membership in allowlist set
        - Flag if not found, with recipe name and suggested closest match
  3. Report per-file pass/fail status
```

**Allowlist loaded:** 136 unique ingredient identifiers  
**Matching:** Exact string match (case-sensitive) — no fuzzy matching, since ETL uses exact lookups.

---

## Results — Per Batch

| File | Recipes | Ingredients | Rejections | Allowlist Violations |
|------|---------|-------------|------------|----------------------|
| batch_1.json | 10 | — | 0 | 0 ✅ |
| batch_2.json | 10 | — | 0 | 0 ✅ |
| batch_3.json | 5 | — | 0 | 0 ✅ |
| batch_4.json | 5 | — | 0 | 0 ✅ |
| batch_5.json | 10 | — | 0 | 0 ✅ |
| batch_6.json | 10 | — | 0 | 0 ✅ |
| batch_7.json | 5 | — | 0 | 0 ✅ |
| batch_8.json | 5 | — | 0 | 0 ✅ |
| batch_9.json | 5 | — | 0 | 0 ✅ |
| batch_10.json | 10 | — | 0 | 0 ✅ |
| batch_11.json | 10 | — | 0 | 0 ✅ |
| batch_12.json | 5 | — | 0 | 0 ✅ |
| batch_13.json | 5 | — | 0 | 0 ✅ |
| batch_14.json | 5 | — | 0 | 0 ✅ |

---

## Summary

| Metric | Value |
|--------|-------|
| Total batch files scanned | 14 |
| Total recipes scanned | 100 |
| Total ingredient references checked | 1,113 |
| Total REJECTED verdicts found | **0** |
| Total allowlist violations found | **0** |

---

## High-Risk Batches — Spot Check

These batches were specifically flagged for manual review because they use non-vegetarian ingredients that are more prone to naming mismatches (e.g., `rohu_fish_raw` vs `rohu_raw`):

| Batch | Recipe | Ingredient Used | Allowlist Match? |
|-------|--------|-----------------|------------------|
| batch_8.json | Rohu Machher Jhol | `rohu_raw` | ✅ Yes |
| batch_8.json | Cholar Dal | (all veg) | ✅ Yes |
| batch_8.json | Aloo Posto | `poppy_seeds_raw` | ✅ Yes |
| batch_11.json | Pomfret Fish Curry | `pomfret_raw` | ✅ Yes |
| batch_11.json | Kerala Pepper Chicken Roast | `chicken_thigh_raw` | ✅ Yes |
| batch_13.json | Spicy Andhra Chicken Curry | `chicken_thigh_raw` | ✅ Yes |
| batch_13.json | Chettinad Egg Curry | `egg_whole_raw` | ✅ Yes |

All non-veg ingredient names resolve correctly.

---

## Audit 3: Duplicate Recipe Name Detection

### Purpose
Detect recipe names that appear in more than one batch file. Duplicate names can cause **ETL conflicts** — overwriting entries, double-counting nutrition data, or breaking unique-name constraints in the database.

### Script Used

```python
import json, glob
from collections import Counter

names = []
for f in sorted(glob.glob('batch_*.json')):
    data = json.load(open(f))
    # Handle both list and dict with 'corrected_recipes' key
    if isinstance(data, dict) and 'corrected_recipes' in data:
        recipes = data['corrected_recipes']
    elif isinstance(data, list):
        recipes = data
    else:
        recipes = []
    for r in recipes:
        names.append((r['name'].lower().strip(), f))

counts = Counter(n[0] for n in names)
dupes = {n: [f for nn, f in names if nn == n] for n, c in counts.items() if c > 1}

for name, files in sorted(dupes.items()):
    print(f'"{name}" appears in: {files}')
```

### Results

| Metric | Value |
|--------|-------|
| Total recipes scanned | 100 |
| Total unique recipe names | 93 |
| **Duplicate recipe names found** | **7** ⚠️ |

### Duplicates Found

| # | Recipe Name | Appears In | Notes |
|---|-------------|------------|-------|
| 1 | Aloo Paratha | `batch_1.json`, `batch_9.json` | Breakfast (batch 1) vs Lunch/Dinner (batch 9) |
| 2 | Bhindi Masala | `batch_5.json`, `batch_10.json` | Both are lunch/dinner |
| 3 | Cabbage Poriyal | `batch_6.json`, `batch_11.json` | Both are South Indian sides |
| 4 | Jeera Rice | `batch_5.json`, `batch_10.json` | Both are lunch/dinner |
| 5 | Moong Dal Khichdi | `batch_7.json`, `batch_10.json` | Gujarati (batch 7) vs general (batch 10) |
| 6 | Palak Paneer | `batch_5.json`, `batch_10.json` | Both are lunch/dinner |
| 7 | Rajma Masala | `batch_5.json`, `batch_10.json` | Both are lunch/dinner |

### Resolution (2026-05-23)

**Strategy:** Remove the duplicate from the batch where it was less contextually unique (kept the version with more regional specificity or the one in a more specialized batch).

| # | Removed From | Kept In | Rationale |
|---|-------------|---------|----------|
| 1 | `batch_1.json` | `batch_9.json` | batch_9 has the Punjabi lunch/dinner context |
| 2 | `batch_5.json` | `batch_10.json` | batch_10 is a more curated set |
| 3 | `batch_6.json` | `batch_11.json` | batch_11 has more South Indian depth |
| 4 | `batch_5.json` | `batch_10.json` | batch_10 is a more curated set |
| 5 | `batch_10.json` | `batch_7.json` | batch_7 has Gujarati regional specificity |
| 6 | `batch_5.json` | `batch_10.json` | batch_10 is a more curated set |
| 7 | `batch_5.json` | `batch_10.json` | batch_10 is a more curated set |

**Post-dedup recipe counts:**
- `batch_1.json`: 10 → 9
- `batch_5.json`: 10 → 6
- `batch_6.json`: 10 → 9
- `batch_10.json`: 10 → 9

> ✅ **RESOLVED** — Re-ran dedup audit: **93 recipes, 93 unique names, 0 duplicates.**

---

## Audit 4: ingredient_mapping.csv `app_id` Validation (Critical ETL Check)

### Purpose
This is the **most important check**. Every recipe's `ingredient_name` must exactly match an `app_id` from `ingredient_mapping.csv`. A mismatch here means the ETL will fail to resolve nutritional data for that ingredient — causing either a crash or silently missing nutrition.

### Script

Saved as [`check_allowlist.py`](corrected_output/check_allowlist.py) for reuse in Phase 5 ETL.

```python
import json, glob, csv
from collections import Counter
from difflib import get_close_matches

# Load allowlist from ingredient_mapping.csv
with open('../../mappings/ingredient_mapping.csv') as f:
    allowlist = {r['app_id'] for r in csv.DictReader(f)}

# Check every corrected recipe batch
violations = []
for f in sorted(glob.glob('batch_*.json')):
    data = json.load(open(f))
    if isinstance(data, dict) and 'corrected_recipes' in data:
        recipes = data['corrected_recipes']
    elif isinstance(data, list):
        recipes = data
    else:
        recipes = []
    for recipe in recipes:
        for ing in recipe['ingredients']:
            ing_name = ing['ingredient_name']
            if ing_name not in allowlist:
                close = get_close_matches(ing_name, list(allowlist), n=3, cutoff=0.6)
                violations.append((f, recipe['name'], ing_name, close))

if violations:
    print(f"{len(violations)} violations found:")
    for f, recipe, ing, close in violations:
        fix = f" → FIXABLE: {close}" if close else " → UNFIXABLE"
        print(f"  {f} :: {recipe} :: {ing}{fix}")
else:
    print("All recipe ingredient names match the allowlist. Clean.")
```

### Triage Protocol for Violations

| Type | Description | Action |
|------|-------------|--------|
| **Fixable** | Typo or close match (e.g., `fish_rohu_raw` → `rohu_raw`) | Fix the `ingredient_name` in the recipe JSON |
| **Unfixable** | Ingredient genuinely not in allowlist (e.g., `kashmiri_chilli_powder_raw`) | Reject the recipe, or substitute with closest allowlist match |

### Results

| Metric | Value |
|--------|-------|
| Allowlist source | `ingredient_mapping.csv` → `app_id` column |
| Allowlist size | 136 `app_id` entries |
| Total recipes scanned | 93 (post-dedup) |
| Total ingredients checked | 1,046 (post-dedup) |
| **Violations found** | **0** ✅ |

Every `ingredient_name` across all 14 batch files (93 recipes post-dedup) exactly matches an `app_id` in `ingredient_mapping.csv`.

---

## Conclusion

### ✅ All Checks Passing
- **Audit 1 — Zero rejections** — every recipe passed the correction pipeline.
- **Audit 2 — Zero allowlist.txt violations** — all ingredient references resolve to the 136-item allowlist.
- **Audit 3 — Zero duplicates** — 7 duplicates detected and resolved; 93 unique recipes remain.
- **Audit 4 — Zero ingredient_mapping.csv violations** — every `ingredient_name` matches an `app_id` (critical ETL check).
- **High-risk non-veg batches verified** — no naming mismatches like `rohu_fish_raw` or `chicken_breast` (without `_raw` suffix).

### Final Stats (Post-Dedup)
| Metric | Value |
|--------|-------|
| Batch files | 14 |
| Total recipes | 93 |
| Unique recipe names | 93 |
| Total ingredient references | 1,046 |
| Allowlist violations | 0 |
| Rejected recipes | 0 |

**✅ All clear. Safe to proceed to Phase 5 ETL.**

