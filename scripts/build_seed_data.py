#!/usr/bin/env python3
"""
Build seed data JSON files for M3 from ingredient_mapping.csv, IFCT index.csv,
and batch recipe JSON files.

Produces three output files in apps/recipes/seed_data/:
  - ingredients.json  (136 entries)
  - household_units.json  (~400-500 entries)
  - recipes.json  (211 entries)

Plus a BUILD_REPORT.md summary.

Usage:
    python scripts/build_seed_data.py

Idempotent — running twice with same inputs produces identical output.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = BASE_DIR / "apps" / "recipes" / "seed_data"
MAPPING_CSV = SEED_DIR / "mappings" / "ingredient_mapping.csv"
IFCT_CSV = SEED_DIR / "sources" / "ifct2017" / "index.csv"
BATCH_DIR = SEED_DIR / "claude_recipes" / "corrected_output"

OUT_INGREDIENTS = SEED_DIR / "ingredients.json"
OUT_HOUSEHOLD = SEED_DIR / "household_units.json"
OUT_RECIPES = SEED_DIR / "recipes.json"
OUT_REPORT = SEED_DIR / "BUILD_REPORT.md"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EXTRACTED_AT = "2026-05-23"
PACKAGE_VERSION = "@ifct2017/compositions@2.0.11"

# Valid controlled vocabularies
VALID_MEAL_TYPES = {"breakfast", "lunch", "dinner"}
VALID_CUISINES = {
    "north_indian", "south_indian", "east_indian", "west_indian",
    "punjabi", "bengali", "gujarati", "maharashtrian",
    "tamil", "kerala", "andhra", "rajasthani",
    "goan", "sindhi",
    "continental", "chinese_indo", "pan_asian",
}
VALID_SOURCES = {"ifct", "usda", "composed"}
VALID_CONFIDENCE = {"exact", "good", "approximate", "weak"}

AMCHUR_MULTIPLIER = 9.0  # moisture ratio: fresh ~80% water to dried ~10% water

# ---------------------------------------------------------------------------
# IFCT CSV parsing
# ---------------------------------------------------------------------------

def _parse_ifct_header(header_row: list[str]) -> dict[str, int]:
    """
    Parse the IFCT CSV header row to build a mapping from short field names
    (e.g. 'enerc', 'protcnt', 'ca') to column indices.

    The header format is: "Display Name; short_name" per cell.
    """
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        cell = cell.strip().strip('"')
        if "; " in cell:
            parts = cell.split("; ")
            short = parts[-1].strip()
            mapping[short] = idx
        elif cell:
            mapping[cell.lower().replace(" ", "_")] = idx
    return mapping


def load_ifct_data(ifct_csv_path: Path) -> dict[str, dict[str, float | str]]:
    """
    Load IFCT CSV into a dict keyed by Food Code.
    Returns raw values (no unit conversions yet).
    """
    ifct: dict[str, dict[str, float | str]] = {}

    with open(ifct_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        col_map = _parse_ifct_header(header)

        for row in reader:
            if not row or not row[0].strip().strip('"'):
                continue
            code = row[0].strip().strip('"')
            name = row[1].strip().strip('"') if len(row) > 1 else ""

            def get_float(field: str) -> float:
                idx = col_map.get(field)
                if idx is None or idx >= len(row):
                    return 0.0
                val = row[idx].strip().strip('"')
                if not val:
                    return 0.0
                try:
                    return float(val)
                except ValueError:
                    return 0.0

            ifct[code] = {
                "name": name,
                # Energy
                "enerc": get_float("enerc"),
                # Macros (already in g/100g)
                "protcnt": get_float("protcnt"),
                "fatce": get_float("fatce"),
                "choavldf": get_float("choavldf"),
                "fibtg": get_float("fibtg"),
                "water": get_float("water"),
                "ash": get_float("ash"),
                # Minerals (in g/100g — need ×1000 for mg)
                "ca": get_float("ca"),
                "fe": get_float("fe"),
                "na": get_float("na"),
                "k": get_float("k"),
                "mg": get_float("mg"),
                "zn": get_float("zn"),
                "cu": get_float("cu"),
                "p": get_float("p"),
                "se": get_float("se"),
                # Vitamins
                "vitc": get_float("vitc"),  # g/100g → ×1000 for mg
                # Fat-soluble vitamins (g/100g → ×1,000,000 for μg)
                "vita": get_float("vita"),
                "retol": get_float("retol"),
                "ergcal": get_float("ergcal"),
                "chocal": get_float("chocal"),
                "folsum": get_float("folsum"),
                # β-Carotene equivalents for vitamin A calculation
                "cartbeq": get_float("cartbeq"),
            }

    return ifct


def compute_nutrition_from_ifct(
    ifct_row: dict[str, float | str],
    multiplier: float = 1.0,
) -> dict[str, Any]:
    """
    Convert raw IFCT values to the per_100g_nutrition schema.

    Unit conversions per PROJECT_SPEC.json ifct_data_conventions:
      - enerc (kJ) → kcal: divide by 4.184
      - Minerals: ×1000 → mg
      - vitc: ×1000 → mg
      - Fat-soluble vitamins + folate: ×1,000,000 → μg
      - Macros: already in grams
    """
    def val(field: str) -> float:
        v = ifct_row.get(field, 0.0)
        if isinstance(v, str):
            return 0.0
        return float(v) * multiplier

    calories = round(val("enerc") / 4.184)
    protein_g = round(val("protcnt"), 2)
    carbs_g = round(val("choavldf"), 2)
    fat_g = round(val("fatce"), 2)
    fiber_g = round(val("fibtg"), 2)

    # Minerals: g → mg (×1000)
    iron_mg = round(val("fe") * 1000, 2)
    calcium_mg = round(val("ca") * 1000, 2)
    potassium_mg = round(val("k") * 1000, 2)
    sodium_mg = round(val("na") * 1000, 2)
    magnesium_mg = round(val("mg") * 1000, 2)
    zinc_mg = round(val("zn") * 1000, 2)

    # Vitamin C: g → mg (×1000)
    vit_c_mg = round(val("vitc") * 1000, 2)

    # Vitamin A: retol + cartbeq → μg (×1,000,000)
    # retol is preformed vitamin A in grams, cartbeq is β-carotene equivalents in grams
    retol_ug = val("retol") * 1_000_000
    cartbeq_ug = val("cartbeq") * 1_000_000
    vit_a_ug = retol_ug + cartbeq_ug
    # Convert μg RAE to IU: 1 μg retinol = 3.33 IU, 1 μg β-carotene eq = 0.167 IU (as RAE)
    # Actually, simpler: store as μg total (retol + cartbeq), then note we say IU
    # The spec says "vit_a_iu": float — assume retol+cartbeq
    # Using: 1 μg retinol = 3.33 IU, 1 μg β-carotene = 1.67 IU
    # But for simplicity and per the spec instruction "assume retol+cartbeq for now",
    # we'll convert the total μg to IU using the retinol conversion factor
    vit_a_iu = round(retol_ug * 3.33 + cartbeq_ug * 1.67, 2)

    # Folate: g → μg (×1,000,000)
    folate_ug = round(val("folsum") * 1_000_000, 2)

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
            "vit_b12_ug": None,  # Always null for source=ifct
        },
    }


def make_zero_nutrition(micros_null: bool = False) -> dict[str, Any]:
    """Return all-zero per_100g_nutrition."""
    return {
        "calories": 0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": 0.0,
        "micronutrients": {
            "iron_mg": None if micros_null else 0.0,
            "calcium_mg": None if micros_null else 0.0,
            "vit_c_mg": None if micros_null else 0.0,
            "potassium_mg": None if micros_null else 0.0,
            "sodium_mg": None if micros_null else 0.0,
            "magnesium_mg": None if micros_null else 0.0,
            "zinc_mg": None if micros_null else 0.0,
            "vit_a_iu": None if micros_null else 0.0,
            "folate_ug": None if micros_null else 0.0,
            "vit_b12_ug": None,
        },
    }


# ---------------------------------------------------------------------------
# Phase 5A — Build ingredients.json
# ---------------------------------------------------------------------------

def build_ingredients(ifct_data: dict[str, dict[str, float | str]]) -> list[dict[str, Any]]:
    """Build the ingredients list from ingredient_mapping.csv + IFCT data."""
    ingredients: list[dict[str, Any]] = []
    errors: list[str] = []

    with open(MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):
            app_id = row["app_id"].strip()
            source = row["source"].strip()
            ifct_code = row.get("ifct_code", "").strip()
            ifct_name = row.get("ifct_name_used", "").strip()
            usda_fdc_id_raw = row.get("usda_fdc_id", "").strip()
            usda_desc = row.get("usda_description", "").strip()
            confidence = row.get("confidence", "").strip()
            mapping_notes = row.get("mapping_notes", "").strip()

            # Parse usda_fdc_id
            usda_fdc_id: int | None = None
            if usda_fdc_id_raw:
                try:
                    usda_fdc_id = int(usda_fdc_id_raw)
                except ValueError:
                    pass

            # Resolve per_100g_nutrition
            per_100g: dict[str, Any]
            data_status: str | None = None

            if source == "ifct":
                if ifct_code not in ifct_data:
                    errors.append(
                        f"ERROR: IFCT row not found for app_id='{app_id}', "
                        f"ifct_code='{ifct_code}' (row {row_num})"
                    )
                    continue
                per_100g = compute_nutrition_from_ifct(ifct_data[ifct_code])

            elif source == "usda":
                if usda_fdc_id and confidence in ("exact", "good", "approximate"):
                    # TODO: Run a separate USDA fetch pass to populate real values.
                    # For now, use placeholder zeros per Phase 5A spec.
                    per_100g = make_zero_nutrition()
                else:
                    # No FDC ID or confidence=weak
                    per_100g = make_zero_nutrition(micros_null=True)
                    data_status = "missing_no_usda_match"

            elif source == "composed":
                # amchur_powder_raw special case
                if app_id == "amchur_powder_raw":
                    if ifct_code not in ifct_data:
                        errors.append(
                            f"ERROR: IFCT row not found for composed ingredient "
                            f"app_id='{app_id}', ifct_code='{ifct_code}' (row {row_num})"
                        )
                        continue
                    per_100g = compute_nutrition_from_ifct(
                        ifct_data[ifct_code], multiplier=AMCHUR_MULTIPLIER
                    )
                else:
                    errors.append(
                        f"ERROR: Unknown composed ingredient app_id='{app_id}' "
                        f"(row {row_num}). Only amchur_powder_raw is supported."
                    )
                    continue
            else:
                errors.append(
                    f"ERROR: Unknown source='{source}' for app_id='{app_id}' "
                    f"(row {row_num})"
                )
                continue

            # Parse aliases (semicolon-split)
            aliases_raw = row.get("app_aliases", "").strip()
            aliases = [a.strip() for a in aliases_raw.split(";") if a.strip()] if aliases_raw else []

            # Parse allergens (semicolon-split)
            allergens_raw = row.get("allergens", "").strip()
            allergen_tags = [a.strip() for a in allergens_raw.split(";") if a.strip()] if allergens_raw else []

            # Parse dietary_tags
            # IFCT rows use space-separated; others use semicolon-separated
            diet_tags_raw = row.get("dietary_tags", "").strip()
            if diet_tags_raw:
                if source == "ifct" or source == "composed":
                    diet_tags = [t.strip() for t in diet_tags_raw.split() if t.strip()]
                else:
                    # For USDA rows, check if semicolons exist
                    if ";" in diet_tags_raw:
                        diet_tags = [t.strip() for t in diet_tags_raw.split(";") if t.strip()]
                    else:
                        # Fall back to space-split (all rows in the actual data use space-separated)
                        diet_tags = [t.strip() for t in diet_tags_raw.split() if t.strip()]
            else:
                diet_tags = []

            # Parse household_units JSON
            hu_raw = row.get("household_units", "").strip()
            household_units: dict[str, float] = {}
            if hu_raw:
                try:
                    household_units = json.loads(hu_raw)
                except json.JSONDecodeError:
                    errors.append(
                        f"ERROR: Malformed household_units JSON for app_id='{app_id}' "
                        f"(row {row_num}): {hu_raw[:100]}"
                    )
                    continue

            # Parse cooked_yield_ratio
            cyr_raw = row.get("cooked_yield_ratio", "1").strip()
            try:
                cooked_yield_ratio = float(cyr_raw)
            except ValueError:
                cooked_yield_ratio = 1.0

            # Build provenance
            provenance: dict[str, Any] = {
                "source": source,
                "ifct_code": ifct_code if ifct_code else None,
                "ifct_name": ifct_name if ifct_name else None,
                "usda_fdc_id": usda_fdc_id,
                "usda_description": usda_desc if usda_desc else None,
                "confidence": confidence,
                "extracted_at": EXTRACTED_AT,
                "notes": mapping_notes if mapping_notes else None,
            }
            if source == "ifct" or source == "composed":
                provenance["package_version"] = PACKAGE_VERSION

            # Build final ingredient object
            ingredient: dict[str, Any] = {
                "app_id": app_id,
                "name": row.get("app_name", "").strip(),
                "aliases": aliases,
                "category": row.get("category", "").strip(),
                "form": row.get("form", "raw").strip(),
                "cooked_yield_ratio": cooked_yield_ratio,
                "per_100g_nutrition": per_100g,
                "household_units": household_units,
                "allergen_tags": allergen_tags,
                "diet_tags": diet_tags,
                "provenance": provenance,
            }

            if data_status:
                ingredient["data_status"] = data_status

            ingredients.append(ingredient)

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\n❌ {len(errors)} error(s) found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Sort by app_id
    ingredients.sort(key=lambda x: x["app_id"])
    return ingredients


# ---------------------------------------------------------------------------
# Phase 5B — Build household_units.json
# ---------------------------------------------------------------------------

def build_household_units(ingredients: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract household units from ingredients into a flat list."""
    units: list[dict[str, Any]] = []

    for ing in ingredients:
        app_id = ing["app_id"]
        hu = ing.get("household_units", {})
        for unit_name, grams in hu.items():
            units.append({
                "unit_name": unit_name,
                "ingredient_app_id": app_id,
                "grams": float(grams),
            })

    # Sort for deterministic output
    units.sort(key=lambda x: (x["ingredient_app_id"], x["unit_name"]))
    return units


