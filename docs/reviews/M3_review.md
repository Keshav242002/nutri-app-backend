# M3 — Recipes: Code Review

**Reviewer:** Antigravity Agent  
**Date:** 2026-05-23  
**Scope:** All files in the M3 diff (uncommitted), audited against `docs/plans/M3_plan.md`, `CLAUDE.md §7–§8`, and `docs/PROJECT_SPEC.json`  
**Verification:** `make test` → 195 passed (100 in recipes), 93% coverage · `make lint` → all green (ruff + black + mypy)

---

## Summary

M3 is a **solid implementation** — models, services, serializers, views, filters, admin, management commands, and tests are all present, functionally correct, and closely aligned with the plan. The 100 recipe tests (vs 95 planned) all pass, coverage is 90% on seed services and 100% on nutrition services, lint is clean. **No critical blocking issues** were found.

There are **2 major issues**, **5 minor issues**, and **3 observations** documented below. The major issues are about `full_clean()` ordering semantics and a missing spec-mandated log event. None block the push, but both deserve attention before M4.

---

## Critical Issues

**None.**

---

## Major Issues

### M-1. `full_clean()` called AFTER `update_or_create` — validation fires post-save

**Files:** [seed.py:97-103](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L97-L103), [seed.py:180-185](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L180-L185), [seed.py:266-267](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L266-L267)

**Rule:** CLAUDE.md §7: *"Service-layer writes call `model.full_clean()` before `model.save()`"*

**Problem:** `update_or_create()` calls `save()` internally. The code then calls `full_clean()` on the already-saved instance:

```python
obj, created = Ingredient.objects.update_or_create(
    app_id=app_id,
    defaults=defaults,
)
obj.full_clean()  # ← data is already in the DB
```

If `full_clean()` raises `ValidationError`, the invalid data is already committed (unless the caller wraps it in a transaction). The `seed_recipes` management command DOES wrap all three seed calls in `transaction.atomic()`, so in the **only production call path** the data rolls back on validation failure. However, calling `seed_ingredients()` or `seed_household_units()` directly (e.g., from a shell or future code path) would leave invalid rows committed.

**Severity:** Major (architecture rule violation), but mitigated by the atomic transaction wrapper in the management command and by the fact that seed data is curated and pre-validated.

**Recommendation:** Either:
- (a) Build the model instance manually, call `full_clean()`, then `save()` — but lose `update_or_create` idempotency convenience
- (b) Add `@transaction.atomic` to each seed service function individually so the rule is self-contained
- (c) Accept the current approach with a comment explaining the mitigation (pragmatic; the data is curated)

Option (c) is acceptable for M3 given the atomic wrapper exists. Document this as a known deviation.

---

### M-2. Missing `event=recipe_uses_zero_nutrition_ingredient` log event

**File:** [seed.py:200-345](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L200-L345)

**Plan ref:** M3_plan.md line 233: *"WARNING: `event=recipe_uses_zero_nutrition_ingredient` listing affected recipe slugs and trace ingredient app_ids"*

**Problem:** The plan specifies that `seed_recipes` should log a warning when a recipe uses zero-nutrition ingredients (the 12 weak USDA items). This log event is **not implemented**. The code logs `recipe_calorie_out_of_range` and `display_unit_mismatch`, but does not track which recipes use zero-nutrition trace ingredients.

**Impact:** Low functional impact (the data is correct, just not logged for auditing). But it's a spec deviation from the authoritative plan.

**Recommendation:** Add a post-loop check after creating all `RecipeIngredient`s that collects any ingredients where `per_100g_nutrition.calories == 0` and `protein+carbs+fat == 0`, and logs them at WARNING.

---

## Minor Issues

### m-1. `_SEED_ONLY_FIELDS` is dead code with incorrect contents

**File:** [seed.py:12-20](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L12-L20)

**Problem:** This set is defined but never referenced anywhere in the codebase. Worse, it lists `name_hi`, `approximate_price_inr_per_kg`, and `price_as_of_month` as "NOT stored on the Ingredient model" — but all three ARE stored on the model (models.py lines 213, 216-218, 219). Only `aliases`, `household_units`, and `diet_tags` are genuinely seed-only.

**Recommendation:** Delete the constant entirely, or fix it to only contain `{"aliases", "household_units", "diet_tags"}`.

---

### m-2. `compute_recipe_nutrition` does NOT call `full_clean()` before `save()`

