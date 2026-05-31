# M5 — Tracker + Nutrition

Log what the user ate; auto-derive nutrition; daily/weekly aggregates. Two log modes: mark planned/substituted recipe as eaten with fractional servings, or log custom meal with free-text description + mandatory calories + optional macros.

## Prerequisite Gate

- [x] M4 (+ M4.5 + M4.6) acceptance criteria met — 314 tests, 95% coverage
- [x] No new external dependencies required
- [x] No new env vars required

---

## Proposed Changes

### New App: `apps.tracker`

> [!IMPORTANT]
> This creates a brand-new Django app at `apps/tracker/` following the locked per-app layout from CLAUDE.md §7.2.

---

### Registration & Routing

#### [MODIFY] [base.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/nutriplan/settings/base.py)
- Add `"apps.tracker"` to `LOCAL_APPS`

#### [MODIFY] [api_router.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/nutriplan/api_router.py)
- Add `path("tracker/", include("apps.tracker.urls"))` for tracker endpoints
- Add `path("nutrition/", include("apps.tracker.nutrition_urls"))` for nutrition endpoints
- Spec puts tracker endpoints under `/api/v1/tracker/` and nutrition endpoints under `/api/v1/nutrition/`

---

### Models

#### [NEW] `apps/tracker/models.py`

**MealLog**
| Field | Type | Notes |
|-------|------|-------|
| `user` | FK to User, indexed | `on_delete=CASCADE` |
| `log_date` | DateField, indexed | |
| `slot` | CharField enum | `breakfast \| lunch \| dinner` (reuses `SLOT_CHOICES` from mealplans or defines own) |
| `status` | CharField enum | `planned \| ate_planned \| ate_substituted \| ate_custom \| skipped` |
| `planned_recipe` | FK to Recipe, nullable | `SET_NULL` — the recipe that was in the meal plan |
| `actual_recipe` | FK to Recipe, nullable | `SET_NULL` — used when `status=ate_substituted` |
| `servings_eaten` | DecimalField(4,2) default 1.00 | Constrained to 0.25 multiples, range [0.25, 6.00] |
| `custom_description` | CharField(200), nullable | Required when `status=ate_custom` |
| `custom_calories` | PositiveIntegerField, nullable | Required when `status=ate_custom` |
| `custom_protein_g` | DecimalField(6,2), nullable | Optional, for custom meals |
| `custom_carbs_g` | DecimalField(6,2), nullable | Optional, for custom meals |
| `custom_fat_g` | DecimalField(6,2), nullable | Optional, for custom meals |
| `notes` | CharField(500), blank | User notes |
| `logged_at` | DateTimeField auto_now | |
| `unique_together` | `(user, log_date, slot)` | Upsert semantics |

Inherits `TimestampedModel`.

**DailyNutritionSummary**
| Field | Type | Notes |
|-------|------|-------|
| `user` | FK to User | `on_delete=CASCADE` |
| `summary_date` | DateField | |
| `calories` | PositiveIntegerField | Sum from contributing logs |
| `protein_g` | DecimalField(6,2) | |
| `carbs_g` | DecimalField(6,2) | |
| `fat_g` | DecimalField(6,2) | |
| `fiber_g` | DecimalField(6,2) | |
| `micronutrients` | JSONField | Merged key-by-key from recipe cached_nutrition |
| `meals_eaten` | PositiveSmallIntegerField | Count of ate_planned + ate_substituted + ate_custom |
| `meals_skipped` | PositiveSmallIntegerField | Count of skipped |
| `unique_together` | `(user, summary_date)` | |

Inherits `TimestampedModel` (provides `updated_at` for the auto-update timestamp).

---

### Services

#### [NEW] `apps/tracker/services/tracker_service.py`

**`upsert_meal_log(user, log_date, slot, status, **kwargs) -> MealLog`**
- Upserts by `(user, log_date, slot)` — idempotent per spec
- Validates status-specific fields at service layer:
  - `ate_custom`: `custom_description` and `custom_calories` must be non-null
  - Non-custom statuses: all `custom_*` fields must be null (reject if provided)
  - `ate_substituted`: `actual_recipe` (passed as `actual_recipe_id`) must be non-null
