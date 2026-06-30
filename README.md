# Ahara — Backend

> **Production-grade, Indian-first personalized nutrition API built with Django 5, Firebase Auth, Google Gemini, and Celery.**

Ahara is the REST API powering a Flutter mobile app that generates personalized weekly meal plans, tracks daily nutrition, runs an AI nutrition chatbot, and sends push notifications — tuned for the Indian diet and market.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Feature Set](#2-feature-set)
3. [Technology Stack](#3-technology-stack)
4. [System Architecture](#4-system-architecture)
5. [Project Layout](#5-project-layout)
6. [Domain Model](#6-domain-model)
7. [API Surface](#7-api-surface)
8. [Meal Planning Engine](#8-meal-planning-engine)
9. [AI Integration](#9-ai-integration)
10. [Authentication & Security](#10-authentication--security)
11. [Async Task System](#11-async-task-system)
12. [Coding Principles & Practices](#12-coding-principles--practices)
13. [Error Handling](#13-error-handling)
14. [Testing](#14-testing)
15. [Deployment](#15-deployment)
16. [Local Development Setup](#16-local-development-setup)
17. [Configuration Reference](#17-configuration-reference)
18. [Engineering Decisions Log](#18-engineering-decisions-log)

---

## 1. Project Overview

Ahara solves a non-trivial personalization problem: given biometrics, dietary restrictions, cuisine preferences, cooking constraints, and a weekly food budget in INR — generate a nutritionally complete, variety-rich, culturally appropriate meal plan and keep it live as the user logs meals.

**This repository is the Django REST backend only.** The Flutter client lives in a [separate repository](https://github.com/Keshav242002/nutri-app-flutter).

Key qualities:
- Firebase ID token authentication on every endpoint
- Canonical JSON response envelope on every success and error
- 536 automated tests at 95% aggregate coverage
- Full OpenAPI 3.0 schema (zero `drf-spectacular` warnings)
- Structured JSON logging in production
- Deployed on GCP via Docker Compose + Caddy

---

## 2. Feature Set

| Module | What it does |
|---|---|
| **Accounts** | Firebase-backed User model; token verification; auto-registration on first request |
| **Profiles** | 6-step onboarding; biometrics → macro targets (Mifflin-St Jeor BMR + TDEE); budget in INR |
| **Recipes** | 211 seeded Indian recipes; IFCT 2017 nutrition data with USDA fallback; household-unit display (katori, roti, tbsp) |
| **Meal Plans** | Scoring engine; cuisine + macro + variety + budget signals; per-slot regeneration; auto grocery lists |
| **Tracker** | Daily meal log with five statuses; fractional servings; real-time daily & weekly nutrition summaries |
| **Celery Tasks** | Nightly plan generation at user's local 4 AM; daily nutrition recompute; streak checks; notification pruning |
| **AI Chat** | Gemini-powered chatbot; tracker-aware system prompt; SSE streaming; USDA ingredient lookups cached in Redis |
| **Notifications** | FCM push + in-app feed; idempotent dispatch; streak milestones; 30-day auto-prune |
| **Hardening** | Rate limiting; Sentry; `@audit_log` decorator; full OpenAPI schema; Docker + Caddy production stack |

---

## 3. Technology Stack

### Core
| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Framework | Django | 5.1.15 |
| API layer | Django REST Framework | 3.17.1 |
| Database | PostgreSQL | 16 |
| Cache / broker | Redis | 7 |
| Task queue | Celery + django-celery-beat | 5.6.3 |
| ASGI server | Uvicorn | 0.48.0 |
| WSGI server | Gunicorn | (prod) |

### External Services
| Service | Purpose |
|---|---|
| Firebase Auth | Identity provider — ID tokens issued on the client, verified server-side |
| Firebase Cloud Messaging | Push notifications to Android / iOS |
| Google Gemini | AI chatbot (via `google-genai` SDK + `GEMINI_API_KEY`) |
| USDA FoodData Central | Ingredient nutritional data (fallback to IFCT 2017) |
| Sentry | Error + performance monitoring in production (active when `SENTRY_DSN` is set) |

### Key Libraries
| Library | Purpose |
|---|---|
| `firebase-admin` 7.4.0 | Token verification + FCM |
| `google-genai` 1.20.0 | Gemini native SDK |
| `openai` 1.82.0 | OpenRouter / OpenAI-compatible SDK (optional fallback providers) |
| `httpx` 0.28.1 | Async HTTP client for USDA calls |
| `drf-spectacular` 0.29.0 | OpenAPI 3.0 schema — every view is decorated with `@extend_schema`; `core/schema.py` customises the envelope response shape |
| `django-ratelimit` 4.1.0 | View-level rate limiting |
| `python-json-logger` 2.0.7 | Structured JSON logs in production |
| `psycopg` 3.3.4 | PostgreSQL driver (psycopg3) |

### Dev Toolchain
| Tool | Purpose |
|---|---|
| `pytest` + `factory-boy` | Test runner + model factories |
| `black` + `ruff` | Formatter + linter |
| `mypy --strict` | Static type checking |
| `django-stubs` + `djangorestframework-stubs` | Type stubs for Django/DRF |
| `freezegun` | Time-travel in date-sensitive tests |
| `uv` | Fast Python package manager |

---

## 4. System Architecture

```
Flutter App (Firebase SDK)
    |
    | HTTPS — Authorization: Bearer <firebase-id-token>
    v
Caddy (reverse proxy + automatic TLS)
    |
    v
Django + DRF  (Gunicorn / Uvicorn)
  +-- accounts    (Firebase auth, User model)
  +-- profiles    (BMR/TDEE, macro targets)
  +-- recipes     (IFCT/USDA nutrition, 211 recipes)
  +-- mealplans   (scoring engine, grocery lists)
  +-- tracker     (MealLog, DailyNutritionSummary)
  +-- chat        (Gemini, SSE streaming)
  +-- notifications (FCM + in-app feed)
  +-- core/       (exceptions, audit, pagination)
    |
  +--+--+
  |     |
  v     v
PostgreSQL 16    Redis 7
                   |
                   v
             Celery Worker + Beat
             (nightly plans, FCM push, streaks)
```

### Request Flow — `GET /api/v1/mealplans/today/`

```
1. FirebaseAuthentication  — verify token, upsert user
2. TodayMealPlanView.get() — resolve user-local date (IANA timezone)
3. get_or_generate_plan()  — get_or_create MealPlan row
4. engine.select_recipe()  — filter (SQL) + score (Python) x 3 slots
5. MealPlanDayDetailSerializer + success_response()
```

---

## 5. Project Layout

```
ahara-backend/
+-- manage.py
+-- pyproject.toml        # black + ruff + mypy + pytest config
+-- Makefile              # developer shortcuts
+-- Dockerfile
+-- docker-compose.yml    # postgres + redis + web + worker + beat + caddy
+-- Caddyfile
+-- POSTMAN_COLLECTION.json
+-- .env.example
+-- requirements/
|   +-- base.txt          # exact-pinned production deps
|   +-- dev.txt           # + test/lint tools
|   +-- prod.txt          # + gunicorn + sentry-sdk
+-- nutriplan/            # Django project package
|   +-- settings/
|   |   +-- base.py
|   |   +-- development.py
|   |   +-- production.py
|   +-- api_router.py     # all /api/v1/* includes in one place
|   +-- celery.py
+-- core/                 # shared utilities — NO models
|   +-- exceptions.py     # AppException hierarchy + custom DRF handler
|   +-- error_codes.py    # all error code constants
|   +-- mixins.py         # TimestampedModel
|   +-- pagination.py     # StandardCursorPagination
|   +-- responses.py      # success_response()
|   +-- audit.py          # @audit_log decorator
|   +-- utils/nutrition_math.py
+-- apps/                 # all domain apps
|   +-- accounts/
|   +-- profiles/
|   +-- recipes/
|   +-- mealplans/
|   +-- tracker/
|   +-- chat/
|   +-- notifications/
+-- tests/                # cross-app integration tests
+-- scripts/              # one-off data scripts (not served)
```

### Per-App Convention (enforced)

```
apps/<name>/
+-- models.py       # schema + simple invariants only
+-- serializers.py  # (de)serialization only
+-- views.py        # thin: input -> service -> serialize
+-- services/       # ALL business logic lives here
+-- tasks.py        # thin Celery wrappers
+-- tests/
+-- migrations/
```

---

## 6. Domain Model

```
User (AbstractBaseUser)
  -- firebase_uid (unique, indexed)
  -- email, display_name
  -- created_at, updated_at (TimestampedModel)

DietaryProfile (1:1 -> User)
  -- biometrics: date_of_birth, sex, height_cm, weight_kg
  -- goal (5 types), activity_level
  -- diet_pattern (vegetarian / vegan / eggetarian / jain / non_veg / anything)
  -- allergies, dislikes, no_onion_garlic (ArrayField + GIN index)
  -- cuisine prefs: primary_cuisine_region + secondary_cuisine_preferences
  -- daily_food_budget_inr, max_prep_time_min, timezone (IANA)
  -- target_calories / target_protein_g / target_carbs_g / target_fat_g
     (auto-recomputed on every save via Mifflin-St Jeor + TDEE)

Ingredient
  -- per_100g_nutrition (JSONField — raw-weight, IFCT 2017 primary)
  -- allergen_tags (ArrayField + GIN), cooked_yield_ratio
  -- source: ifct / usda / manual | ifct_code, usda_fdc_id (provenance)

HouseholdUnit  -- name + grams (katori=150g, roti=60g, tbsp=15g ...)

Recipe
  -- meal_type (breakfast / lunch / dinner)
  -- cuisine (17 types), diet_tags, allergen_tags (ArrayField + GIN)
  -- cached_nutrition (JSONField, per serving), cached_calories_per_serving (indexed)
  -- cached_cost_inr, cost_known

RecipeIngredient  -- quantity_grams (canonical), display_quantity + display_unit

MealPlan  (user x date -> breakfast_id, lunch_id, dinner_id)
  -- regeneration_count (JSONField per-slot), full_plan_regenerations

GroceryList  (user x ISO week) -- items JSONField, estimated_cost_inr

MealLog  (user x date x slot)
  -- status: planned / ate_planned / ate_substituted / ate_custom / skipped
  -- servings_eaten (Decimal, 0.25 increments)

DailyNutritionSummary  (user x date)
  -- calories, protein_g, carbs_g, fat_g, fiber_g, micronutrients (JSONField)

ChatSession + ChatMessage  (role: user / assistant / system)

Notification  -- dedup_key (UniqueConstraint with user for idempotency)
DeviceToken   -- fcm_token, platform (ios / android / web)
```

---

## 7. API Surface

All endpoints live under `/api/v1/`. Every response uses the canonical envelope:

```json
// Success
{ "status": "success", "message": "...", "data": { } }

// Error
{ "status": "error", "message": "...", "error": { "code": "ERROR_CODE", "details": {} } }
```

| Group | Method | Path | Description |
|---|---|---|---|
| **Auth** | POST | `/auth/register/` | Firebase token → upsert user |
| | GET/PATCH | `/auth/me/` | Current user |
| **Profiles** | POST | `/profiles/` | Create / upsert dietary profile |
| | GET/PATCH | `/profiles/me/` | Get or update profile |
| | GET | `/profiles/questionnaire/` | Questionnaire schema for the Flutter onboarding UI |
| **Recipes** | GET | `/recipes/` | Paginated list (filters: meal_type, cuisine, diet_tags, allergens) |
| | GET | `/recipes/<id>/` | Detail with ingredients + nutrition |
| **Meal Plans** | GET | `/mealplans/today/` | Today's plan (lazily generated) |
| | GET | `/mealplans/day/<YYYY-MM-DD>/` | Specific date plan |
| | POST | `/mealplans/regenerate/` | Full-day regeneration (3/week limit) |
| | POST | `/mealplans/regenerate-slot/` | Single slot (3/slot/week limit) |
| | GET | `/mealplans/week/<YYYY-MM-DD>/` | ISO week of plans |
| | GET | `/mealplans/week/<YYYY-MM-DD>/grocery/` | Aggregated grocery list |
| **Tracker** | GET/POST | `/tracker/today/` | Today's logs |
| | GET/POST/PATCH | `/tracker/date/<YYYY-MM-DD>/<slot>/` | Specific slot log |
| | GET | `/nutrition/daily/<YYYY-MM-DD>/` | Daily nutrition summary |
| | GET | `/nutrition/weekly/<YYYY-MM-DD>/` | 7-day summary with targets |
| **Chat** | GET/POST | `/chat/sessions/` | List or create sessions |
| | GET/DELETE | `/chat/sessions/<id>/` | Session detail |
| | GET/POST | `/chat/sessions/<id>/messages/` | History or send (SSE streaming supported) |
| **Notifications** | GET | `/notifications/` | In-app feed |
| | POST | `/notifications/read/` | Mark read |
| | POST/DELETE | `/notifications/device-tokens/` | Register / remove FCM token |

---

## 8. Meal Planning Engine

The engine (`apps/mealplans/services/engine.py`) selects one recipe per slot (breakfast / lunch / dinner) using a two-step approach.

### Step 1 — Hard Filters (SQL)

A single ORM query filters by: active status, meal type, diet tags, allergen exclusions, calorie window, and budget (1.15× grace). If budget filtering leaves zero candidates, the engine retries at 1.40× grace.

Calorie windows (as % of slot target):
- Breakfast: 50–150% (wider, Indian breakfasts are lighter)
- Lunch / Dinner: 75–125%

### Step 2 — Soft Scoring (Python)

| Signal | Weight |
|---|---|
| Cuisine match (primary or secondary) | +30 |
| Macro proximity (protein, carbs, fat) | ×20 |
| Variety penalty (used in past 7 days) | −50 |
| Budget fit | +25 |
| Fiber boost (eat_healthier goal) | +15 |
| Quick recipe (within max_prep_time_min) | +15 |
| Protein rotation penalty (same source as yesterday) | −25 |
| Random tiebreaker | 0–5 |

If no candidate survives the hard filter even at relaxed budget, `NoSuitableRecipeError` is raised → HTTP 422.

---

## 9. AI Integration

### Provider

The app uses **Google Gemini** (`AI_PROVIDER=gemini_native`, `GEMINI_API_KEY=...`). The code supports switching to OpenRouter or OpenAI via the `AI_PROVIDER` env var with zero code changes — useful for cost or availability fallback.

### Tracker-Aware System Prompt

Every chat request builds a real-time context block:

```
Today's intake:
  Calories: 850 / 1,800 kcal (47%)
  Remaining: Protein 45g | Carbs 120g | Fat 22g
  Logged: breakfast (ate_planned) | lunch (skipped)
```

This lets Gemini give advice grounded in the user's actual day, not generic responses.

### USDA Ingredient Lookup

When users ask about specific foods, the chat service fetches USDA FoodData Central and caches results in Redis for 30 days. Gemini-returned macro values are **never stored** — only IFCT/USDA data is persisted.

### SSE Streaming

```
POST /api/v1/chat/sessions/<id>/messages/
Accept: text/event-stream
→ data: {"chunk": "Based on your remaining macros..."}
→ data: [DONE]
```

---

## 10. Authentication & Security

### Firebase Token Flow

1. Extract `Authorization: Bearer <token>`
2. `firebase_auth.verify_id_token(token)` — validates signature, expiry, revocation
3. Upsert user in Postgres using `firebase_uid` as the stable key

Each Firebase error type (`ExpiredIdTokenError`, `RevokedIdTokenError`, `InvalidIdTokenError`) maps to a distinct error code. Unexpected exceptions propagate as HTTP 500.

### Dev Auth Bypass

Three conditions must all be true: `DEBUG=True`, `DEV_AUTH_BYPASS_ENABLED=True`, and the request uses the exact `DEV_AUTH_BYPASS_TOKEN`. `production.py` hard-codes `DEV_AUTH_BYPASS_ENABLED=False` unconditionally.

### Rate Limiting

`django-ratelimit` applied to:
- Plan regeneration: 3/day per user (configurable via `REGENERATE_RATE_LIMIT`)
- Chat: 30/hour per user (configurable via `CHAT_RATE_LIMIT`)

---

## 11. Async Task System

All tasks are thin wrappers in `apps/<name>/tasks.py`:

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def my_task(self: Task, user_id: int) -> None:
    user = User.objects.get(pk=user_id)  # IDs only — never model instances
    some_service.do_work(user)
```

### Scheduled Tasks (stored in DB, updatable without redeploy)

| Task | Schedule |
|---|---|
| `generate_plans_for_all_users` | Daily 04:00 user's local time |
| `nightly_recompute_all_summaries` | Daily 03:00 UTC |
| `check_and_dispatch_streaks` | Daily 20:00 UTC |
| `prune_old_notifications` | Daily 02:00 UTC |

### Notification Dispatch

```
dispatch(user, category, title, body, dedup_key)
  -> Notification.objects.get_or_create(user, dedup_key)  [idempotent]
  -> send_push.delay(notification_id)                     [fire-and-forget]
     -> firebase_messaging.send()  [soft-fail: logs error, never raises]
```

---

## 12. Coding Principles & Practices

### Three-Tier Separation

| Layer | Does | Must NOT |
|---|---|---|
| **Views** | Parse input → call service → serialize | Business logic, DB queries |
| **Services** | All logic; typed exceptions | Know about `request`, HTTP codes |
| **Models** | Schema + `clean()` + `save()` hooks | External API calls, workflows |

Every service function is unit-testable without the HTTP stack.

### Type Safety

All `apps/` and `core/` code passes `mypy --strict` with `django-stubs` and `djangorestframework-stubs`.

### Model Validation

Every service-layer write calls `model.full_clean()` before `model.save()` to enforce validators, choices, and custom `clean()` methods Django's ORM would otherwise skip.

### Conventions

- Exact version pins in `requirements/base.txt`
- `TimestampedModel` as first MRO entry on every model
- Migrations committed in the same PR as the model change
- PostgreSQL only — no SQLite, including in tests
- No PII in logs (no email, token, or name in log lines)

---

## 13. Error Handling

### Exception Hierarchy

```
AppException
+-- AppValidationError   -> 400
+-- NotFoundError        -> 404
+-- ConflictError        -> 409
+-- RateLimitError       -> 429
+-- ExternalServiceError -> 502
```

### Custom DRF Handler

`app_exception_handler` in `core/exceptions.py` maps every exception type to the canonical JSON envelope — including unexpected 500s. The Flutter client **never receives an HTML error page**.

---

## 14. Testing

- **536 tests, 95% aggregate coverage**
- Per-module service coverage gate: ≥ 80%
- All external services (Firebase, Gemini, USDA, FCM) are always mocked

```python
# Firebase bypassed via DRF force_authenticate
@pytest.fixture
def api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client

# Deterministic engine tests via random.seed(0)
def test_engine_selects_cuisine_match():
    random.seed(0)
    plan = generate_plan_for_user(user, today)
    assert plan.breakfast is not None
```

---

## 15. Deployment

### Infrastructure Overview

```
GCP Compute Engine e2-micro (Always-Free tier)
    |
    | SSH / secrets via GCP Secret Manager
    |
Docker Compose on the VM
  +-- caddy    (automatic HTTPS, reverse proxy)
  +-- web      (Gunicorn, 2 workers)
  +-- worker   (Celery worker)
  +-- beat     (Celery beat — ONLY 1 instance, never scale)
  +-- postgres (volume-backed)
  +-- redis    (volume-backed)
```

### GCP VM Setup (one-time)

```bash
# 1. Create VM
gcloud compute instances create ahara-backend \
  --machine-type=e2-micro \
  --zone=asia-south1-a \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB

# 2. SSH in and install Docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER && newgrp docker

# 3. Open firewall ports
gcloud compute firewall-rules create allow-http-https \
  --allow tcp:80,tcp:443 \
  --target-tags=http-server,https-server
```

### Deploying the App

```bash
# On the VM — first time
git clone <repo-url> ahara-backend
cd ahara-backend
cp .env.example .env
# Fill in .env with production values (SECRET_KEY, DB, Firebase, Gemini, etc.)
# Put firebase-admin.json in secrets/

# Start all services
docker compose up -d

# Run migrations and seed
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_recipes

# Subsequent deploys
git pull
docker compose build web worker beat
docker compose up -d --no-deps web worker beat
docker compose exec web python manage.py migrate
```

### Caddyfile (automatic HTTPS)

```
yourdomain.com {
    reverse_proxy web:8000
}
```

Caddy auto-provisions a Let's Encrypt certificate — no manual SSL configuration needed.

### Environment — Production vs Development

| Setting | Development | Production |
|---|---|---|
| `DEBUG` | True | False |
| Logging | Console, human-readable | JSON (python-json-logger) |
| CORS | Relaxed | Locked to `CORS_ALLOWED_ORIGINS` |
| `DEV_AUTH_BYPASS_ENABLED` | Configurable | Hard-coded `False` |
| HSTS / Secure cookies | Off | On |

### What Gets Pushed to GitHub

The `.gitignore` already excludes everything sensitive. Files **tracked** in the repo:

| Tracked | Excluded |
|---|---|
| All `apps/`, `core/`, `nutriplan/` source | `.env` and any `.env.*` (except `.env.example`) |
| `requirements/*.txt`, `pyproject.toml` | `secrets/` directory (firebase JSON) |
| `Makefile`, `Dockerfile`, `docker-compose.yml`, `Caddyfile` | `__pycache__/`, `.venv/`, `.mypy_cache/` |
| `POSTMAN_COLLECTION.json` | `.coverage`, `htmlcov/` |
| `.env.example` | `docs/` (internal docs, gitignored) |
| `README.md`, `migrations/` | `CLAUDE.md` (internal dev notes) |
| `apps/recipes/seed_data/recipes.json` | `apps/recipes/seed_data/images/` (in Firebase Storage) |

---

## 16. Local Development Setup

```bash
# Prerequisites (macOS)
brew install python@3.12 postgresql@16 redis
brew services start postgresql@16 redis

createuser -s ahara && createdb -O ahara ahara
psql -c "ALTER USER ahara WITH PASSWORD 'ahara';"
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup
git clone <repo-url> && cd ahara-backend
make install          # uv pip install -r requirements/dev.txt
cp .env.example .env  # fill in SECRET_KEY + FIREBASE_CREDENTIALS_PATH + GEMINI_API_KEY
make migrate
make seed             # loads 211 recipes with full IFCT/USDA nutrition
```

### Running

```bash
make run          # Django runserver (sync — sufficient for most endpoints)
make run-asgi     # Uvicorn (required for SSE streaming in chat)

make worker       # Terminal 2: Celery worker
make beat         # Terminal 3: Celery beat
```

### Common Commands

```bash
make test         # pytest + coverage (~30s)
make lint         # ruff + black --check + mypy
make format       # ruff --fix + black
make shell        # Django shell
make dbreset      # drop + recreate DB (confirmed)
```

OpenAPI docs: `http://localhost:8000/api/schema/swagger-ui/`

---

## 17. Configuration Reference

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | — | Use `get_random_secret_key()` |
| `DATABASE_URL` | Yes | — | `postgres://user:pass@host:5432/db` |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Cache |
| `CELERY_BROKER_URL` | Yes | `redis://localhost:6379/1` | Broker |
| `CELERY_RESULT_BACKEND` | Yes | `redis://localhost:6379/2` | Results |
| `FIREBASE_CREDENTIALS_PATH` | Local | — | Path to service account JSON |
| `FIREBASE_CREDENTIALS_JSON` | Prod | — | Full JSON as single-line string |
| `AI_PROVIDER` | No | `gemini_native` | `gemini_native`, `gemini_openai`, `openai`, `openrouter` |
| `GEMINI_API_KEY` | Yes | — | From aistudio.google.com |
| `USDA_API_KEY` | Yes | — | Free at fdc.nal.usda.gov |
| `SENTRY_DSN` | No | — | Set in production to enable Sentry error + performance monitoring |
| `REGENERATE_RATE_LIMIT` | No | `3/d` | |
| `CHAT_RATE_LIMIT` | No | `30/h` | |
| `DEV_AUTH_BYPASS_ENABLED` | No | `False` | Never True in production |

---

## 18. Engineering Decisions Log

**Firebase Auth over Django auth** — The Flutter client uses Firebase SDK. Verifying tokens server-side avoids a token-exchange layer; `firebase_uid` is the stable key (stable across email changes).

**IFCT 2017 as primary nutrition source** — USDA FDC lacks data for jowar, bajra, regional dals, Indian ghee variants. IFCT is Indian-first; USDA is the fallback. Both sources carry provenance metadata (`ifct_code`, `usda_fdc_id`, `confidence`).

**Raw-weight canonical storage** — `Ingredient.per_100g_nutrition` stores raw-weight values. `cooked_yield_ratio` converts to cooked weight once, at seed time, cached on `Recipe.cached_nutrition`. Cooking-yield math is never scattered across the codebase.

**Cursor pagination over offset** — Offset pagination breaks when rows are inserted during pagination (e.g., live notification feed). Cursor pagination is stable regardless of concurrent writes.

**JSONField for nutrition** — IFCT defines ~100 nutrients per ingredient; only 5–10 are used by the engine. `JSONField` stores the full dataset; indexed cached columns (`cached_calories_per_serving`, `cached_cost_inr`) are what the engine queries.

**Synchronous nutrition recompute** — `recompute_daily_summary` is called inline at the end of `upsert_meal_log`. The client sees fresh totals immediately. The nightly Celery recompute is a safety net, not the primary mechanism.

**`(user, dedup_key)` for notifications** — Each notification event generates a deterministic key (e.g., `streak_7_2026-06-30`). `UniqueConstraint` makes repeated dispatch calls idempotent without any guard code.

**Three Redis databases** — Separate logical DBs (0=cache, 1=broker, 2=results) means dev `FLUSHDB` only clears one store and each can move to a dedicated instance in production with a single env var change.

---

## Project Stats

| Metric | Value |
|---|---|
| Tests | 536 |
| Coverage | 95% |
| API endpoints | ~30 |
| Seeded recipes | 211 |
| Django apps | 7 |
| Deployed on | GCP Compute Engine e2-micro |

---

## License

Private project — all rights reserved.
