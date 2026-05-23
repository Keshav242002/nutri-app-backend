#!/usr/bin/env python3
"""
Phase 6 — Fetch USDA nutrition data for USDA-sourced ingredients.

Reads ingredient_mapping.csv to identify USDA-sourced ingredients with
valid FDC IDs, fetches nutrition from the USDA FoodData Central API,
caches responses to disk, normalizes values to the per_100g_nutrition
schema, and merges into ingredients.json.

Usage:
    python scripts/fetch_usda_nutrition.py

Requires:
    USDA_API_KEY set in .env (or environment variable)
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BASE_DIR / "apps" / "recipes" / "seed_data"
MAPPING_CSV = SEED_DIR / "mappings" / "ingredient_mapping.csv"
INGREDIENTS_JSON = SEED_DIR / "ingredients.json"
USDA_CACHE_DIR = SEED_DIR / "sources" / "usda_cache"
BUILD_REPORT = SEED_DIR / "BUILD_REPORT.md"

# ---------------------------------------------------------------------------
# FDC ID corrections
# ---------------------------------------------------------------------------
# ingredient_mapping.csv has some incorrect FDC IDs (off-by-one or wrong
# variant). We correct them here rather than modifying the CSV (which is the
# source of truth for provenance metadata). Each correction was verified
# against the USDA FoodData Central search API.
FDC_ID_CORRECTIONS: dict[str, int] = {
    "curd_raw": 171284,              # 170887 = skim milk yogurt → 171284 = whole milk yogurt
    "butter_raw": 173410,            # 173430 = unsalted butter → 173410 = salted butter
    "buttermilk_raw": 170874,        # 173441 = 1% milk → 170874 = cultured buttermilk lowfat
    "brown_sugar_raw": 168833,       # 169656 = powdered sugar → 168833 = brown sugar
    "instant_coffee_raw": 171893,    # 171890 = brewed coffee → 171893 = instant coffee powder
    "bread_white_raw": 174924,       # 172684 = rye bread → 174924 = white bread, commercially prepared
    "processed_cheese_raw": 170853,  # 746766 = 404 → 170853 = American cheese, pasteurized process
}

# ---------------------------------------------------------------------------
# USDA Nutrient ID → schema field mapping
# ---------------------------------------------------------------------------
# USDA nutrient IDs we care about and their target field names.
# See: https://fdc.nal.usda.gov/api-guide.html
NUTRIENT_MAP: dict[int, str] = {
    1008: "calories",         # Energy (kcal)
    1003: "protein_g",        # Protein (g)
    1005: "carbs_g",          # Carbohydrate, by difference (g)
    1004: "fat_g",            # Total lipid (fat) (g)
    1079: "fiber_g",          # Fiber, total dietary (g)
    1089: "iron_mg",          # Iron (mg)
    1087: "calcium_mg",       # Calcium (mg)
    1162: "vit_c_mg",         # Vitamin C (mg)
    1092: "potassium_mg",     # Potassium (mg)
    1093: "sodium_mg",        # Sodium (mg)
    1090: "magnesium_mg",     # Magnesium (mg)
    1095: "zinc_mg",          # Zinc (mg)
    1106: "vit_a_rae_ug",     # Vitamin A, RAE (μg) — convert to IU
    1177: "folate_ug",        # Folate, total (μg)
    1178: "vit_b12_ug",       # Vitamin B-12 (μg)
}

# Macro fields (top-level in per_100g_nutrition)
MACRO_FIELDS = {"calories", "protein_g", "carbs_g", "fat_g", "fiber_g"}

# Micronutrient fields (nested under micronutrients)
MICRO_FIELDS = {
    "iron_mg", "calcium_mg", "vit_c_mg", "potassium_mg", "sodium_mg",
    "magnesium_mg", "zinc_mg", "vit_a_iu", "folate_ug", "vit_b12_ug",
}

# B12 dairy/animal items that MUST have B12 populated
B12_REQUIRED_APP_IDS = {
    "curd_raw", "butter_raw", "processed_cheese_raw",
    "buttermilk_raw", "fresh_cream_raw",
}


# ---------------------------------------------------------------------------
# Phase 6A — Identify rows to fetch
# ---------------------------------------------------------------------------

def identify_fetch_rows() -> list[dict[str, str]]:
    """
    Read ingredient_mapping.csv and return rows where:
    - source == "usda"
    - usda_fdc_id is a non-empty valid integer

    Applies FDC_ID_CORRECTIONS for known incorrect IDs in the CSV.
    """
    rows: list[dict[str, str]] = []

    with open(MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row["source"].strip()
            app_id = row["app_id"].strip()
            fdc_id_raw = row.get("usda_fdc_id", "").strip()

            if source != "usda":
                continue

            if not fdc_id_raw:
                continue

            # Verify it's a valid integer
            try:
                int(fdc_id_raw)
            except ValueError:
                continue

            # Apply FDC ID correction if needed
            if app_id in FDC_ID_CORRECTIONS:
                corrected_id = FDC_ID_CORRECTIONS[app_id]
                if int(fdc_id_raw) != corrected_id:
                    original_id = fdc_id_raw
                    row = dict(row)  # copy to avoid mutating the CSV reader
                    row["usda_fdc_id"] = str(corrected_id)
                    print(
                        f"    ℹ {app_id}: FDC ID corrected {original_id} → {corrected_id}"
                    )

            rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Phase 6B — Fetch from USDA API
# ---------------------------------------------------------------------------

def fetch_usda_food(fdc_id: int, api_key: str) -> dict[str, Any] | None:
    """
    Fetch a single food item from USDA FoodData Central API.
    Returns parsed JSON response or None on error.
    Uses stdlib urllib (no requests dependency needed).
    """
    url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}?api_key={api_key}"
    req = Request(url)
    req.add_header("Accept", "application/json")

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code in (401, 403):
            print(
                f"\n❌ USDA API authentication error (HTTP {e.code}) for FDC ID {fdc_id}.",
                file=sys.stderr,
            )
            print(
                "   This likely means your USDA_API_KEY is invalid or expired.",
                file=sys.stderr,
            )
            print("   Aborting. Please check your API key and retry.", file=sys.stderr)
            sys.exit(1)
        else:
            print(
                f"  ⚠ HTTP {e.code} for FDC ID {fdc_id}: {e.reason}",
                file=sys.stderr,
            )
            return None
    except Exception as e:
        print(f"  ⚠ Error fetching FDC ID {fdc_id}: {e}", file=sys.stderr)
        return None


def fetch_all(
    rows: list[dict[str, str]],
    api_key: str,
) -> tuple[dict[int, dict[str, Any]], int, int, int]:
    """
    Fetch USDA data for all rows, using disk cache when available.
    Returns (results, cached_count, fetched_count, error_count).
    """
    USDA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[int, dict[str, Any]] = {}
    cached_count = 0
    fetched_count = 0
    error_count = 0
    errors: list[str] = []

    for row in rows:
        fdc_id = int(row["usda_fdc_id"].strip())
        app_id = row["app_id"].strip()
        cache_path = USDA_CACHE_DIR / f"{fdc_id}.json"

        # Check cache
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                results[fdc_id] = data
                cached_count += 1
                print(f"  ✓ {app_id} (FDC {fdc_id}) — cached")
                continue
            except json.JSONDecodeError:
                print(f"  ⚠ Corrupt cache for FDC {fdc_id}, re-fetching...")

        # Fetch from API
        print(f"  → Fetching {app_id} (FDC {fdc_id})...")
        data = fetch_usda_food(fdc_id, api_key)

        if data is None:
            error_count += 1
            errors.append(f"FDC {fdc_id} ({app_id}): HTTP error")
            continue

        # Save to cache
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        results[fdc_id] = data
        fetched_count += 1

        # Rate limit: max 1 request per second
        time.sleep(1.0)

    print(f"\n  Fetch summary: {fetched_count} live, {cached_count} cached, {error_count} errors")
    if errors:
        for err in errors:
            print(f"    ERROR: {err}")

    return results, cached_count, fetched_count, error_count


# ---------------------------------------------------------------------------
# Phase 6C — Parse and normalize
# ---------------------------------------------------------------------------

def parse_usda_nutrition(
    usda_data: dict[str, Any],
    app_id: str,
) -> dict[str, Any]:
    """
    Parse USDA API response and normalize to per_100g_nutrition schema.

    Handles Foundation, SR Legacy, and Branded data types — all share
    the foodNutrients array structure.

    Vitamin A conversion: μg RAE × 3.33 ≈ IU (rough retinol-equivalent;
    documented approximation — actual conversion depends on whether the
    source is retinol or β-carotene).
    """
    raw_nutrients: dict[str, float] = {}
    missing_nutrients: list[str] = []

    food_nutrients = usda_data.get("foodNutrients", [])
    if not food_nutrients:
        print(f"    ⚠ {app_id}: no foodNutrients array in USDA response")
        # Return all zeros
        return _make_zero_nutrition()

    # Extract values from USDA response
    for entry in food_nutrients:
        nutrient = entry.get("nutrient", {})
        nutrient_id = nutrient.get("id")
        amount = entry.get("amount")

        if nutrient_id in NUTRIENT_MAP and amount is not None:
            field_name = NUTRIENT_MAP[nutrient_id]
            raw_nutrients[field_name] = float(amount)

    # Build per_100g_nutrition
    # Track which nutrients were absent
    for nutrient_id, field_name in NUTRIENT_MAP.items():
        if field_name not in raw_nutrients:
            missing_nutrients.append(field_name)

    # Macros
    calories = round(raw_nutrients.get("calories", 0))
    protein_g = round(raw_nutrients.get("protein_g", 0), 2)
    carbs_g = round(raw_nutrients.get("carbs_g", 0), 2)
    fat_g = round(raw_nutrients.get("fat_g", 0), 2)
    fiber_g = round(raw_nutrients.get("fiber_g", 0), 2)

    # Micronutrients
    iron_mg = round(raw_nutrients.get("iron_mg", 0), 2)
    calcium_mg = round(raw_nutrients.get("calcium_mg", 0), 2)
    vit_c_mg = round(raw_nutrients.get("vit_c_mg", 0), 2)
    potassium_mg = round(raw_nutrients.get("potassium_mg", 0), 2)
    sodium_mg = round(raw_nutrients.get("sodium_mg", 0), 2)
    magnesium_mg = round(raw_nutrients.get("magnesium_mg", 0), 2)
    zinc_mg = round(raw_nutrients.get("zinc_mg", 0), 2)
    folate_ug = round(raw_nutrients.get("folate_ug", 0), 2)
    vit_b12_ug = round(raw_nutrients.get("vit_b12_ug", 0), 2)

    # Vitamin A: μg RAE → IU (rough: μg × 3.33)
    vit_a_rae_ug = raw_nutrients.get("vit_a_rae_ug", 0)
    vit_a_iu = round(vit_a_rae_ug * 3.33, 2)

    if missing_nutrients:
        print(f"    ℹ {app_id}: missing nutrients set to 0: {', '.join(missing_nutrients)}")

    return {
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": fiber_g,
        "micronutrients": {
            "iron_mg": iron_mg,
            "calcium_mg": calcium_mg,
            "vit_c_mg": vit_c_mg,
            "potassium_mg": potassium_mg,
            "sodium_mg": sodium_mg,
            "magnesium_mg": magnesium_mg,
            "zinc_mg": zinc_mg,
            "vit_a_iu": vit_a_iu,
            "folate_ug": folate_ug,
            "vit_b12_ug": vit_b12_ug,
        },
    }


def _make_zero_nutrition() -> dict[str, Any]:
    """Return all-zero per_100g_nutrition."""
    return {
        "calories": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "micronutrients": {
            "iron_mg": 0.0,
            "calcium_mg": 0.0,
            "vit_c_mg": 0.0,
            "potassium_mg": 0.0,
            "sodium_mg": 0.0,
            "magnesium_mg": 0.0,
            "zinc_mg": 0.0,
            "vit_a_iu": 0.0,
            "folate_ug": 0.0,
            "vit_b12_ug": 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Phase 6D — Merge into ingredients.json
# ---------------------------------------------------------------------------

def merge_into_ingredients(
    usda_results: dict[int, dict[str, Any]],
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Load ingredients.json, update USDA-sourced entries with fetched nutrition,
    and write back. Returns (updated_ingredients, fetch_report_rows).
    """
    with open(INGREDIENTS_JSON, encoding="utf-8") as f:
        ingredients: list[dict[str, Any]] = json.load(f)

    # Build lookup: app_id → row from CSV
    row_lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        row_lookup[row["app_id"].strip()] = row

    # Build lookup: app_id → ingredient index
    ing_index: dict[str, int] = {}
    for i, ing in enumerate(ingredients):
        ing_index[ing["app_id"]] = i

    fetch_report: list[dict[str, Any]] = []
    description_mismatches: list[str] = []

    for row in rows:
        app_id = row["app_id"].strip()
        fdc_id = int(row["usda_fdc_id"].strip())
        csv_usda_desc = row.get("usda_description", "").strip()

        if fdc_id not in usda_results:
            fetch_report.append({
                "app_id": app_id,
                "fdc_id": fdc_id,
                "kcal": "ERROR",
                "b12_status": "ERROR — not fetched",
            })
            continue

        usda_data = usda_results[fdc_id]

        # Parse and normalize nutrition
        nutrition = parse_usda_nutrition(usda_data, app_id)

        # Cross-reference USDA description
        usda_api_desc = usda_data.get("description", "")
        if csv_usda_desc and usda_api_desc:
            # Simple check: are they substantially different?
            csv_lower = csv_usda_desc.lower().strip()
            api_lower = usda_api_desc.lower().strip()
            if csv_lower != api_lower:
                # Check if one contains the other
                if csv_lower not in api_lower and api_lower not in csv_lower:
                    description_mismatches.append(
                        f"  ⚠ {app_id} (FDC {fdc_id}): "
                        f"CSV='{csv_usda_desc}' vs API='{usda_api_desc}'"
                    )

        # Find ingredient in ingredients.json
        if app_id not in ing_index:
            print(f"  ⚠ {app_id} not found in ingredients.json, skipping")
            continue

        idx = ing_index[app_id]
        ing = ingredients[idx]

        # Update nutrition
        ing["per_100g_nutrition"] = nutrition

        # Update provenance
        ing["provenance"]["extracted_at"] = date.today().isoformat()
        if fdc_id:
            ing["provenance"]["usda_fdc_id"] = fdc_id
        if usda_api_desc:
            ing["provenance"]["usda_description"] = usda_api_desc

        # Remove data_status if it was "missing_no_usda_match" — it's now populated
        if ing.get("data_status") == "missing_no_usda_match":
            del ing["data_status"]

        # B12 status
        b12_val = nutrition["micronutrients"]["vit_b12_ug"]
        b12_status = f"{b12_val} μg" if b12_val > 0 else "not in response"

        fetch_report.append({
            "app_id": app_id,
            "fdc_id": fdc_id,
            "kcal": nutrition["calories"],
            "b12_status": b12_status,
        })

    # Report description mismatches
    if description_mismatches:
        print("\n  ⚠ Description mismatches (CSV vs USDA API):")
        for m in description_mismatches:
            print(m)

    # Sort by app_id
    ingredients.sort(key=lambda x: x["app_id"])

    # Write back
    with open(INGREDIENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(ingredients, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return ingredients, fetch_report


# ---------------------------------------------------------------------------
# Phase 6E — Validate
# ---------------------------------------------------------------------------

def validate_results(
    ingredients: list[dict[str, Any]],
    rows: list[dict[str, str]],
) -> list[str]:
    """Run validation checks on the updated ingredients."""
    errors: list[str] = []

    # Build set of fetched app_ids
    fetched_app_ids = {row["app_id"].strip() for row in rows}

    # Items that legitimately have 0 calories (mineral condiments)
    zero_cal_allowed = {"salt_raw", "black_salt_raw"}

    for ing in ingredients:
        app_id = ing["app_id"]
        if app_id not in fetched_app_ids:
            continue

        nutr = ing["per_100g_nutrition"]

        # Calories sanity: must be > 0 and < 1000 (except for salt)
        cal = nutr.get("calories", 0)
        if cal <= 0 and app_id not in zero_cal_allowed:
            errors.append(f"VALIDATION: {app_id} has calories={cal} (expected > 0)")
        if cal >= 1000:
            errors.append(f"VALIDATION: {app_id} has calories={cal} (expected < 1000)")

        # Macro plausibility
        protein = nutr.get("protein_g", 0)
        carbs = nutr.get("carbs_g", 0)
        fat = nutr.get("fat_g", 0)
        macro_sum = protein + carbs + fat
        if macro_sum > 110:
            errors.append(
                f"VALIDATION: {app_id} has protein+carbs+fat={macro_sum:.1f}g "
                f"(exceeds 110g per 100g — implausible)"
            )

    # B12 check for dairy/animal items
    b12_check_app_ids = B12_REQUIRED_APP_IDS
    ing_lookup = {ing["app_id"]: ing for ing in ingredients}
    for app_id in b12_check_app_ids:
        if app_id not in ing_lookup:
            continue
        ing = ing_lookup[app_id]
        b12 = ing["per_100g_nutrition"]["micronutrients"].get("vit_b12_ug")
        if b12 is None or b12 == 0:
            errors.append(
                f"VALIDATION WARNING: {app_id} has vit_b12_ug={b12} "
                f"(expected non-zero for dairy/animal product)"
            )

    return errors


# ---------------------------------------------------------------------------
# Phase 6F — Update BUILD_REPORT.md
# ---------------------------------------------------------------------------

def update_build_report(
    fetch_report: list[dict[str, Any]],
    fetched_live: int,
    from_cache: int,
    errored: int,
    total_time: float,
) -> None:
    """Append USDA fetch section to BUILD_REPORT.md."""
    # Compute new SHA-256 for ingredients.json
    with open(INGREDIENTS_JSON, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    lines = [
        "",
        "---",
        "",
        "## Phase 6 — USDA Nutrition Fetch",
        "",
        f"**Fetch date:** {date.today().isoformat()}",
        f"**Script:** `scripts/fetch_usda_nutrition.py`",
        "",
        "### Fetch summary",
        "",
        f"- Fetched live from API: {fetched_live}",
        f"- Served from cache: {from_cache}",
        f"- Errors: {errored}",
        f"- Total time: {total_time:.1f}s",
        "",
        "### Per-ingredient results",
        "",
        "| app_id | FDC ID | kcal | B12 status |",
        "|--------|--------|------|------------|",
    ]

    for r in fetch_report:
        lines.append(
            f"| {r['app_id']} | {r['fdc_id']} | {r['kcal']} | {r['b12_status']} |"
        )

    lines.extend([
        "",
        "### Updated output file",
        "",
        f"- `ingredients.json` SHA-256: `{sha256}`",
        "",
        "### Notes",
        "",
        "- Vitamin A conversion: μg RAE × 3.33 ≈ IU (rough retinol-equivalent "
        "approximation; actual conversion depends on source being retinol vs "
        "β-carotene)",
        "- Missing USDA nutrients are set to 0.0 (not null)",
        "- Vitamin B12 from USDA is the primary reason these dairy/animal items "
        "use USDA as the data source (IFCT does not measure B12)",
        "",
    ])

    # Append to existing BUILD_REPORT.md
    with open(BUILD_REPORT, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    start_time = time.time()

    print("=" * 60)
    print("Phase 6 — USDA Nutrition Fetch")
    print("=" * 60)

    # Pre-flight: check API key
    api_key = os.environ.get("USDA_API_KEY", "")
    if not api_key:
        # Try reading from .env file
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("USDA_API_KEY=") and not line.startswith("#"):
                        api_key = line.split("=", 1)[1].strip()
                        break

    if not api_key or api_key in ("replace-me", "your-usda-fdc-api-key-here"):
        print(
            "\n❌ USDA_API_KEY is not set or is a placeholder.",
            file=sys.stderr,
        )
        print(
            "   Please set USDA_API_KEY in your .env file with a valid key.",
            file=sys.stderr,
        )
        print(
            "   Get one at: https://fdc.nal.usda.gov/api-key-signup.html",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✓ USDA_API_KEY found (ends with ...{api_key[-4:]})")

    # Verify input files
    for path, desc in [
        (MAPPING_CSV, "ingredient_mapping.csv"),
        (INGREDIENTS_JSON, "ingredients.json"),
    ]:
        if not path.exists():
            print(f"❌ MISSING: {desc} at {path}", file=sys.stderr)
            sys.exit(1)
    print("✓ Input files verified")

    # Phase 6A — Identify rows
    print("\n--- Phase 6A: Identifying USDA rows to fetch ---")
    rows = identify_fetch_rows()
    print(f"  Found {len(rows)} USDA ingredients with valid FDC IDs to fetch:")
    for row in rows:
        print(f"    - {row['app_id'].strip()} (FDC {row['usda_fdc_id'].strip()})")

    if not rows:
        print("  No rows to fetch. Exiting.")
        sys.exit(0)

    # Phase 6B — Fetch
    print("\n--- Phase 6B: Fetching from USDA API ---")
    usda_results, cached_count, fetched_count, errored = fetch_all(rows, api_key)
    print(f"  Got data for {len(usda_results)} FDC IDs")

    # Phase 6C+6D — Parse, normalize, and merge
    print("\n--- Phase 6C+6D: Parse, normalize, and merge into ingredients.json ---")
    ingredients, fetch_report = merge_into_ingredients(usda_results, rows)
    print(f"  ✓ Updated {len(fetch_report)} ingredients in ingredients.json")

    # Phase 6E — Validate
    print("\n--- Phase 6E: Validation ---")
    validation_errors = validate_results(ingredients, rows)
    if validation_errors:
        for e in validation_errors:
            is_warning = "WARNING" in e
            prefix = "⚠" if is_warning else "❌"
            print(f"  {prefix} {e}")
        hard_errors = [e for e in validation_errors if "WARNING" not in e]
        if len(hard_errors) > 3:
            print(
                f"\n❌ {len(hard_errors)} hard validation errors. "
                f"Stopping — investigate before merging.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print("  ✓ All validation checks passed")

    # Phase 6F — Update BUILD_REPORT.md
    print("\n--- Phase 6F: Updating BUILD_REPORT.md ---")
    total_time = time.time() - start_time

    update_build_report(
        fetch_report=fetch_report,
        fetched_live=fetched_count,
        from_cache=cached_count,
        errored=errored,
        total_time=total_time,
    )
    print(f"  ✓ BUILD_REPORT.md updated")

    # Compute final SHA-256
    with open(INGREDIENTS_JSON, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    # Final report to chat
    print("\n" + "=" * 60)
    print("✅ PHASE 6 COMPLETE")
    print("=" * 60)
    print(f"\nFDC IDs fetched (live API): {fetched_count}")
    print(f"FDC IDs from cache: {cached_count}")
    print(f"Errors: {errored}")
    print(f"\nPer-ingredient results:")
    print(f"{'app_id':<30} {'FDC ID':<10} {'kcal':<8} {'B12 status'}")
    print("-" * 70)
    for r in fetch_report:
        print(f"{r['app_id']:<30} {r['fdc_id']:<10} {str(r['kcal']):<8} {r['b12_status']}")

    print(f"\ningredients.json SHA-256: {sha256}")
    print(f"Total time: {total_time:.1f}s")


if __name__ == "__main__":
    main()