# ---------------------------------------------------------------------------
# Phase 5C — Build recipes.json
# ---------------------------------------------------------------------------

def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug from a recipe name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


def build_recipes(ingredient_app_ids: set[str]) -> list[dict[str, Any]]:
    """Build recipes from batch JSON files."""
    all_recipes: list[dict[str, Any]] = []
    errors: list[str] = []

    batch_files = sorted(glob.glob(str(BATCH_DIR / "batch_*.json")))
    if not batch_files:
        print("ERROR: No batch files found.", file=sys.stderr)
        sys.exit(1)

    for batch_file in batch_files:
        batch_name = os.path.basename(batch_file)
        try:
            with open(batch_file, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"ERROR: Malformed JSON in {batch_name}: {e}")
            continue

        # Extract recipes based on file shape
        if isinstance(data, dict) and "corrected_recipes" in data:
            recipes = data["corrected_recipes"]
        elif isinstance(data, list):
            recipes = data
        else:
            errors.append(
                f"ERROR: Unexpected shape in {batch_name}. "
                f"Expected 'corrected_recipes' key or top-level array."
            )
            continue

        if not isinstance(recipes, list):
            errors.append(f"ERROR: Recipes in {batch_name} is not a list.")
            continue

        for i, recipe in enumerate(recipes):
            if not isinstance(recipe, dict):
                errors.append(f"ERROR: Recipe {i} in {batch_name} is not a dict.")
                continue

            recipe_name = recipe.get("name", f"unknown_recipe_{i}")

            # Validate ingredients
            recipe_ingredients = recipe.get("ingredients", [])
            if not recipe_ingredients:
                errors.append(f"ERROR: Recipe '{recipe_name}' in {batch_name} has no ingredients.")
                continue

            for ing in recipe_ingredients:
                ing_name = ing.get("ingredient_name", "")
                if ing_name not in ingredient_app_ids:
                    errors.append(
                        f"ERROR: Recipe '{recipe_name}' in {batch_name} uses "
                        f"ingredient '{ing_name}' which is not in ingredients.json."
                    )

            # Validate instructions
            instructions = recipe.get("instructions", [])
            if not instructions:
                errors.append(f"ERROR: Recipe '{recipe_name}' in {batch_name} has no instructions.")
                continue

            # Validate meal_type
            meal_type = recipe.get("meal_type", "")
            if meal_type not in VALID_MEAL_TYPES:
                errors.append(
                    f"ERROR: Recipe '{recipe_name}' in {batch_name} has invalid "
                    f"meal_type='{meal_type}'."
                )

            # Validate cuisine
            cuisine = recipe.get("cuisine", "")
            if cuisine not in VALID_CUISINES:
                errors.append(
                    f"ERROR: Recipe '{recipe_name}' in {batch_name} has invalid "
                    f"cuisine='{cuisine}'."
                )

            # Build transformed ingredients
            transformed_ingredients: list[dict[str, Any]] = []
            for ing in recipe_ingredients:
                transformed_ingredients.append({
                    "ingredient_app_id": ing.get("ingredient_name", ""),
                    "quantity_grams": float(ing.get("quantity_grams", 0)),
                    "display_quantity": float(ing.get("display_quantity", 0)),
                    "display_unit": ing.get("display_unit", ""),
                    "notes": ing.get("notes", ""),
                })

            # Build final recipe object
            final_recipe: dict[str, Any] = {
                "name": recipe_name,
                "meal_type": meal_type,
                "cuisine": cuisine,
                "diet_tags": recipe.get("diet_tags", []),
                "allergen_tags": recipe.get("allergen_tags", []),
                "prep_time_min": int(recipe.get("prep_time_min", 0)),
                "cook_time_min": int(recipe.get("cook_time_min", 0)),
                "servings": int(recipe.get("servings", 1)),
                "estimated_difficulty": recipe.get("estimated_difficulty", "intermediate"),
                "spice_level": recipe.get("spice_level", "medium"),
                "ingredients": transformed_ingredients,
                "instructions": instructions,
                "source": "seed",
            }

            # Optional fields
            name_alt = recipe.get("name_alt")
            if name_alt:
                final_recipe["name_alt"] = name_alt

            all_recipes.append(final_recipe)

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\n❌ {len(errors)} error(s) found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Generate slugs with collision handling
    slug_counts: dict[str, int] = {}
    for recipe in all_recipes:
        base_slug = generate_slug(recipe["name"])
        if base_slug in slug_counts:
            slug_counts[base_slug] += 1
            recipe["slug"] = f"{base_slug}-{slug_counts[base_slug]}"
        else:
            slug_counts[base_slug] = 1
            recipe["slug"] = base_slug

    # Sort by slug
    all_recipes.sort(key=lambda x: x["slug"])

    return all_recipes


