#!/usr/bin/env python3
"""
Pre-ETL Audit Script: Validate recipe ingredient names against ingredient_mapping.csv allowlist.

Usage:
    python3 check_allowlist.py

Checks:
    1. Every recipe's ingredient_name must exactly match an app_id from ingredient_mapping.csv
    2. Reports fixable (close match) vs unfixable (no match) violations
    3. Detects duplicate recipe names across batches

Place this script in the corrected_output/ directory, or adjust paths below.
"""

import json
import glob
import csv
import os
from collections import Counter
from difflib import get_close_matches

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPING_CSV = os.path.join(SCRIPT_DIR, '..', '..', 'mappings', 'ingredient_mapping.csv')
BATCH_GLOB = os.path.join(SCRIPT_DIR, 'batch_*.json')

# ── Load allowlist from ingredient_mapping.csv ─────────────────────────────────
with open(MAPPING_CSV, 'r') as f:
    reader = csv.DictReader(f)
    allowlist = {row['app_id'].strip() for row in reader if row['app_id'].strip()}

print(f"{'='*80}")
print(f"PRE-ETL AUDIT: ingredient_mapping.csv allowlist validation")
print(f"{'='*80}")
print(f"Allowlist source: {os.path.abspath(MAPPING_CSV)}")
print(f"Allowlist size:   {len(allowlist)} app_ids")
print(f"{'='*80}\n")

# ── Scan all batch files ───────────────────────────────────────────────────────
violations = []
all_names = []
total_recipes = 0
total_ingredients = 0

batch_files = sorted(
    glob.glob(BATCH_GLOB),
    key=lambda x: int(os.path.basename(x).replace('batch_', '').replace('.json', ''))
)

for filepath in batch_files:
    filename = os.path.basename(filepath)
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Handle both list and dict-wrapped formats
    if isinstance(data, dict) and 'corrected_recipes' in data:
        recipes = data['corrected_recipes']
    elif isinstance(data, list):
        recipes = data
    else:
        recipes = []

    file_violations = []

    for recipe in recipes:
        total_recipes += 1
        recipe_name = recipe.get('name', 'UNKNOWN')
        all_names.append((recipe_name.lower().strip(), filename))

        for ing in recipe.get('ingredients', []):
            total_ingredients += 1
            ing_name = ing.get('ingredient_name', '').strip()

            if ing_name not in allowlist:
                # Find close matches for triage
                close = get_close_matches(ing_name, list(allowlist), n=3, cutoff=0.6)
                violation = {
                    'file': filename,
                    'recipe': recipe_name,
                    'ingredient': ing_name,
                    'close_matches': close,
                    'fixable': len(close) > 0
                }
                violations.append(violation)
                file_violations.append(violation)

    status = '✅' if not file_violations else '❌'
    print(f"{status} {filename}: {len(recipes)} recipes scanned", end='')
    if file_violations:
        print(f" — {len(file_violations)} VIOLATIONS:")
        for v in file_violations:
            fix_hint = f" → FIXABLE: {v['close_matches']}" if v['fixable'] else " → UNFIXABLE (no close match)"
            print(f"     🚨 \"{v['recipe']}\" uses \"{v['ingredient']}\"{fix_hint}")
    else:
        print(" — all clean")

# ── Duplicate recipe name check ────────────────────────────────────────────────
print(f"\n{'='*80}")
print("DUPLICATE RECIPE NAME CHECK")
print(f"{'='*80}\n")

counts = Counter(n[0] for n in all_names)
dupes = {n: [f for nn, f in all_names if nn == n] for n, c in counts.items() if c > 1}

if dupes:
    print(f"⚠️  {len(dupes)} duplicate recipe names found:\n")
    for name, files in sorted(dupes.items()):
        print(f"   \"{name}\" → {files}")
else:
    print("✅ No duplicate recipe names found.")

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
print(f"Total batch files scanned:   {len(batch_files)}")
print(f"Total recipes scanned:       {total_recipes}")
print(f"Total unique recipe names:   {len(counts)}")
print(f"Total ingredients checked:   {total_ingredients}")
print(f"Duplicate recipe names:      {len(dupes)}")
print(f"Allowlist violations:        {len(violations)}")

if violations:
    fixable = [v for v in violations if v['fixable']]
    unfixable = [v for v in violations if not v['fixable']]
    print(f"  ├─ Fixable (close match):  {len(fixable)}")
    print(f"  └─ Unfixable (no match):   {len(unfixable)}")
    print()
    print("⚠️  ACTION REQUIRED before Phase 5 ETL:")
    print("    Fixable:   Typo or close match — fix the ingredient_name in the recipe JSON")
    print("    Unfixable: Ingredient not in allowlist — reject recipe or substitute with closest match")
else:
    print()
    print("✅ ALL CLEAR — every ingredient_name matches an app_id in ingredient_mapping.csv.")
    print("   Safe to proceed to Phase 5 ETL.")
