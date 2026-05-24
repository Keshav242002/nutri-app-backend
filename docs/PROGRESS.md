# NutriPlan Backend — Progress Log

Append one entry per completed module. Newest at the top.

---

## M3 — Recipes
- **Completed:** 2026-05-24
- **Commit:** 7803cbc
- **Tests:** 201 passing; `apps/recipes/services/seed.py` 92%, `apps/recipes/services/nutrition.py` 100%
- **Acceptance criteria:** all met
  - `GET /api/v1/recipes/` — cursor-paginated list with 10 filters (meal_type, cuisine, diet_tags, allergen exclusion, difficulty, spice_level, calorie range, cost, search) ✅
  - `GET /api/v1/recipes/<slug>/` — full detail with ingredients and cached nutrition ✅
  - 4 models: Ingredient, HouseholdUnit, Recipe, RecipeIngredient — all indexes, constraints, and choices per spec ✅
  - `seed_ingredients` / `seed_household_units` / `seed_recipes` — idempotent upserts, calorie fallback, allowlist validation ✅
  - `compute_recipe_nutrition` — per-serving sums, cost, cost_known flag ✅
  - `recompute_recipes_using_ingredient` — targeted recompute for admin use ✅
  - `seed_recipes` management command (transaction.atomic) + `recompute_nutrition` command ✅
  - `ruff + black --check + mypy --strict` all pass ✅
- **Deviations from spec:** `DIET_TAG_CHOICES` corrected to canonical vocab (seed data ∪ spec). Removed `fishetarian`, `non_vegetarian`, `diabetic_friendly`, `veg`; added `pescatarian`, `dairy_free`, `nut_free`, `satvik`, `keto`, `mediterranean`.
- **Postfix commit:** Filter validation — all filter fields now reject invalid vocab with 400 `INVALID_FILTER_VALUE` (5 new tests, 201 total)
- **New env vars:** None
- **New external services touched:** None
- **What the next module needs to know:**
  - `Recipe.cached_calories_per_serving` is a denormalized `PositiveIntegerField` with a B-tree index — M4 engine should filter on this column directly for calorie-window queries, not on `cached_nutrition`
  - `Recipe.cost_known` gates strict budget filtering; recipes with `cost_known=False` belong in the fallback pool only
  - `compute_recipe_nutrition()` must be called after any ingredient price update (`recompute_recipes_using_ingredient`)
  - Seed files live at `apps/recipes/seed_data/` — `ingredients.json` (136 entries), `household_units.json`, and the recipe JSON files under `claude_recipes/` and `gemini recipies/`

---

## M4 — MealPlans (BLOCKED)
- **Status:** Blocked on prerequisite
- **Blocker:** Seed expansion to ≥200 recipes covering all profile×goal combinations (diet_type × goal × budget tier). Current seed has 93 recipes, all vegetarian/vegan/eggetarian/pescatarian. Non-veg recipes (chicken, mutton, fish-as-main, egg-as-main) are missing entirely. The M4 recommendation engine requires sufficient recipe coverage across all diet×goal cells to avoid `NO_SUITABLE_RECIPE` failures.
- **Unblock criteria:**
  1. Expand `recipes.json` to ≥200 recipes with coverage across: breakfast/lunch/dinner × vegetarian/eggetarian/pescatarian/non-veg × lose_weight/maintain/gain_muscle/gain_weight_healthy/eat_healthier
  2. Run `make seed` and verify no calorie-range warnings
  3. Verify `?diet_tags=<tag>` returns ≥10 recipes for each common tag

---

## M2 — Profiles
- **Completed:** 2026-05-20
- **Commit:** e193f2f
- **Tests:** 95 tests passing, 90% total coverage; profiles services 100% covered
- **Acceptance criteria:** all met
  - `POST /api/v1/profiles/onboarding` — idempotent create/update, returns computed targets ✅
  - `GET /api/v1/profiles/me` — returns full profile with target macros and `age` ✅
  - `PATCH /api/v1/profiles/me` — partial update, recomputes targets, no disclaimer required ✅
  - `GET /api/v1/profiles/onboarding/questions` — 6-step questionnaire metadata (auth required) ✅
  - Standard response envelope `{status, message, data}` / `{status, message, error}` across all endpoints ✅
  - Budget derivation (daily↔weekly, ±5% consistency), Jain auto-rule, dislike normalisation ✅
  - Disclaimer gate on POST only; PATCH explicitly bypasses it via `ProfileUpdateSerializer` ✅
  - Validators fire via `full_clean()` before every `save()` ✅
  - `ruff + black --check + mypy --strict` all pass ✅
- **Deviations from spec:** None
- **New env vars:** None
- **New external services touched:** None
- **What the next module needs to know:**
  - `DietaryProfile.user` is a `OneToOneField` on `settings.AUTH_USER_MODEL` with `related_name="profile"` — `user.profile` works; `user.has_profile` (via `UserSerializer`) checks for it
  - `core/responses.py::success_response(data, message)` is the only way to build a success response; import it everywhere
  - `core/error_codes.py` must be the import source for error constants in any module loaded during DRF settings init — avoids circular import with `core.exceptions`
  - Budget fields have new DB-level minimums (daily ≥100, weekly ≥700) enforced via migration `0002_budget_minimum_raise`; M3 seed data should respect this