# ---------------------------------------------------------------------------
# Phase 5D — Validation
# ---------------------------------------------------------------------------

def validate_outputs(
    ingredients: list[dict[str, Any]],
    recipes: list[dict[str, Any]],
    source_counts: dict[str, int],
) -> list[str]:
    """Run all validation checks. Returns list of errors (empty = pass)."""
    errors: list[str] = []

    # 1. ingredients.json has 136 entries, all with unique app_id
    if len(ingredients) != 136:
        errors.append(
            f"VALIDATION FAILED: Expected 136 ingredients, got {len(ingredients)}."
        )
    app_ids = [i["app_id"] for i in ingredients]
    if len(app_ids) != len(set(app_ids)):
        dupes = [aid for aid in app_ids if app_ids.count(aid) > 1]
        errors.append(f"VALIDATION FAILED: Duplicate app_ids: {set(dupes)}")

    # 2. recipes.json has 211 entries, all with unique slug
    if len(recipes) != 211:
        errors.append(
            f"VALIDATION FAILED: Expected 211 recipes, got {len(recipes)}."
        )
    slugs = [r["slug"] for r in recipes]
    if len(slugs) != len(set(slugs)):
        dupes = [s for s in slugs if slugs.count(s) > 1]
        errors.append(f"VALIDATION FAILED: Duplicate slugs: {set(dupes)}")

    # 3. Every recipe's ingredient_app_id references a real ingredient
    ingredient_set = set(app_ids)
    for recipe in recipes:
        for ing in recipe.get("ingredients", []):
            if ing["ingredient_app_id"] not in ingredient_set:
                errors.append(
                    f"VALIDATION FAILED: Recipe '{recipe['name']}' references "
                    f"unknown ingredient '{ing['ingredient_app_id']}'."
                )

    # 4. Every recipe has non-empty ingredients and instructions
    for recipe in recipes:
        if not recipe.get("ingredients"):
            errors.append(
                f"VALIDATION FAILED: Recipe '{recipe['name']}' has empty ingredients."
            )
        if not recipe.get("instructions"):
            errors.append(
                f"VALIDATION FAILED: Recipe '{recipe['name']}' has empty instructions."
            )

    # 5. No NaN, Infinity in nutrition data
    for ing in ingredients:
        nutr = ing.get("per_100g_nutrition", {})
        for key, val in nutr.items():
            if key == "micronutrients":
                for mk, mv in val.items():
                    if mv is not None and (math.isnan(mv) or math.isinf(mv)):
                        errors.append(
                            f"VALIDATION FAILED: Ingredient '{ing['app_id']}' has "
                            f"NaN/Inf in micronutrients.{mk}."
                        )
            elif val is not None and isinstance(val, (int, float)):
                if math.isnan(val) or math.isinf(val):
                    errors.append(
                        f"VALIDATION FAILED: Ingredient '{ing['app_id']}' has "
                        f"NaN/Inf in {key}."
                    )

    # 6. Source distribution matches mapping CSV
    actual_sources: dict[str, int] = {}
    for ing in ingredients:
        src = ing["provenance"]["source"]
        actual_sources[src] = actual_sources.get(src, 0) + 1
    if actual_sources != source_counts:
        errors.append(
            f"VALIDATION FAILED: Source distribution mismatch. "
            f"Expected {source_counts}, got {actual_sources}."
        )

    # 7. All meal_type and cuisine values are valid
    for recipe in recipes:
        if recipe["meal_type"] not in VALID_MEAL_TYPES:
            errors.append(
                f"VALIDATION FAILED: Recipe '{recipe['name']}' has invalid "
                f"meal_type='{recipe['meal_type']}'."
            )
        if recipe["cuisine"] not in VALID_CUISINES:
            errors.append(
                f"VALIDATION FAILED: Recipe '{recipe['name']}' has invalid "
                f"cuisine='{recipe['cuisine']}'."
            )

    return errors