- Validates `servings_eaten`:
  - Must be a multiple of 0.25
  - Range: [0.25, 6.00]
  - Only relevant for `ate_planned`, `ate_substituted` (set to 1.00 for `ate_custom`, ignored for `planned`/`skipped`)
- Calls `full_clean()` before `save()`
- Calls `recompute_daily_summary(user, log_date)` synchronously after upsert
- Returns the saved `MealLog`

#### [NEW] `apps/tracker/services/nutrition_service.py`

**`recompute_daily_summary(user, log_date) -> DailyNutritionSummary`**
- Walks all `MealLog` rows for `(user, log_date)`
- For each log, computes nutrition contribution:
  - `ate_planned`: `planned_recipe.cached_nutrition` per-serving values × `servings_eaten`
  - `ate_substituted`: `actual_recipe.cached_nutrition` per-serving values × `servings_eaten`
  - `ate_custom`: `custom_calories` + `custom_protein_g/carbs_g/fat_g` (null → 0)
  - `planned`, `skipped`: zero contribution
- Sums all contributions into totals
- Merges `micronutrients` key-by-key from recipe cached_nutrition (custom logs contribute no micros)
- Counts `meals_eaten` (ate_planned + ate_substituted + ate_custom) and `meals_skipped`
- Upserts `DailyNutritionSummary` by `(user, summary_date)`
- Idempotent — safe to call multiple times for the same date

---

### Serializers

#### [NEW] `apps/tracker/serializers.py`

| Serializer | Purpose |
|------------|---------|
| `MealLogSerializer` | Input: `{log_date, slot, status, actual_recipe_id?, servings_eaten?, custom_description?, custom_calories?, custom_protein_g?, custom_carbs_g?, custom_fat_g?, notes?}` |
| `MealLogResponseSerializer` | Output: full MealLog with nested slim recipe serializers for `planned_recipe` and `actual_recipe` |
| `DailyNutritionSerializer` | Output: `{date, totals: {calories, protein_g, carbs_g, fat_g, fiber_g, micronutrients}, targets: {from profile}, percentage_of_target: {computed}, meals_eaten, meals_skipped}` |
| `WeeklyNutritionSerializer` | Output: list of daily summaries with `averages` dict at top |

---

### Views

#### [NEW] `apps/tracker/views.py`

| View | Method | Endpoint | Description |
|------|--------|----------|-------------|
| `MealLogView` | POST | `/api/v1/tracker/log` | Upsert a meal log |
| `TrackerListView` | GET | `/api/v1/tracker/?date=` | List logs for a date |
| `TrackerRangeView` | GET | `/api/v1/tracker/range?from=&to=` | List logs in date range |
| `DailyNutritionView` | GET | `/api/v1/nutrition/daily?date=` | Daily summary with targets + percentages |
| `WeeklyNutritionView` | GET | `/api/v1/nutrition/weekly?from=&to=` | Weekly summaries with averages |

All views follow thin-view pattern: parse → service → serialize → `success_response()`.

---

### URL Configuration

#### [NEW] `apps/tracker/urls.py`
```
POST tracker/log/
GET  tracker/?date=YYYY-MM-DD
GET  tracker/range?from=YYYY-MM-DD&to=YYYY-MM-DD
```

#### [NEW] `apps/tracker/nutrition_urls.py`
```
GET  nutrition/daily?date=YYYY-MM-DD
GET  nutrition/weekly?from=YYYY-MM-DD&to=YYYY-MM-DD
```

---

### Admin

#### [NEW] `apps/tracker/admin.py`
- Register `MealLog` with list display: user, log_date, slot, status
- Register `DailyNutritionSummary` with list display: user, summary_date, calories, meals_eaten

---

### Error Codes

No new error codes needed. Existing codes cover all cases:
- `VALIDATION_ERROR` — for invalid servings_eaten, missing custom fields, etc.
- `PROFILE_NOT_FOUND` — for nutrition endpoints when user has no profile (needed for targets)
- `NOT_FOUND` — for empty date ranges