**File:** [nutrition.py:85-93](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/nutrition.py#L85-L93)

**Problem:** The nutrition service writes `cached_nutrition`, `cached_calories_per_serving`, `cached_cost_inr`, and `cost_known` to the recipe and calls `save(update_fields=[...])` without a preceding `full_clean()`. Per CLAUDE.md §7, service-layer writes must call `full_clean()` before `save()`.

**Mitigation:** The fields being written are `JSONField`, `PositiveIntegerField`, `DecimalField`, and `BooleanField` — all computed by the service, not user input. The risk of invalid values is negligible. And `update_fields` narrows the save scope.

**Recommendation:** Add `recipe.full_clean()` before the `save()` call for spec compliance, or document the deviation.

---

### m-3. PROGRESS.md not updated for M3

**File:** [PROGRESS.md](file:///Users/keshavrudo/nutriapp/nutri-app-backend/docs/PROGRESS.md)

**Rule:** CLAUDE.md §12: *"Context update protocol — mandatory after every module"*

**Problem:** PROGRESS.md still shows M2 as the latest entry. The M3 entry has not been written. CLAUDE.md §3 still says `Active module: M3_recipes` and `Build order: M0 ✅ → M1 ✅ → M2 → M3 → ...` — M2 and M3 are not marked ✅.

**Note:** This is likely intentional — Claude Code completed the implementation but the user wanted a review before committing. The context update should happen as part of the commit. Flagging for completeness.

---

### m-4. `seed_ingredients` stores `name_hi`, `approximate_price_inr_per_kg`, `price_as_of_month` in defaults but also lists them in `_SEED_ONLY_FIELDS`

**File:** [seed.py:76-95](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/services/seed.py#L76-L95)

**Problem:** This is a consequence of m-1. The defaults dict correctly includes `name_hi` (line 77), `approximate_price_inr_per_kg` (line 82), and `price_as_of_month` (line 83) — these are stored on the model. But `_SEED_ONLY_FIELDS` claims they're not stored. The code works correctly because `_SEED_ONLY_FIELDS` is never used, but the contradiction is confusing.

---

### m-5. `RecipeIngredient.__str__` triggers N+1 if accessed in a list context

**File:** [models.py:349-350](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/models.py#L349-L350)

**Problem:** `__str__` accesses `self.ingredient.name` and `self.recipe.name`, which are ForeignKey references. In admin list views or logging, this triggers additional queries per row unless `select_related("ingredient", "recipe")` is applied. The admin's `RecipeIngredientAdmin` does not set `list_select_related`.

**Impact:** Minor — only affects admin performance with large datasets.

**Recommendation:** Add `list_select_related = ("recipe", "ingredient")` to `RecipeIngredientAdmin`.

---

## Observations (Informational, no action required)

### O-1. Test `test_seed_ingredients_loads_real_seed_file` hardcodes `== 136`

**File:** [test_services.py:269](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/tests/test_services.py#L269)

This test loads the production `ingredients.json` and asserts exactly 136 entries. If ingredients are added or removed in a future data update, this test will break. This is intentional as a regression guard (plan says "~136 ingredients"), so it's fine — just note it's a maintenance point.

### O-2. `RecipeFactory` default `servings=2` but `Recipe` model default is `servings=1`

**File:** [factories.py:76](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/tests/factories.py#L76) vs [models.py:289](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/models.py#L289)

The factory defaults `servings=2` while the model defaults to `1`. This is intentional (seed recipes typically serve 2+, and tests benefit from non-trivial serving counts), but it's a subtle asymmetry worth knowing about.

### O-3. Cost filter annotates `cost_per_serving` as `DecimalField` without explicit precision

**File:** [filters.py:52-55](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/recipes/filters.py#L52-L55)

```python
cost_per_serving=ExpressionWrapper(
    F("cached_cost_inr") / F("servings"),
    output_field=DecimalField(),
)
```

`DecimalField()` without `max_digits`/`decimal_places` works in Postgres (it uses arbitrary precision), but Django's model validation layer may warn. In practice, this is fine for annotation-only fields that are never saved. No action needed.

---

## Conformance Checklist

| Area | Plan Requirement | Status | Notes |
|------|-----------------|--------|-------|
| **Models** | 4 models: Ingredient, HouseholdUnit, Recipe, RecipeIngredient | ✅ | All present with correct fields, constraints, indexes |
| **Ingredient fields** | All 18 fields per spec | ✅ | Exact match including overlays JSONField |
| **Ingredient indexes** | B-tree on category, GIN on allergen_tags | ✅ | |
| **HouseholdUnit** | unique_together (name, ingredient), CASCADE on ingredient | ✅ | |
| **Recipe fields** | All 17 fields per spec | ✅ | Including name_alt, estimated_difficulty, spice_level |
| **Recipe indexes** | 6 B-tree + 2 GIN per spec | ✅ | All 8 indexes present |
| **RecipeIngredient** | PROTECT on ingredient, CASCADE on recipe, SET_NULL on display_unit | ✅ | |
| **RecipeIngredient ordering** | `ordering = ["order"]` | ✅ | |
| **TimestampedModel** | All 4 models inherit | ✅ | |
| **Choice constants** | Exported as module-level constants | ✅ | |
| **Mustard allergen** | In controlled vocab | ✅ | `ALLERGEN_MUSTARD = "mustard"` |
| **seed_ingredients** | Idempotent upsert, calorie fallback, logging | ✅ | |
| **seed_household_units** | Idempotent upsert, resolve ingredient | ✅ | |
| **seed_recipes** | Idempotent upsert, allowlist validation, display_unit resolution, nutrition compute | ✅ | |
| **compute_recipe_nutrition** | Sum × quantity, divide by servings, cost, cost_known | ✅ | |
| **recompute_recipes_using_ingredient** | Filter active, distinct, recompute | ✅ | |
| **seed_recipes command** | transaction.atomic, 3 seed calls | ✅ | |
| **recompute_nutrition command** | All active recipes, summary stats | ✅ | |
| **RecipeListSerializer** | Slim with nutrition_summary, cost_per_serving | ✅ | |
| **RecipeDetailSerializer** | Full with ingredients, instructions, cached_nutrition | ✅ | |
| **RecipeIngredientSerializer** | ingredient_name, app_id, display_unit_name/grams | ✅ | |
| **RecipeListView** | IsAuthenticated, cursor pagination, all 10 filters | ✅ | |
| **RecipeDetailView** | IsAuthenticated, slug lookup, prefetch_related | ✅ | |
| **Response envelope** | success_response wrapper, error envelope for 401/404 | ✅ | |
| **Admin** | All 4 models registered with search/filter/inline | ✅ | |
| **URL registration** | `/api/v1/recipes/` in api_router | ✅ | |
| **Migration** | Single 0001_initial with all indexes | ✅ | |
| **Tests** | ≥95 tests, ≥80% services coverage | ✅ | 100 tests, 90%+ |
| **Lint** | ruff + black + mypy clean | ✅ | |
| **Calorie fallback** | For IFCT oils with enerc=0 | ✅ | Tested with ghee=900 |
| **Zero nutrition logging** | `event=zero_nutrition_ingredient` | ✅ | In seed_ingredients |
| **Display unit mismatch** | >5% deviation warning | ✅ | Tested |
| **Calorie range check** | 50-1200 range warning | ✅ | Tested |
| **`recipe_uses_zero_nutrition_ingredient`** | Per plan line 233 | ❌ | **Not implemented** (M-2) |
| **`full_clean()` before `save()`** | CLAUDE.md §7 | ⚠️ | After `update_or_create` (M-1), missing in nutrition.py (m-2) |
| **PROGRESS.md** | Updated at Step 5 | ❌ | Not yet (m-3, expected pre-commit) |
| **CLAUDE.md §3** | Updated at Step 5 | ❌ | Not yet (expected pre-commit) |

---

## Manual Endpoint Test Guide

Run the dev server and verify these 8 endpoints. Requires: `make migrate && make seed && make run`.

```bash
# Auth: get a valid token first (Firebase or DEV_AUTH_BYPASS if enabled)
TOKEN="Bearer <your-firebase-token>"

# 1. List recipes (basic)
curl -s -H "Authorization: $TOKEN" http://localhost:8000/api/v1/recipes/ | jq '.status, .data.results | length'
# Expected: "success", 20 (page_size default)

# 2. Filter by meal_type
curl -s -H "Authorization: $TOKEN" "http://localhost:8000/api/v1/recipes/?meal_type=breakfast" | jq '.data.results | length'
# Expected: ~29

# 3. Filter by diet_tags (AND semantics)
curl -s -H "Authorization: $TOKEN" "http://localhost:8000/api/v1/recipes/?diet_tags=vegetarian,vegan" | jq '.data.results | length'

# 4. Exclude allergens
curl -s -H "Authorization: $TOKEN" "http://localhost:8000/api/v1/recipes/?exclude_allergens=dairy,gluten" | jq '.data.results | length'

# 5. Search by name
curl -s -H "Authorization: $TOKEN" "http://localhost:8000/api/v1/recipes/?search=dal" | jq '[.data.results[].slug]'

# 6. Cost filter
curl -s -H "Authorization: $TOKEN" "http://localhost:8000/api/v1/recipes/?max_cost_per_serving_inr=30" | jq '.data.results | length'

# 7. Detail endpoint
curl -s -H "Authorization: $TOKEN" http://localhost:8000/api/v1/recipes/dal-tadka/ | jq '.data | {slug, calories: .cached_nutrition.calories, ingredients: [.ingredients[].ingredient_name]}'

# 8. 404 for bad slug
curl -s -H "Authorization: $TOKEN" http://localhost:8000/api/v1/recipes/nonexistent-recipe/ | jq '.'
# Expected: {"status":"error","message":"...","error":{"code":"NOT_FOUND",...}}
```

---

## Final Recommendation

**✅ APPROVE for commit and push**, with two follow-up items to address before M4:

1. **M-2 (missing log event):** Add `event=recipe_uses_zero_nutrition_ingredient` to `seed_recipes`. Low effort, plan compliance.
2. **m-1 (dead code):** Delete `_SEED_ONLY_FIELDS` from seed.py.

The `full_clean()` ordering issue (M-1) is architecturally impure but functionally safe due to the `transaction.atomic()` wrapper in the management command. I recommend adding a brief code comment at lines 101-103 of seed.py explaining this trade-off. The nutrition service `full_clean()` gap (m-2) is similarly low-risk given the fields are computed, not user-supplied.

The implementation is clean, well-tested, and ready for downstream consumption by M4.
