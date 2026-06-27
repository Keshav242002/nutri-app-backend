#!/usr/bin/env python3
"""
Validate computed recipe nutrition against the Anuvaad INDB 2024-11 database.

One-shot, read-only script. Does NOT modify recipes.json, ingredients.json,
or any application code.

Usage:
    python scripts/validate_against_anuvaad.py

Outputs:
    docs/data_quality/anuvaad_validation_report.md
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECIPES_PATH = PROJECT_ROOT / "apps" / "recipes" / "seed_data" / "recipes.json"
INGREDIENTS_PATH = PROJECT_ROOT / "apps" / "recipes" / "seed_data" / "ingredients.json"
ANUVAAD_CSV_PATH = (
    PROJECT_ROOT
    / "apps"
    / "recipes"
    / "seed_data"
    / "sources"
    / "anuvaad"
    / "Anuvaad_INDB_2024.11 - Sheet1.csv"
)
REPORT_DIR = PROJECT_ROOT / "docs" / "data_quality"
REPORT_PATH = REPORT_DIR / "anuvaad_validation_report.md"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
FUZZY_MATCH_THRESHOLD = 75  # minimum similarity to consider a match
CALORIE_FLAG_THRESHOLD = 0.25  # >25% deviation → PROBABLY_WRONG
TOP_N_MATCHES = 3  # fuzzy top-N per recipe


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class NutritionPer100g:
    """Nutrition values per 100g."""

    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    fiber_g: float = 0.0


@dataclass
class AnuvaadEntry:
    """A single row from the Anuvaad CSV."""

    food_code: str
    food_name: str
    food_name_clean: str  # stripped of parenthetical romanised names
    nutrition: NutritionPer100g = field(default_factory=NutritionPer100g)


@dataclass
class MatchResult:
    """Result of fuzzy matching a recipe against Anuvaad."""

    anuvaad_name: str
    similarity: float
    anuvaad_nutrition: NutritionPer100g
    delta_calories: Optional[float] = None
    delta_protein: Optional[float] = None
    delta_carbs: Optional[float] = None
    delta_fat: Optional[float] = None
    delta_fiber: Optional[float] = None


@dataclass
class RecipeValidation:
    """Validation result for a single recipe."""

    name: str
    name_alt: str
    slug: str
    servings: int
    total_weight_grams: float
    computed_nutrition: NutritionPer100g
    matches: list[MatchResult] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    flag: str = ""  # "PROBABLY_WRONG", "NO_MATCH", ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_float(val: str | float | int | None) -> float:
    """Convert a value to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _pct_delta(ours: float, ref: float) -> Optional[float]:
    """Compute abs((ours - ref) / ref) as a fraction. None if ref == 0."""
    if ref == 0:
        return None
    return abs(ours - ref) / ref


def _fmt_pct(val: Optional[float]) -> str:
    """Format a fraction as a percentage string."""
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _strip_parenthetical(name: str) -> str:
    """
    Strip parenthetical romanised names from Anuvaad food_name.
    e.g. "Aloo paratha (Aloo ka parantha)" → "Aloo paratha"
    Also strip leading/trailing whitespace.
    """
    return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_ingredients() -> dict[str, NutritionPer100g]:
    """
    Load ingredients.json and return a dict mapping app_id → NutritionPer100g.
    """
    with open(INGREDIENTS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, NutritionPer100g] = {}
    for ing in raw:
        app_id = ing["app_id"]
        nutr = ing.get("per_100g_nutrition", {})
        result[app_id] = NutritionPer100g(
            calories=_safe_float(nutr.get("calories")),
            protein_g=_safe_float(nutr.get("protein_g")),
            carbs_g=_safe_float(nutr.get("carbs_g")),
            fat_g=_safe_float(nutr.get("fat_g")),
            fiber_g=_safe_float(nutr.get("fiber_g")),
        )
    return result


