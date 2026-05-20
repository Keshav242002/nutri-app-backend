# M2 — Profiles Plan (Final)

**Date:** 2026-05-17 (all open questions resolved; ready for Claude Code)
**Status:** Awaiting final user approval
**Spec ref:** `docs/PROJECT_SPEC.json :: backend_build_specification.modules.M2_profiles`

---

## Module purpose

M2 introduces `DietaryProfile` — one record per user capturing everything needed for Indian-first meal planning: biometrics, goal, dietary restrictions, cuisine region, budget, and cooking constraints. The six-step onboarding questionnaire feeds this model. `core/utils/nutrition_math.compute_targets` is fully implemented here. M2 activates the `has_profile: true` flag already plumbed in `UserSerializer`.

---

## Prerequisite check

| Gate | Status |
|---|---|
| M1 acceptance criteria met | ✅ All met; amendment commit ef1ce04 pushed |
| No new external dependencies | ✅ `django.contrib.postgres` (built-in); `freezegun==1.5.1` added to `requirements/dev.txt` |

---

## Questionnaire — six steps (one mobile screen each)

### Step 1 — Basics
| Field | Type | Constraints |
|---|---|---|
| `date_of_birth` | `DateField` | age derived ≥ 13 and ≤ 100 at submission |
| `sex` | `CharField(max_length=20)` | `male / female / other / prefer_not_to_say` |
| `height_cm` | `PositiveSmallIntegerField` | 100–250 |
| `weight_kg` | `DecimalField(5,1)` | 30.0–300.0 |

**BMR sex offsets (documented in `nutrition_math.py` with inline comment):**
- `male` → `+5`
- `female` → `−161`
- `other` / `prefer_not_to_say` → average: `((BMR_base + 5) + (BMR_base − 161)) / 2 = BMR_base − 78`

### Step 2 — Activity and goal
| Field | Values |
|---|---|
| `activity_level` | `sedentary / light / moderate / very / athlete` |
| `goal` | `lose_weight / maintain / gain_muscle / gain_weight_healthy / eat_healthier` |

**Goal calorie deltas and macro splits:**

| Goal | kcal Δ | Protein | Carbs | Fat | Fiber |
|---|---|---|---|---|---|
| `lose_weight` | −500 | 35% | 40% | 25% | 14g/1000 kcal |
| `maintain` | 0 | 25% | 50% | 25% | 14g/1000 kcal |
| `gain_muscle` | +300 | 30% | 45% | 25% | 14g/1000 kcal |
| `gain_weight_healthy` | +500 | 25% | 50% | 25% | 14g/1000 kcal |
| `eat_healthier` | 0 | 25% | 50% | 25% | **18g/1000 kcal** |

`eat_healthier` uses elevated fiber (18g vs 14g) to emphasise micronutrient density. The 0 kcal delta means targets equal `maintain`; the distinction is the fiber target and (in M4) a scoring boost for high-fiber recipes.

### Step 3 — Cuisine and region
| Field | Type | Constraints |
|---|---|---|
| `primary_cuisine_region` | `CharField(max_length=20)` | REQUIRED; `north_indian / south_indian / east_indian / west_indian` |
| `secondary_cuisine_preferences` | `ArrayField(CharField(64))` | OPTIONAL; default empty `[]`; controlled vocab (see below) |
| `spice_tolerance` | `CharField(max_length=10)` | REQUIRED; `mild / medium / hot / very_hot` |

Secondary cuisine controlled vocab: `punjabi, gujarati, maharashtrian, bengali, tamil, kerala, andhra, rajasthani, goan, sindhi, continental, chinese_indo, pan_asian`

**Decided (Q1):** empty `secondary_cuisine_preferences` is valid. M4 falls back to `primary_cuisine_region` when it's empty.