---

### M1 amendment — 2026-05-17
- Fixed `User` to inherit `TimestampedModel` (removed inline `created_at`/`updated_at`); Django detects no schema change — no migration required
- Tightened Firebase exception handling: explicit `ExpiredIdTokenError`, `RevokedIdTokenError`, `InvalidIdTokenError`, `FirebaseError` catches; bare `except Exception` removed; genuine unknowns now propagate
- Added new error codes `TOKEN_REVOKED` and `EXTERNAL_SERVICE_ERROR` to `core/error_codes.py`
- Added structured logging (`event`, `user_id`, `firebase_uid`, `error_code`) to `FirebaseAuthentication` and `register_or_get_user`
- Tightened `has_profile` sentinel from `except Exception` to `except AttributeError`
- Deleted dead `core/authentication.py` (PlaceholderAuthentication — nothing imported it)
- Resolved 4 protocol ambiguities in CLAUDE.md §7 (model inheritance MRO, logging granularity, exception specificity, per-module coverage)
- New migration: none (TimestampedModel move is schema-neutral)
- Tests: 23 passing (+2 new: TOKEN_REVOKED, INVALID_TOKEN explicit paths), 88% on `apps/accounts/services/`

---

## M1 — Accounts
- **Completed:** 2026-05-17
- **Commit:** feat(M1): accounts (see git log for SHA)
- **Tests:** 21 tests passing, 86% coverage on `apps/accounts/services/`
- **Acceptance criteria:** all met
  - `POST /api/v1/auth/register` with valid Bearer token → 200 `{id, firebase_uid, email, display_name, has_profile, created}` ✅
  - `GET /api/v1/auth/me` with valid token → 200 `{id, firebase_uid, email, display_name, has_profile}` ✅
  - Invalid/expired token → 401 with correct error code ✅
  - 21 tests pass (8 new + 13 carried from M0) ✅
  - `ruff + black --check + mypy --strict` all pass ✅
  - `make migrate` runs cleanly on fresh DB ✅
- **Deviations from spec:** None
- **New env vars:** none (FIREBASE_CREDENTIALS_PATH was pre-declared in M0)
- **New external services touched:** Firebase Admin SDK (firebase-admin==7.4.0)
- **What the next module needs to know:**
  - `AUTH_USER_MODEL = "accounts.User"` is now set; all future models must FK to `settings.AUTH_USER_MODEL`, never to `auth.User`
  - `has_profile` in `UserSerializer.get_has_profile` uses `try: obj.profile is not None` — M2 adds the reverse `OneToOneField` named `profile` on User, which makes this return True
  - Error code constants are in `core/error_codes.py` (no DRF imports) — import from there in any module loaded during DRF init
  - DB was reset at M1 start (AUTH_USER_MODEL added after M0); fresh `make migrate` now covers all apps

---

## M0 — Bootstrap
- **Completed:** 2026-05-16
- **Commit:** feat(M0): bootstrap (see git log for SHA)
- **Tests:** 8 tests passing, 66% overall coverage (no services in M0 — ≥80% rule applies from M1)
- **Acceptance criteria:** all met
  - `python manage.py migrate` succeeds against Postgres ✅
  - `runserver` starts ✅
  - `GET /healthz` → `{"status":"ok","db":"ok"}` ✅
  - `GET /api/docs/` renders Swagger ✅
  - `pytest` 8 tests, exit 0 ✅
  - `ruff + black --check + mypy` all pass ✅
- **Deviations from spec:** None
- **New env vars:** DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_SETTINGS_MODULE, DJANGO_ALLOWED_HOSTS, DATABASE_URL, CORS_ALLOWED_ORIGINS, REDIS_URL, CELERY_BROKER_URL, CELERY_RESULT_BACKEND, FIREBASE_CREDENTIALS_PATH, FIREBASE_CREDENTIALS_JSON, OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS, USDA_API_KEY, USDA_BASE_URL, REGENERATE_RATE_LIMIT, CHAT_RATE_LIMIT, SENTRY_DSN (all pre-declared; only M0 vars are required now)
- **New external services touched:** PostgreSQL 16 (via Homebrew)
- **What the next module needs to know:**
  - `core/authentication.py::PlaceholderAuthentication` is the M0 stub — M1 replaces it with `FirebaseAuthentication` and updates `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` in `settings/base.py`
  - `AUTH_USER_MODEL` must be set in `settings/base.py` in M1 (custom User model) before any migrations run
  - `LOCAL_APPS` list in `settings/base.py` is where `apps.accounts` gets added in M1
  - All env vars are pre-declared in `.env.example`; M1 needs `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON` to be filled in