def load_recipes() -> list[dict]:
    """Load recipes.json."""
    with open(RECIPES_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_anuvaad() -> list[AnuvaadEntry]:
    """
    Load the Anuvaad CSV and return a list of AnuvaadEntry objects.
    Per-100g values are extracted from the top-level columns.
    """
    entries: list[AnuvaadEntry] = []
    with open(ANUVAAD_CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            food_name = row.get("food_name", "").strip()
            entry = AnuvaadEntry(
                food_code=row.get("food_code", "").strip(),
                food_name=food_name,
                food_name_clean=_strip_parenthetical(food_name),
                nutrition=NutritionPer100g(
                    calories=_safe_float(row.get("energy_kcal")),
                    protein_g=_safe_float(row.get("protein_g")),
                    carbs_g=_safe_float(row.get("carb_g")),
                    fat_g=_safe_float(row.get("fat_g")),
                    fiber_g=_safe_float(row.get("fibre_g")),
                ),
            )
            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Nutrition computation
# ---------------------------------------------------------------------------

# Recipes to skip (dry/ambiguous items where weight-based per-100g is misleading)
SKIP_SLUGS = {"papad", "pickle", "chutney"}  # expand as needed


def _should_skip(recipe: dict) -> tuple[bool, str]:
    """
    Decide whether to skip a recipe for per-100g comparison.
    Returns (should_skip, reason).
    """
    slug = recipe.get("slug", "")
    name_lower = recipe.get("name", "").lower()

    # Very low total weight (condiments, garnishes)
    total_grams = sum(
        _safe_float(ing.get("quantity_grams"))
        for ing in recipe.get("ingredients", [])
    )
    if total_grams < 20:
        return True, f"Total weight too low ({total_grams:.0f}g)"

    # Known ambiguous categories
    for kw in SKIP_SLUGS:
        if kw in slug or kw in name_lower:
            return True, f"Ambiguous category (matched '{kw}')"

    return False, ""


def compute_recipe_nutrition_per_100g(
    recipe: dict,
    ingredients_db: dict[str, NutritionPer100g],
) -> tuple[NutritionPer100g, float]:
    """
    Compute total recipe nutrition per 100g from ingredient quantities.

    Returns (NutritionPer100g, total_weight_grams).

    Logic:
    - For each ingredient, nutrition = (quantity_grams / 100) * per_100g_value
    - Sum across all ingredients → total recipe nutrition
    - Divide by (total_weight_grams / 100) → per-100g of the recipe
    """
    total_cal = 0.0
    total_pro = 0.0
    total_carb = 0.0
    total_fat = 0.0
    total_fiber = 0.0
    total_grams = 0.0

    for ing in recipe.get("ingredients", []):
        app_id = ing.get("ingredient_app_id", "")
        qty = _safe_float(ing.get("quantity_grams"))
        if qty <= 0:
            continue

        nutr = ingredients_db.get(app_id)
        if nutr is None:
            # Ingredient not found — contribute weight but zero nutrition
            # (conservative: will underestimate calories)
            total_grams += qty
            continue

        factor = qty / 100.0
        total_cal += nutr.calories * factor
        total_pro += nutr.protein_g * factor
        total_carb += nutr.carbs_g * factor
        total_fat += nutr.fat_g * factor
        total_fiber += nutr.fiber_g * factor
        total_grams += qty

    if total_grams <= 0:
        return NutritionPer100g(), 0.0

    # Normalise to per-100g
    scale = 100.0 / total_grams
    return (
        NutritionPer100g(
            calories=total_cal * scale,
            protein_g=total_pro * scale,
            carbs_g=total_carb * scale,
            fat_g=total_fat * scale,
            fiber_g=total_fiber * scale,
        ),
        total_grams,
    )


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------
def build_anuvaad_lookup(
    entries: list[AnuvaadEntry],
) -> tuple[list[str], dict[str, AnuvaadEntry]]:
    """
    Build a list of matchable names and a reverse lookup.
    Each Anuvaad entry contributes both its original food_name and the
    cleaned (parenthetical-stripped) version.
    Returns (choices_list, name_to_entry_dict).
    """
    choices: list[str] = []
    lookup: dict[str, AnuvaadEntry] = {}

    for entry in entries:
        for name_variant in {entry.food_name, entry.food_name_clean}:
            name_lower = name_variant.strip().lower()
            if name_lower and name_lower not in lookup:
                choices.append(name_lower)
                lookup[name_lower] = entry

    return choices, lookup


def find_best_matches(
    recipe_name: str,
    recipe_name_alt: str,
    choices: list[str],
    lookup: dict[str, AnuvaadEntry],
) -> list[tuple[AnuvaadEntry, float]]:
    """
    Find top-N fuzzy matches for a recipe name against the Anuvaad lookup.
    Tries both recipe.name and recipe.name_alt, deduplicates, and returns
    sorted by descending similarity.
    """
    queries = [q.strip().lower() for q in [recipe_name, recipe_name_alt] if q.strip()]

    # Collect all matches across query variants
    seen: dict[str, tuple[AnuvaadEntry, float]] = {}  # food_code → (entry, score)

    for query in queries:
        results = process.extract(
            query,
            choices,
            scorer=fuzz.token_sort_ratio,
            limit=TOP_N_MATCHES * 2,  # get extra to handle deduplication
        )
        for match_name, score, _idx in results:
            entry = lookup[match_name]
            existing = seen.get(entry.food_code)
            if existing is None or score > existing[1]:
                seen[entry.food_code] = (entry, score)

    # Sort by descending score and take top-N
    ranked = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    return ranked[:TOP_N_MATCHES]


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------
def run_validation() -> list[RecipeValidation]:
    """Run the full validation pipeline."""
    print("Loading data...")
    ingredients_db = load_ingredients()
    recipes = load_recipes()
    anuvaad_entries = load_anuvaad()

    print(f"  Recipes: {len(recipes)}")
    print(f"  Ingredients: {len(ingredients_db)}")
    print(f"  Anuvaad entries: {len(anuvaad_entries)}")

    choices, lookup = build_anuvaad_lookup(anuvaad_entries)
    print(f"  Anuvaad matchable names: {len(choices)}")

    results: list[RecipeValidation] = []

    for i, recipe in enumerate(recipes):
        name = recipe.get("name", "")
        name_alt = recipe.get("name_alt", "")
        slug = recipe.get("slug", "")
        servings = int(_safe_float(recipe.get("servings", 1)))

        # Check skip
        should_skip, skip_reason = _should_skip(recipe)
        if should_skip:
            rv = RecipeValidation(
                name=name,
                name_alt=name_alt,
                slug=slug,
                servings=servings,
                total_weight_grams=0,
                computed_nutrition=NutritionPer100g(),
                skipped=True,
                skip_reason=skip_reason,
            )
            results.append(rv)
            continue

        # Compute per-100g nutrition from ingredients
        nutr_per_100g, total_grams = compute_recipe_nutrition_per_100g(
            recipe, ingredients_db
        )

        rv = RecipeValidation(
            name=name,
            name_alt=name_alt,
            slug=slug,
            servings=servings,
            total_weight_grams=total_grams,
            computed_nutrition=nutr_per_100g,
        )

        # Fuzzy match
        top_matches = find_best_matches(name, name_alt, choices, lookup)

        best_match_above_threshold = False
        for entry, score in top_matches:
            an = entry.nutrition
            mr = MatchResult(
                anuvaad_name=entry.food_name,
                similarity=score,
                anuvaad_nutrition=an,
                delta_calories=_pct_delta(nutr_per_100g.calories, an.calories),
                delta_protein=_pct_delta(nutr_per_100g.protein_g, an.protein_g),
                delta_carbs=_pct_delta(nutr_per_100g.carbs_g, an.carbs_g),
                delta_fat=_pct_delta(nutr_per_100g.fat_g, an.fat_g),
                delta_fiber=_pct_delta(nutr_per_100g.fiber_g, an.fiber_g),
            )
            rv.matches.append(mr)

            if score >= FUZZY_MATCH_THRESHOLD:
                best_match_above_threshold = True

        # Determine flag
        if not best_match_above_threshold:
            rv.flag = "NO_MATCH"
        else:
            # Use best match (highest similarity) for flagging
            best = rv.matches[0]
            if (
                best.similarity >= FUZZY_MATCH_THRESHOLD
                and best.delta_calories is not None
                and best.delta_calories > CALORIE_FLAG_THRESHOLD
            ):
                rv.flag = "PROBABLY_WRONG"

        results.append(rv)

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(recipes)} recipes...")

    print(f"  Processed all {len(recipes)} recipes.")
    return results


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(results: list[RecipeValidation]) -> str:
    """Generate the Markdown validation report."""
    lines: list[str] = []

    # --- Summary stats ---
    total = len(results)
    skipped = sum(1 for r in results if r.skipped)
    evaluated = total - skipped
    matched = sum(
        1
        for r in results
        if not r.skipped
        and r.matches
        and r.matches[0].similarity >= FUZZY_MATCH_THRESHOLD
    )
    no_match = sum(1 for r in results if r.flag == "NO_MATCH")
    flagged = sum(1 for r in results if r.flag == "PROBABLY_WRONG")

    # Average calorie delta for matched recipes
    cal_deltas = [
        r.matches[0].delta_calories
        for r in results
        if not r.skipped
        and r.matches
        and r.matches[0].similarity >= FUZZY_MATCH_THRESHOLD
        and r.matches[0].delta_calories is not None
    ]
    avg_cal_delta = (sum(cal_deltas) / len(cal_deltas)) if cal_deltas else 0
    median_cal_delta = sorted(cal_deltas)[len(cal_deltas) // 2] if cal_deltas else 0

    lines.append("# Anuvaad INDB 2024-11 Validation Report\n")
    lines.append(
        f"*Generated by `scripts/validate_against_anuvaad.py` — "
        f"read-only, no recipes modified.*\n"
    )
    lines.append("## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total recipes | {total} |")
    lines.append(f"| Skipped (ambiguous/condiment) | {skipped} |")
    lines.append(f"| Evaluated | {evaluated} |")
    lines.append(
        f"| Confident match (≥{FUZZY_MATCH_THRESHOLD}% similarity) | "
        f"{matched} ({matched/evaluated*100:.0f}% of evaluated) |"
    )
    lines.append(
        f"| `NO_MATCH` (no match ≥{FUZZY_MATCH_THRESHOLD}%) | {no_match} |"
    )
    lines.append(
        f"| `PROBABLY_WRONG` (calorie delta >{CALORIE_FLAG_THRESHOLD*100:.0f}%) "
        f"| {flagged} |"
    )
    lines.append(
        f"| Mean calorie delta (matched) | {avg_cal_delta*100:.1f}% |"
    )
    lines.append(
        f"| Median calorie delta (matched) | {median_cal_delta*100:.1f}% |"
    )
    lines.append("")

    # --- Top 10 worst calorie deltas ---
    lines.append("## Top 10 Worst Calorie Deltas\n")
    lines.append(
        "Recipes with confident matches (≥75% similarity), ranked by "
        "absolute calorie deviation.\n"
    )

    worst = sorted(
        [
            r
            for r in results
            if not r.skipped
            and r.matches
            and r.matches[0].similarity >= FUZZY_MATCH_THRESHOLD
            and r.matches[0].delta_calories is not None
        ],
        key=lambda r: r.matches[0].delta_calories or 0,
        reverse=True,
    )[:10]

    if worst:
        lines.append(
            "| # | Recipe | Anuvaad Match | Sim% | "
            "Our kcal/100g | Anuvaad kcal/100g | Δ Calories | "
            "Δ Protein | Δ Carbs | Δ Fat | Δ Fiber | Flag |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for idx, r in enumerate(worst, 1):
            m = r.matches[0]
            lines.append(
                f"| {idx} | {r.name} | {m.anuvaad_name} | "
                f"{m.similarity:.0f} | "
                f"{r.computed_nutrition.calories:.1f} | "
                f"{m.anuvaad_nutrition.calories:.1f} | "
                f"{_fmt_pct(m.delta_calories)} | "
                f"{_fmt_pct(m.delta_protein)} | "
                f"{_fmt_pct(m.delta_carbs)} | "
                f"{_fmt_pct(m.delta_fat)} | "
                f"{_fmt_pct(m.delta_fiber)} | "
                f"{r.flag or '✓'} |"
            )
        lines.append("")

    # --- Flagged: PROBABLY_WRONG ---
    prob_wrong = [r for r in results if r.flag == "PROBABLY_WRONG"]
    lines.append(f"## Flagged: `PROBABLY_WRONG` ({len(prob_wrong)} recipes)\n")
    lines.append(
        "Recipes with a confident match but >25% calorie deviation from Anuvaad.\n"
    )
    if prob_wrong:
        lines.append(
            "| Recipe | Anuvaad Match | Sim% | "
            "Our kcal/100g | Anuvaad kcal/100g | Δ Calories |"
        )
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(
            prob_wrong,
            key=lambda r: r.matches[0].delta_calories or 0,
            reverse=True,
        ):
            m = r.matches[0]
            lines.append(
                f"| {r.name} | {m.anuvaad_name} | {m.similarity:.0f} | "
                f"{r.computed_nutrition.calories:.1f} | "
                f"{m.anuvaad_nutrition.calories:.1f} | "
                f"{_fmt_pct(m.delta_calories)} |"
            )
        lines.append("")

    # --- Flagged: NO_MATCH ---
    no_matches = [r for r in results if r.flag == "NO_MATCH"]
    lines.append(f"## Flagged: `NO_MATCH` ({len(no_matches)} recipes)\n")
    lines.append(
        f"Recipes with no Anuvaad match above {FUZZY_MATCH_THRESHOLD}% similarity.\n"
    )
    if no_matches:
        lines.append("| Recipe | Alt Name | Best Match | Best Sim% |")
        lines.append("|---|---|---|---|")
        for r in no_matches:
            best_name = r.matches[0].anuvaad_name if r.matches else "—"
            best_sim = f"{r.matches[0].similarity:.0f}" if r.matches else "—"
            lines.append(
                f"| {r.name} | {r.name_alt} | {best_name} | {best_sim} |"
            )
        lines.append("")

    # --- Skipped recipes ---
    skipped_list = [r for r in results if r.skipped]
    if skipped_list:
        lines.append(f"## Skipped Recipes ({len(skipped_list)})\n")
        lines.append("| Recipe | Reason |")
        lines.append("|---|---|")
        for r in skipped_list:
            lines.append(f"| {r.name} | {r.skip_reason} |")
        lines.append("")

    # --- Full per-recipe detail ---
    lines.append("## Full Per-Recipe Details\n")
    lines.append(
        "| # | Recipe | Alt Name | Weight (g) | Our kcal/100g | "
        "Match? | Best Match | Sim% | Anuvaad kcal/100g | "
        "Δ Cal | Δ Pro | Δ Carb | Δ Fat | Δ Fiber | Flag |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    )

    for idx, r in enumerate(results, 1):
        if r.skipped:
            lines.append(
                f"| {idx} | {r.name} | {r.name_alt} | — | — | "
                f"SKIPPED | — | — | — | — | — | — | — | — | {r.skip_reason} |"
            )
            continue

        has_match = (
            r.matches
            and r.matches[0].similarity >= FUZZY_MATCH_THRESHOLD
        )
        if has_match:
            m = r.matches[0]
            lines.append(
                f"| {idx} | {r.name} | {r.name_alt} | "
                f"{r.total_weight_grams:.0f} | "
                f"{r.computed_nutrition.calories:.1f} | "
                f"Y | {m.anuvaad_name} | {m.similarity:.0f} | "
                f"{m.anuvaad_nutrition.calories:.1f} | "
                f"{_fmt_pct(m.delta_calories)} | "
                f"{_fmt_pct(m.delta_protein)} | "
                f"{_fmt_pct(m.delta_carbs)} | "
                f"{_fmt_pct(m.delta_fat)} | "
                f"{_fmt_pct(m.delta_fiber)} | "
                f"{r.flag or '✓'} |"
            )
        else:
            best_name = r.matches[0].anuvaad_name if r.matches else "—"
            best_sim = f"{r.matches[0].similarity:.0f}" if r.matches else "—"
            lines.append(
                f"| {idx} | {r.name} | {r.name_alt} | "
                f"{r.total_weight_grams:.0f} | "
                f"{r.computed_nutrition.calories:.1f} | "
                f"N | {best_name} | {best_sim} | "
                f"— | — | — | — | — | — | {r.flag} |"
            )

    lines.append("")
    lines.append("---\n")
    lines.append(
        "*Report ends. Review flagged recipes and decide on corrections manually.*\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("Anuvaad INDB 2024-11 Validation")
    print("=" * 60)

    # Pre-flight checks
    for path, label in [
        (RECIPES_PATH, "recipes.json"),
        (INGREDIENTS_PATH, "ingredients.json"),
        (ANUVAAD_CSV_PATH, "Anuvaad CSV"),
    ]:
        if not path.exists():
            print(f"ERROR: {label} not found at {path}")
            sys.exit(1)

    results = run_validation()
    report = generate_report(results)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"\nReport written to: {REPORT_PATH}")

    # Quick summary on stdout
    total = len(results)
    skipped = sum(1 for r in results if r.skipped)
    evaluated = total - skipped
    matched = sum(
        1
        for r in results
        if not r.skipped
        and r.matches
        and r.matches[0].similarity >= FUZZY_MATCH_THRESHOLD
    )
    flagged = sum(1 for r in results if r.flag == "PROBABLY_WRONG")
    no_match = sum(1 for r in results if r.flag == "NO_MATCH")

    print(f"\n{'─' * 40}")
    print(f"Total:            {total}")
    print(f"Skipped:          {skipped}")
    print(f"Evaluated:        {evaluated}")
    print(f"Matched (≥75%):   {matched} ({matched/max(evaluated,1)*100:.0f}%)")
    print(f"PROBABLY_WRONG:   {flagged}")
    print(f"NO_MATCH:         {no_match}")
    print(f"{'─' * 40}")


if __name__ == "__main__":
    main()