### Step 4 — Dietary pattern
| Field | Type | Constraints |
|---|---|---|
| `diet_pattern` | `CharField(max_length=20)` | REQUIRED; `vegetarian / eggetarian / non_vegetarian / pescatarian / vegan / jain` |
| `no_onion_garlic` | `BooleanField` | default `False`; auto-set `True` if `diet_pattern=jain` |
| `allergies` | `ArrayField(CharField(64))` | controlled vocab: `dairy / eggs / gluten / peanuts / tree_nuts / soy / shellfish / fish / sesame / mustard` |
| `dislikes` | `ArrayField(CharField(64))` | free text; max 30 items; each lowercased + stripped on save |

**Jain rule (service layer):** if `data['diet_pattern'] == 'jain'` → set `data['no_onion_garlic'] = True` before saving, regardless of client input.

### Step 5 — Budget and household
| Field | Type | Constraints |
|---|---|---|
| `daily_food_budget_inr` | `DecimalField(8,2)` | null=True; range 50–3000 |
| `weekly_food_budget_inr` | `DecimalField(8,2)` | null=True; range 300–20000 |
| `household_size` | `PositiveSmallIntegerField` | REQUIRED; 1–12; default 1 |
| `cooking_frequency` | `CharField(max_length=15)` | REQUIRED; `daily / weekends_only / rarely` |

**Budget derivation rule (service layer, not serializer):**
- At least one of daily/weekly required → else `AppValidationError(VALIDATION_ERROR)`
- Only `daily` given → `weekly = daily * 7`
- Only `weekly` given → `daily = weekly / 7`
- Both given → `weekly` must equal `daily * 7` within ±5% → else `AppValidationError`

**Decided (Q3):** `target_calories` is **always per-user (individual)**, regardless of `household_size`. `household_size` is stored for v2 family-sync only; it does NOT scale macro targets in v1.

### Step 6 — Cooking constraints + disclaimer
| Field | Type | Constraints |
|---|---|---|
| `max_prep_time_min` | `PositiveSmallIntegerField` | REQUIRED; 10–90; default 30 |
| `skill_level` | `CharField(max_length=15)` | REQUIRED; `beginner / intermediate / advanced` |
| `disclaimer_acknowledged` | write-only `BooleanField` | must be `True` to submit; **NOT stored** |

**Disclaimer text (rendered on screen, not persisted):**
> "NutriPlan suggests meals based on your preferences and is not medical advice. For specific medical dietary needs (diabetes, kidney conditions, pregnancy, lactation, etc.), consult your doctor or registered dietitian."

---

## USER INPUT vs COMPUTED fields

### Stored from user input
`date_of_birth`, `sex`, `height_cm`, `weight_kg`, `activity_level`, `goal`,
`primary_cuisine_region`, `secondary_cuisine_preferences`, `spice_tolerance`,
`diet_pattern`, `no_onion_garlic`, `allergies`, `dislikes`,
`daily_food_budget_inr`, `weekly_food_budget_inr`, `household_size`,
`cooking_frequency`, `max_prep_time_min`, `skill_level`

### Computed on save (by service then `compute_targets`)
`target_calories`, `target_protein_g`, `target_carbs_g`, `target_fat_g`, `target_fiber_g`,
missing budget field (daily derived from weekly or vice versa)