---

### Key Design Decisions

1. **Nutrition from `cached_nutrition`**: Recipe-based logs use `recipe.cached_nutrition` which is a JSONField containing `{calories, protein_g, carbs_g, fat_g, fiber_g, micronutrients: {...}}`. Per-serving values are derived by reading the cached values directly (they're already per-serving as computed by `compute_recipe_nutrition`).

2. **Separate URL files**: Tracker and nutrition endpoints live under different URL prefixes (`/tracker/` vs `/nutrition/`) per the spec. Using two URL files in the same app avoids creating a separate app for just 2 nutrition endpoints.

3. **Synchronous recompute**: `recompute_daily_summary` is called synchronously after every `upsert_meal_log`. This is fine for v1 — the summary query touches at most 3 MealLog rows per date. M6 Celery adds a safety-net daily recompute as a batch job.

4. **`planned_recipe` field**: When a user creates a MealLog with `status=ate_planned`, the `planned_recipe` should be auto-populated from the MealPlan for that date/slot if not explicitly provided. The service will look up the active MealPlan to populate this.

---

## Open Questions

> [!IMPORTANT]
> **Q1: Auto-populate `planned_recipe` from MealPlan?**
> When a user logs `ate_planned` or `skipped`, should the service automatically look up the MealPlan for that `(user, log_date, slot)` and set `planned_recipe` to the corresponding recipe? The spec implies this. I plan to implement this — the service will fetch the MealPlan and populate the FK. If no MealPlan exists for that date, the log still succeeds but with `planned_recipe=null`.

> [!IMPORTANT]
> **Q2: `tracker/range` date validation bounds?**
> Should we cap the date range for `GET /tracker/range?from=&to=` to prevent excessively large queries? I'll set a max range of 90 days to be safe. This is a soft limit — easy to adjust later.

---

## Verification Plan

### Automated Tests

Tests in `apps/tracker/tests/`:

| Test | What it verifies |
|------|-----------------|
| `test_log_upsert_idempotent` | POST same (user, date, slot) twice → updates, doesn't duplicate |
| `test_log_creates_summary` | After POST ate_planned, DailyNutritionSummary row exists |
| `test_ate_planned_uses_planned_recipe_for_macros` | Summary calories match planned_recipe.cached_nutrition × servings |
| `test_substituted_uses_actual_recipe_for_macros` | Summary uses actual_recipe, not planned_recipe |
| `test_skipped_contributes_zero_calories` | Log with status=skipped → 0 calories in summary |
| `test_planned_contributes_zero_calories` | Log with status=planned → 0 calories in summary |
| `test_servings_eaten_scales_macros` | servings_eaten=2.0 → double the per-serving calories |
| `test_servings_eaten_rejects_non_quarter_increment` | servings_eaten=0.33 → 400 VALIDATION_ERROR |
| `test_servings_eaten_rejects_above_6` | servings_eaten=7.0 → 400 |
| `test_servings_eaten_rejects_below_025` | servings_eaten=0.10 → 400 |
| `test_ate_custom_requires_description_and_calories` | ate_custom without custom_calories → 400 |
| `test_ate_custom_with_optional_macros` | ate_custom + custom_protein_g works |
| `test_ate_custom_contributes_custom_fields_to_summary` | Summary includes custom calories |
| `test_non_custom_status_rejects_custom_fields` | ate_planned + custom_calories → 400 |
| `test_daily_endpoint_returns_targets_and_percentages` | GET nutrition/daily includes profile targets |
| `test_weekly_endpoint_includes_averages` | GET nutrition/weekly has averages dict |
| `test_summary_includes_ate_custom_in_meals_eaten_count` | meals_eaten counts custom logs |

### Lint & Type Checks
```bash
make lint   # ruff + black --check + mypy --strict
make test   # all tests pass, ≥80% coverage on apps/tracker/services/
```

### Manual Verification
- Full curl sequence in `docs/MANUAL_TEST_RUNBOOK.md` update
- End-to-end: create profile → generate meal plan → log meals → check daily nutrition