# ---------------------------------------------------------------------------
# Phase 5E — Build report
# ---------------------------------------------------------------------------

def write_report(
    ingredients: list[dict[str, Any]],
    household_units: list[dict[str, Any]],
    recipes: list[dict[str, Any]],
) -> None:
    """Write BUILD_REPORT.md."""
    # Source distribution
    source_dist: dict[str, int] = {}
    for ing in ingredients:
        src = ing["provenance"]["source"]
        source_dist[src] = source_dist.get(src, 0) + 1

    # Meal type distribution
    meal_dist: dict[str, int] = {}
    for r in recipes:
        mt = r["meal_type"]
        meal_dist[mt] = meal_dist.get(mt, 0) + 1

    # Cuisine distribution
    cuisine_dist: dict[str, int] = {}
    for r in recipes:
        c = r["cuisine"]
        cuisine_dist[c] = cuisine_dist.get(c, 0) + 1

    # Weak confidence ingredients
    weak_ingredients = [
        ing for ing in ingredients
        if ing["provenance"]["confidence"] == "weak"
    ]

    # Missing USDA match
    missing_usda = [
        ing for ing in ingredients
        if ing.get("data_status") == "missing_no_usda_match"
    ]

    # File sizes
    sizes = {
        "ingredients.json": os.path.getsize(OUT_INGREDIENTS),
        "household_units.json": os.path.getsize(OUT_HOUSEHOLD),
        "recipes.json": os.path.getsize(OUT_RECIPES),
    }

    # SHA-256 hashes
    hashes: dict[str, str] = {}
    for fname, fpath in [
        ("ingredients.json", OUT_INGREDIENTS),
        ("household_units.json", OUT_HOUSEHOLD),
        ("recipes.json", OUT_RECIPES),
    ]:
        with open(fpath, "rb") as f:
            hashes[fname] = hashlib.sha256(f.read()).hexdigest()

    report_lines = [
        "# Seed Data Build Report",
        "",
        f"**Build date:** {date.today().isoformat()}",
        f"**Script:** `scripts/build_seed_data.py`",
        "",
        "---",
        "",
        "## Counts",
        "",
        "### Ingredients by source",
        "",
        "| Source | Count |",
        "|--------|-------|",
    ]
    for src in sorted(source_dist):
        report_lines.append(f"| {src} | {source_dist[src]} |")
    report_lines.append(f"| **Total** | **{len(ingredients)}** |")
    report_lines.append("")

    report_lines.extend([
        f"### Household units: {len(household_units)} entries",
        "",
        "### Recipes by meal_type",
        "",
        "| Meal Type | Count |",
        "|-----------|-------|",
    ])
    for mt in sorted(meal_dist):
        report_lines.append(f"| {mt} | {meal_dist[mt]} |")
    report_lines.append(f"| **Total** | **{len(recipes)}** |")
    report_lines.append("")

    report_lines.extend([
        "### Recipes by cuisine",
        "",
        "| Cuisine | Count |",
        "|---------|-------|",
    ])
    for c in sorted(cuisine_dist):
        report_lines.append(f"| {c} | {cuisine_dist[c]} |")
    report_lines.append("")

    report_lines.extend([
        "---",
        "",
        "## Weak confidence ingredients",
        "",
        "These ingredients have `confidence=weak` and need future improvement:",
        "",
    ])
    if weak_ingredients:
        for ing in weak_ingredients:
            report_lines.append(
                f"- **{ing['app_id']}** ({ing['name']}) — "
                f"source: {ing['provenance']['source']}, "
                f"notes: {ing['provenance'].get('notes', 'N/A')}"
            )
    else:
        report_lines.append("None.")
    report_lines.append("")

    report_lines.extend([
        "## Missing USDA match ingredients",
        "",
        "These ingredients have `data_status=missing_no_usda_match` and need "
        "USDA fetch in a future phase:",
        "",
    ])
    if missing_usda:
        for ing in missing_usda:
            report_lines.append(
                f"- **{ing['app_id']}** ({ing['name']}) — "
                f"notes: {ing['provenance'].get('notes', 'N/A')}"
            )
    else:
        report_lines.append("None.")
    report_lines.append("")

    report_lines.extend([
        "---",
        "",
        "## Output files",
        "",
        "| File | Size | SHA-256 |",
        "|------|------|---------|",
    ])
    for fname in sorted(sizes):
        size_kb = sizes[fname] / 1024
        report_lines.append(
            f"| {fname} | {sizes[fname]:,} bytes ({size_kb:.1f} KB) | "
            f"`{hashes[fname][:16]}...` |"
        )
    report_lines.append("")

    report_lines.extend([
        "### Full SHA-256 hashes",
        "",
    ])
    for fname in sorted(hashes):
        report_lines.append(f"- `{fname}`: `{hashes[fname]}`")
    report_lines.append("")

    report_lines.extend([
        "---",
        "",
        "## Notes",
        "",
        "- USDA-sourced ingredients use placeholder zero values. Run a USDA fetch ",
        "  pass to populate real nutrition data.",
        "- Vitamin B12 is always null for IFCT-sourced ingredients (IFCT does not ",
        "  measure B12). A USDA B12 overlay should be applied for animal products.",
        "- The `composed` source (amchur_powder_raw) uses a 9× multiplier on mango ",
        "  (E036) IFCT values to approximate dried mango powder nutrition.",
        "- Three recipe cuisines (`rajasthani`, `tamil`, `kerala`) extend the ",
        "  PROJECT_SPEC controlled vocab. Update the spec to include these.",
        "- Pomfret (pomfret_raw) has ifct_code=S006 in ingredient_mapping.csv which ",
        "  maps to Rohu in IFCT. The mapping_notes reference P057 (white pomfret). ",
        "  This is a data discrepancy in the input CSV that should be corrected.",
        "",
    ])

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_json(data: Any, path: Path) -> None:
    """Write JSON with 2-space indent, ensure_ascii=False, sorted keys at top level."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")  # trailing newline


def count_sources_from_csv() -> dict[str, int]:
    """Count source distribution directly from the mapping CSV."""
    counts: dict[str, int] = {}
    with open(MAPPING_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = row["source"].strip()
            counts[src] = counts.get(src, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Phase 5 — Seed Data Build")
    print("=" * 60)

    # Verify input files exist
    for path, desc in [
        (MAPPING_CSV, "ingredient_mapping.csv"),
        (IFCT_CSV, "IFCT index.csv"),
    ]:
        if not path.exists():
            print(f"❌ MISSING: {desc} at {path}", file=sys.stderr)
            sys.exit(1)

    batch_files = sorted(glob.glob(str(BATCH_DIR / "batch_*.json")))
    if len(batch_files) < 1:
        print(
            f"❌ No batch files found in {BATCH_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"✓ All input files verified ({len(batch_files)} batch files)")

    # Load IFCT data
    print("\n--- Phase 5A: Building ingredients.json ---")
    ifct_data = load_ifct_data(IFCT_CSV)
    print(f"  Loaded {len(ifct_data)} IFCT entries")

    source_counts = count_sources_from_csv()
    print(f"  Source distribution from CSV: {source_counts}")

    ingredients = build_ingredients(ifct_data)
    print(f"  Built {len(ingredients)} ingredients")
    write_json(ingredients, OUT_INGREDIENTS)
    print(f"  ✓ Written to {OUT_INGREDIENTS.relative_to(BASE_DIR)}")

    # Phase 5B
    print("\n--- Phase 5B: Building household_units.json ---")
    household_units = build_household_units(ingredients)
    print(f"  Built {len(household_units)} household unit entries")
    write_json(household_units, OUT_HOUSEHOLD)
    print(f"  ✓ Written to {OUT_HOUSEHOLD.relative_to(BASE_DIR)}")

    # Phase 5C
    print("\n--- Phase 5C: Building recipes.json ---")
    ingredient_app_ids = {i["app_id"] for i in ingredients}
    recipes = build_recipes(ingredient_app_ids)
    print(f"  Built {len(recipes)} recipes")
    write_json(recipes, OUT_RECIPES)
    print(f"  ✓ Written to {OUT_RECIPES.relative_to(BASE_DIR)}")

    # Phase 5D — Validation
    print("\n--- Phase 5D: Validation ---")
    validation_errors = validate_outputs(ingredients, recipes, source_counts)
    if validation_errors:
        for e in validation_errors:
            print(f"  ❌ {e}", file=sys.stderr)
        print(f"\n❌ {len(validation_errors)} validation error(s). Build FAILED.", file=sys.stderr)
        # Clean up invalid output files
        for p in [OUT_INGREDIENTS, OUT_HOUSEHOLD, OUT_RECIPES]:
            if p.exists():
                p.unlink()
        sys.exit(1)

    print("  ✓ All validation checks passed")

    # Phase 5E — Build report
    print("\n--- Phase 5E: Build report ---")
    write_report(ingredients, household_units, recipes)
    print(f"  ✓ Written to {OUT_REPORT.relative_to(BASE_DIR)}")

    # Summary
    print("\n" + "=" * 60)
    print("✅ BUILD SUCCESSFUL")
    print("=" * 60)

    # Ingredient source summary
    source_summary: dict[str, int] = {}
    for ing in ingredients:
        src = ing["provenance"]["source"]
        source_summary[src] = source_summary.get(src, 0) + 1
    print(f"\nIngredients: {len(ingredients)}")
    for src in sorted(source_summary):
        print(f"  {src}: {source_summary[src]}")

    # Recipe summary
    meal_summary: dict[str, int] = {}
    cuisine_summary: dict[str, int] = {}
    for r in recipes:
        meal_summary[r["meal_type"]] = meal_summary.get(r["meal_type"], 0) + 1
        cuisine_summary[r["cuisine"]] = cuisine_summary.get(r["cuisine"], 0) + 1
    print(f"\nRecipes: {len(recipes)}")
    print("  By meal_type:")
    for mt in sorted(meal_summary):
        print(f"    {mt}: {meal_summary[mt]}")
    print("  By cuisine:")
    for c in sorted(cuisine_summary):
        print(f"    {c}: {cuisine_summary[c]}")

    print(f"\nHousehold units: {len(household_units)}")

    weak = [i for i in ingredients if i["provenance"]["confidence"] == "weak"]
    print(f"\nWeak confidence ingredients: {len(weak)}")
    for w in weak:
        print(f"  - {w['app_id']}")

    # File sizes
    for fname, fpath in [
        ("ingredients.json", OUT_INGREDIENTS),
        ("household_units.json", OUT_HOUSEHOLD),
        ("recipes.json", OUT_RECIPES),
        ("BUILD_REPORT.md", OUT_REPORT),
    ]:
        size = os.path.getsize(fpath)
        print(f"\n{fname}: {size:,} bytes ({size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