### NEVER stored
**`age`** — derived live from `date_of_birth` at every computation and every read. Storing age creates year-staleness bugs (a user's age changes every year without touching their profile). The serializer exposes `age` as a `SerializerMethodField`. `compute_targets` calls `compute_age(profile.date_of_birth)` internally.

---

## `core/utils/nutrition_math.py` — full implementation

Replaces the existing stub. All constants defined at module top.

```python
GOAL_CALORIE_DELTA: dict[str, int] = {
    "lose_weight": -500, "maintain": 0, "gain_muscle": 300,
    "gain_weight_healthy": 500, "eat_healthier": 0,
}
MACRO_SPLITS: dict[str, list[float]] = {          # [protein_pct, carbs_pct, fat_pct]
    "lose_weight":         [0.35, 0.40, 0.25],
    "maintain":            [0.25, 0.50, 0.25],
    "gain_muscle":         [0.30, 0.45, 0.25],
    "gain_weight_healthy": [0.25, 0.50, 0.25],
    "eat_healthier":       [0.25, 0.50, 0.25],
}
ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
    "very": 1.725, "athlete": 1.9,
}
FIBER_TARGET_PER_1000_KCAL: dict[str, float] = {
    "default": 14.0,
    "eat_healthier": 18.0,   # elevated to emphasise micronutrient density
}
```

### `compute_age(dob: date, today: date | None = None) -> int`

```
def compute_age(dob, today=None):
    if today is None:
        today = date.today()   # called at runtime — never cached at module load
    return (today - dob).days // 365
```

Tests use `freezegun` or pass `today=` explicitly to test year-boundary behaviour. **NEVER cache `date.today()` at module load time.**

### `compute_targets(profile) -> None`

Mutates `profile.target_*` in place. Algorithm:

1. `age = compute_age(profile.date_of_birth)`
2. `bmr_base = 10 * float(weight_kg) + 6.25 * float(height_cm) - 5 * age`
3. Sex offset:
   - `male` → `bmr = bmr_base + 5`
   - `female` → `bmr = bmr_base - 161`
   - `other` / `prefer_not_to_say` → `bmr = bmr_base - 78`  *(average of +5 and −161)*
4. `tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]`
5. `delta = GOAL_CALORIE_DELTA[goal]`
6. `target_calories = max(1200, round(tdee + delta))`
7. `split = MACRO_SPLITS[goal]`
8. `target_protein_g = round(target_calories * split[0] / 4, 1)`
9. `target_carbs_g = round(target_calories * split[1] / 4, 1)`
10. `target_fat_g = round(target_calories * split[2] / 9, 1)`
11. `fiber_rate = FIBER_TARGET_PER_1000_KCAL.get(goal, FIBER_TARGET_PER_1000_KCAL["default"])`
12. `target_fiber_g = round(target_calories / 1000 * fiber_rate, 1)`

---

## Models and fields

### `DietaryProfile`

Inherits `TimestampedModel` first per §7 MRO rule. `related_name="profile"` on `user` activates `UserSerializer.get_has_profile()`.

**`date_of_birth` is stored as `DateField`. `age` is NEVER stored.** The serializer exposes `age` as a `SerializerMethodField` calling `compute_age(profile.date_of_birth)`. `compute_targets` also calls `compute_age` internally rather than reading any stored value.

**`save()` override** calls `compute_targets(self)` — computes target fields in place. Budget derivation happens in the **service** before `save()`, not in `save()` itself. Per CLAUDE.md §7: derived field computation in `save()` is permitted for the `DietaryProfile` model because it has no network calls.

**GIN indexes** on `allergies` and `secondary_cuisine_preferences` — both used by M4 hard filters.

All field choices defined as module-level constants in `models.py` for mypy compliance.

---

## Services — `apps/profiles/services/profiles.py`

### `upsert_profile(user, data: dict) -> DietaryProfile`

1. **Jain rule:** `if data.get("diet_pattern") == "jain": data["no_onion_garlic"] = True`
2. **Dislikes normalisation:** lowercase + strip each item, drop empty strings, deduplicate, enforce max 30
3. **Disclaimer gate:** pop `disclaimer_acknowledged`; if not `True` raise `AppValidationError(VALIDATION_ERROR, "Disclaimer must be acknowledged")`
4. **Budget derivation:** apply derivation rules; raise `AppValidationError` on violations
5. `profile, created = DietaryProfile.objects.get_or_create(user=user)`
6. Assign all fields from `data` to `profile`
7. `profile.full_clean()` ← mandatory per CLAUDE.md §7 — fires all model validators before save
8. `profile.save()` ← triggers `compute_targets`
9. Logging: `INFO profile_created` or `INFO profile_updated` with `{"event": ..., "user_id": user.pk}`; `ERROR profile_validation_failed` with `error_code` on `ValidationError`

### `get_profile(user) -> DietaryProfile`
`DietaryProfile.objects.get(user=user)` — raises `NotFoundError(code=PROFILE_NOT_FOUND)` if absent. Trivial pass-through; no logging per §7.

### `update_profile(user, data: dict) -> DietaryProfile`
`get_profile(user)` → apply same Jain / dislikes / budget / disclaimer normalisation → partial-update only fields present in `data` → `full_clean()` → `save()`

```python
# TODO(M2): invalidate today's MealPlan cache here when M4 is built
```

Log `INFO profile_updated`.

---

## Serializers and views

### `DietaryProfileSerializer`
- All stored model fields present
- `target_*` → `read_only=True` (silently ignored on write — DRF default for read-only)
- `daily_food_budget_inr`, `weekly_food_budget_inr` → `required=False` (budget derivation in service)
- `secondary_cuisine_preferences` → `ListField(child=CharField(max_length=64), required=False, default=list)`
- `allergies`, `dislikes` → `ListField(child=CharField(max_length=64), required=False, default=list)`
- `disclaimer_acknowledged` → `BooleanField(write_only=True)` (not on model; service pops it)
- `age` → `SerializerMethodField` returning `compute_age(obj.date_of_birth)`

### Endpoints

| Endpoint | View | Notes |
|---|---|---|
| `POST /api/v1/profiles/onboarding` | `OnboardingView.post` | upsert; idempotent |
| `GET /api/v1/profiles/me` | `ProfileMeView.get` | 404 `PROFILE_NOT_FOUND` if absent |
| `PATCH /api/v1/profiles/me` | `ProfileMeView.patch` | partial update; recomputes targets |

---

## Files to create / modify

**Create:**
`apps/profiles/__init__.py`, `apps.py`, `models.py`, `admin.py`, `serializers.py`, `views.py`, `urls.py`,
`services/__init__.py`, `services/profiles.py`,
`migrations/0001_initial.py` (generated),
`tests/__init__.py`, `tests/factories.py`, `tests/test_models.py`, `tests/test_services.py`, `tests/test_views.py`

**Modify:**
- `core/utils/nutrition_math.py` — replace stub with full implementation
- `nutriplan/settings/base.py` — add `"django.contrib.postgres"` to `DJANGO_APPS`; add `"apps.profiles"` to `LOCAL_APPS`
- `nutriplan/api_router.py` — add `path("profiles/", include("apps.profiles.urls"))`

---

## Migration

`apps/profiles/migrations/0001_initial.py` (generated by `makemigrations profiles`).
- Creates `profiles_dietaryprofile` table with all fields
- GIN indexes on `allergies` and `secondary_cuisine_preferences`
- FK to `accounts_user.id` (CASCADE)
- `django.contrib.postgres` must be in `INSTALLED_APPS` first or GIN index syntax will fail

---

## Tests to write

### Pure math — no DB (`@pytest.mark.django_db` not needed)

| Test | What it pins |
|---|---|
| `test_bmr_male_known_value` | male 30yo 80kg 180cm → BMR = 1730 |
| `test_bmr_female_known_value` | female 25yo 60kg 165cm → BMR = 1255.25 |
| `test_bmr_other_uses_average` | `other` → same as `bmr_base − 78` |
| `test_bmr_prefer_not_to_say_uses_average` | `prefer_not_to_say` → same formula as `other` |
| `test_tdee_sedentary` | BMR × 1.2 |
| `test_tdee_light` | BMR × 1.375 |
| `test_tdee_moderate` | BMR × 1.55 |
| `test_tdee_very` | BMR × 1.725 |
| `test_tdee_athlete` | BMR × 1.9 |
| `test_target_calories_lose_weight` | −500 delta applied |
| `test_target_calories_maintain` | 0 delta |
| `test_target_calories_gain_muscle` | +300 delta |
| `test_target_calories_gain_weight_healthy` | +500 delta |
| `test_target_calories_eat_healthier` | 0 delta (same kcal as maintain) |
| `test_target_calories_floors_at_1200` | very low TDEE + aggressive deficit → 1200 |
| `test_macro_split_lose_weight` | 35/40/25 split |
| `test_macro_split_eat_healthier` | 25/50/25 split |
| `test_fiber_target_default_14g` | maintain goal → 14g/1000 kcal |
| `test_fiber_target_eat_healthier_uses_18g` | eat_healthier → 18g/1000 kcal |
| `test_age_computed_from_dob_not_stored` | `compute_age` with fixed `today` returns correct int |
| `test_age_year_boundary` | DOB = today − exactly N years → age = N (freezegun) |

### Service tests — DB

| Test | What it pins |
|---|---|
| `test_budget_derivation_daily_from_weekly` | weekly=700 → daily=100 |
| `test_budget_derivation_weekly_from_daily` | daily=100 → weekly=700 |
| `test_budget_rejects_inconsistent_pair` | daily=100, weekly=800 → VALIDATION_ERROR |
| `test_budget_requires_at_least_one_field` | neither provided → VALIDATION_ERROR |
| `test_jain_implies_no_onion_garlic_true` | jain → no_onion_garlic forced True |
| `test_dislikes_lowercases_and_trims` | " Paneer " → ["paneer"] |
| `test_disclaimer_required_to_submit` | missing/false → VALIDATION_ERROR |
| `test_cuisine_preferences_validates_controlled_vocab` | unknown string → VALIDATION_ERROR |
| `test_allergies_controlled_vocab` | unknown string → VALIDATION_ERROR |
| `test_upsert_creates_profile` | creates with correct computed targets |
| `test_upsert_is_idempotent` | two identical calls → same profile, count=1 |
| `test_upsert_recomputes_on_update` | change weight → targets change |
| `test_get_profile_raises_not_found` | no profile → NotFoundError |

### View / endpoint tests — DB

| Test | What it pins |
|---|---|
| `test_onboarding_endpoint_is_idempotent` | POST twice → 200 both; 1 row in DB |
| `test_onboarding_recomputes_targets_on_update` | POST with new weight → targets updated |
| `test_get_profile_includes_computed_fields` | `target_calories` non-null in response |
| `test_patch_recomputes_when_weight_changes` | PATCH weight → new targets |
| `test_patch_recomputes_when_activity_changes` | PATCH activity_level → new targets |
| `test_patch_recomputes_when_goal_changes` | PATCH goal → new targets and macro split |
| `test_patch_recomputes_when_dob_changes_year_boundary` | PATCH DOB → different age → new targets |
| `test_other_sex_uses_averaged_bmr_formula` | POST sex=other → targets match averaged formula |
| `test_has_profile_true_after_onboarding` | GET /auth/me after onboarding → `has_profile: true` |
| `test_get_me_404_when_no_profile` | authenticated, no profile → 404 PROFILE_NOT_FOUND |
| `test_onboarding_endpoint_rejects_age_below_13` | DOB = today − 12 years → 400 VALIDATION_ERROR |
| `test_onboarding_endpoint_rejects_height_out_of_range` | height_cm=400 → 400 |
| `test_onboarding_endpoint_rejects_weight_out_of_range` | weight_kg=1 → 400 |
| `test_onboarding_endpoint_rejects_invalid_activity_level` | activity_level="superfast" → 400 |

**Total: 21 math tests + 13 service tests + 14 view tests = 48 tests.** All 26 originally listed plus full activity/goal coverage, endpoint-level validation tests, and year-boundary age tests.

---

## Explicitly NOT in M2

These were discussed and formally deferred to v2:

| Item | Reason |
|---|---|
| Medical conditions (diabetes, PCOS, thyroid, BP, kidney) | Requires clinical validation; v2 with RD review |
| Target weight / weight-loss-rate input | Engine computes calorie delta; user-specified rate is unreliable |
| Body composition (body fat %, muscle mass) | Most users don't know; high error in estimation formulas |
| Meal-timing preferences (intermittent fasting, time-restricted eating) | v2 |
| Photo/face scan biometric estimation | v2 |

---

## Follow-up for M4 (document now, implement later)

### `eat_healthier` goal — M4 engine scoring boost (Q2 follow-up)
The elevated fiber target (18g/1000 kcal) is decorative in M2 — it's set on the profile but no recipe-selection logic uses it. In M4, add:

```
+15 score boost for recipes where (cached_nutrition.fiber_g / cached_nutrition.calories * 1000) ≥ 4g/100kcal
Applied only when profile.goal == "eat_healthier"
```

Without this, the elevated target is a display value only, not a planning signal.

### `cooking_frequency` — M4 engine scoring logic (Q4 decision)

**Decided:** score penalty/boost in M4 engine from existing recipe metadata, NOT a `batch_cookable` field on Recipe.

| `cooking_frequency` value | M4 scoring rule |
|---|---|
| `daily` | +15 score for recipes with `prep_time_min ≤ 15` |
| `weekends_only` | +15 score for recipes with `cook_time_min ≥ 30 AND servings ≥ 4` |
| `rarely` | +20 score for same batch-friendly criteria (`cook_time_min ≥ 30 AND servings ≥ 4`) |

**For "rarely" cooks — detection of "keeps well":** At M4 planning time, this should be approximated from `recipe.meal_type` and `instructions` content. Proposed heuristic: recipes with `meal_type=lunch OR dinner` AND `servings ≥ 4` are considered batch-friendly. A more robust v2 signal would be a `keeps_well: bool` field added to Recipe during M3 seed authoring. **Antigravity: flag this decision during M4 planning — if the heuristic is insufficient, add `keeps_well` to the Recipe model in M3 before seeding.**

---

## Acceptance criteria mapping

| Spec criterion | Test(s) |
|---|---|
| POST onboarding upserts, returns profile with computed targets | `test_upsert_creates_profile`, `test_get_profile_includes_computed_fields` |
| Onboarding idempotent | `test_onboarding_endpoint_is_idempotent`, `test_upsert_is_idempotent` |
| GET /profiles/me → profile or 404 PROFILE_NOT_FOUND | `test_get_profile_includes_computed_fields`, `test_get_me_404_when_no_profile` |
| PATCH recomputes targets | `test_patch_recomputes_when_*` (4 tests) |
| BMR male/female known values | `test_bmr_male_known_value`, `test_bmr_female_known_value` |
| TDEE multipliers correct | `test_tdee_*` (5 tests) |
| Calorie floor 1200 | `test_target_calories_floors_at_1200` |
| All 5 goal targets correct | `test_target_calories_*` (5 tests) |
| Budget derivation and consistency | `test_budget_*` (4 tests) |
| Jain auto-sets no_onion_garlic | `test_jain_implies_no_onion_garlic_true` |
| `has_profile=true` after onboarding | `test_has_profile_true_after_onboarding` |
| Disclaimer required | `test_disclaimer_required_to_submit` |
| Endpoint-level validation (ADD 1) | `test_onboarding_endpoint_rejects_*` (4 tests) |
| Elevated fiber for eat_healthier | `test_fiber_target_eat_healthier_uses_18g` |

---

## Build order (for Claude Code)

1. Add `"django.contrib.postgres"` to `DJANGO_APPS` in `settings/base.py`
2. `apps/profiles/` scaffold — `__init__.py`, `apps.py`, `admin.py`; add `"apps.profiles"` to `LOCAL_APPS`
3. `apps/profiles/models.py` — all field definitions and constants; `save()` override
4. `python manage.py makemigrations profiles` — review GIN index in generated output; check in
5. `core/utils/nutrition_math.py` — full implementation: constants, `compute_age`, `compute_targets`
6. `apps/profiles/services/profiles.py` — `upsert_profile`, `get_profile`, `update_profile`
7. `apps/profiles/serializers.py` — all fields, `disclaimer_acknowledged` write-only, `age` method field
8. `apps/profiles/views.py` — `OnboardingView`, `ProfileMeView`
9. `apps/profiles/urls.py` + wire into `api_router.py`
10. `apps/profiles/tests/factories.py`
11. `apps/profiles/tests/test_models.py`
12. `apps/profiles/tests/test_services.py` — math tests first (no DB), then service tests
13. `apps/profiles/tests/test_views.py`
14. `make test` — verify ≥80% coverage on `apps/profiles/services/`
15. `make lint` — ruff + black --check + mypy apps/ core/
16. Context update: `docs/PROGRESS.md`, CLAUDE.md §3, `docs/RUNBOOK.md`, §13 if new conventions
