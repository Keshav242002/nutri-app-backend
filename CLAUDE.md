# NutriPlan Backend — Agent Operating Manual

> **For the agent (Claude Code / Antigravity Agent):** This file is loaded at the start of every session. Read it fully before doing anything. The authoritative project spec lives at `docs/PROJECT_SPEC.json` — that file is the **single source of truth** for *what* to build. This file is the **operating manual** that tells you *how* to work.
>
> **Section 12 (Context update protocol) is mandatory at the end of every module. Skipping it is a protocol violation.**

---

## Table of contents

1. Project at a glance
2. Workflow protocol (the loop you must follow)
3. Current state (kept up to date by you)
4. Prerequisite gates — what must be ready before each module
5. External services playbook — how to obtain & configure each
6. Local environment setup
7. Django architecture & coding standards (enforced)
8. Hard rules (PR-blockers)
9. Code style & tooling
10. Standard commands
11. When you're stuck or unsure
12. **Context update protocol — mandatory after every module**
13. Conventions discovered (you append here as you go)

---

## 1. Project at a glance

**NutriPlan** is a personalized nutrition app: Flutter mobile client + Django REST backend + Firebase Auth + GPT-4o + USDA FoodData Central.

You are working on the **backend only** (`nutriplan-backend/`). Flutter is a separate workstream; do not generate Flutter code unless explicitly asked.

Full agenda, tech stack, system architecture, user journey, sprint plan, and module specs live in `docs/PROJECT_SPEC.json`. Read it. Do not paraphrase from memory.

---

## 2. Workflow protocol

This is the loop. Every module follows it. No exceptions.

```
  ┌─────────────────────────────────────────────────────────┐
  │  STEP 0  Read context                                   │
  │          - CLAUDE.md (this file)                        │
  │          - docs/PROJECT_SPEC.json (current module spec) │
  │          - docs/PROGRESS.md (what's done)               │
  │                                                          │
  │  STEP 1  Prerequisite gate (Section 4)                  │
  │          Check that all external dependencies for this  │
  │          module are ready. If not, STOP and ask user.   │
  │                                                          │
  │  STEP 2  Plan                                           │
  │          Output 5–10 bullets: files, key functions,     │
  │          test list, open questions. WAIT for approval.  │
  │                                                          │
  │  STEP 3  Implement (in order, do not skip)              │
  │          models → migration → services → serializers    │
  │          → views → urls → tests → run → fix → commit    │
  │                                                          │
  │  STEP 4  Verify                                         │
  │          - All tests pass                                │
  │          - Coverage ≥ 80% on services                    │
  │          - ruff, black --check, mypy --strict all pass   │
  │          - Module acceptance criteria from spec all met  │
  │                                                          │
  │  STEP 5  Context update (Section 12) — MANDATORY        │
  │          - Append entry to docs/PROGRESS.md             │
  │          - Update Section 3 of this file                │
  │          - Update Section 13 if new conventions emerged │
  │          - Update docs/RUNBOOK.md with new commands     │
  │          - Update .env.example with new env vars        │
  │                                                          │
  │  STEP 6  Status report                                  │
  │          Summary: what built, test count, coverage,     │
  │          deviations + justification, what's next.       │
  └─────────────────────────────────────────────────────────┘
```

**Do not start the next module until the current one's acceptance criteria pass AND Step 5 is complete.**

---

## 3. Current state

> **Update this section at Step 5 of every module.**

- **Active module:** `M1_accounts`
- **Last completed module:** `M0_bootstrap` (2026-05-16)
- **Build order:** M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8
- **Repo path:** `nutri-app-backend/`
- **Python version:** 3.12.13 (managed by `uv`, venv at `.venv/`)
- **Package manager:** `uv` 0.11.2
- **Django version:** 5.1.15

---

## 4. Prerequisite gates

**Before starting any module, run the gate check for that module.** If anything is missing, STOP and ask the user. Do not silently substitute or stub past what the spec allows.

### M0 — Bootstrap
- [x] Python 3.11+ installed (`python3 --version`) — 3.12.13 via uv
- [x] Package manager available (`uv --version`) — uv 0.11.2
- [x] PostgreSQL 16 running (`pg_isready -h localhost`) — installed via Homebrew
- [x] Postgres user `nutriplan` and database `nutriplan` exist
- [x] `DJANGO_SECRET_KEY` generated and in `.env`
- [x] Git initialized in repo

### M1 — Accounts (Firebase)
- [ ] Firebase project created (see §5.1)
- [ ] Email/password + Google providers enabled in Firebase console
- [ ] Firebase Admin SDK service-account JSON downloaded
- [ ] File placed at `./secrets/firebase-admin.json`
- [ ] `secrets/` added to `.gitignore`
- [ ] `FIREBASE_CREDENTIALS_PATH` set in `.env`

### M2 — Profiles
- [ ] M1 acceptance criteria met
- [ ] No new external dependencies

### M3 — Recipes
- [ ] M2 acceptance criteria met
- [ ] Seed data files exist at `apps/recipes/seed_data/ingredient_nutrition.json` and `recipes.json` — if absent, you must produce them per `M3_recipes.seed_strategy`; ask user before generating large data files

### M4 — MealPlans + engine
- [ ] M3 seed data loaded (`python manage.py seed_recipes` ran successfully, ≥ ~200 recipes in DB)

### M5 — Tracker
- [ ] M4 acceptance criteria met
- [ ] No new external dependencies

### M6 — Celery
- [ ] Redis 7 running locally (`redis-cli ping` → `PONG`)
- [ ] `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` set in `.env`
- [ ] User aware they need to run `make worker` and `make beat` in separate terminals

### M7 — Chat + AI
- [ ] OpenAI API key (see §5.2) — `OPENAI_API_KEY` in `.env`
- [ ] USDA FoodData Central API key (see §5.3) — `USDA_API_KEY` in `.env`
- [ ] User aware of OpenAI costs (give rough estimate before running)

### M8 — Hardening
- [ ] All previous modules acceptance criteria met
- [ ] Sentry DSN optional — if user wants it, see §5.4
- [ ] Deployment target chosen (Railway / Render / Fly.io — see spec)

---

## 5. External services playbook

This is the **how to get it** reference. When the user is unsure, walk them through the relevant subsection step by step. Surface estimated costs and free-tier limits.

### 5.1 Firebase (auth)

**Cost:** Free for typical dev / small prod (Spark plan). Auth is free up to 50k MAU.

**Steps the user must perform (you cannot do these):**
1. Go to https://console.firebase.google.com → "Add project" → name it (e.g., `nutriplan-dev`).
2. Disable Google Analytics for the dev project (faster, fewer prompts).
3. In left sidebar → **Build → Authentication → Get started**.
4. **Sign-in method** tab → enable **Email/Password** and **Google**.
5. Project settings (gear icon) → **Service accounts** → **Generate new private key** → download the JSON file.
6. Save the JSON as `./secrets/firebase-admin.json` in the repo root. **Never commit this file.**

**What you (agent) do:**
- Add `secrets/` to `.gitignore` before anything else.
- In M1, install `firebase-admin` (pin exact version in `requirements/base.txt`).
- Initialize the Admin SDK once at Django startup. Pattern:
  ```python
  # apps/accounts/firebase.py
  import firebase_admin
  from firebase_admin import credentials
  from django.conf import settings

  def init_firebase() -> None:
      if firebase_admin._apps:
          return
      if settings.FIREBASE_CREDENTIALS_JSON:
          cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
      else:
          cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
      firebase_admin.initialize_app(cred)
  ```
- Call `init_firebase()` from `AppConfig.ready()` in `apps/accounts/apps.py`.

**For Flutter side (not your job, but worth noting):** the user must also register Android/iOS apps in the Firebase project and add `google-services.json` / `GoogleService-Info.plist`. Mention this if the user asks about wiring up the client.

### 5.2 OpenAI (GPT-4o)

**Cost:** Pay-as-you-go. GPT-4o is ~$2.50/1M input tokens, ~$10/1M output tokens (verify at https://openai.com/pricing — prices change). A typical chat exchange in this app is ~$0.01–$0.05. **Tell the user this before M7 starts** so they can set a usage cap.

**Steps the user performs:**
1. Go to https://platform.openai.com → sign in.
2. **Billing → Payment methods** → add a card; set a monthly hard limit (recommend $20 for dev).
3. **API keys → Create new secret key** → name it `nutriplan-dev` → copy the `sk-...` value once (you can't view it again).
4. Paste into `.env` as `OPENAI_API_KEY`.

**What you (agent) do in M7:**
- Use `openai` Python SDK v1.x with `OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)`.
- Use structured outputs (JSON schema) per the spec — never free-form parsing.
- Wrap every call in a service function with retry (max 2) and map failures to `ExternalServiceError(code=OPENAI_FAILURE)`.
- **Never** call OpenAI from a view, model, signal, or serializer. Service layer only.
- Log token usage to structured logs for cost tracking.

### 5.3 USDA FoodData Central

**Cost:** Free. Rate limit: 1,000 requests/hour per key. No credit card needed.

**Steps the user performs:**
1. Go to https://fdc.nal.usda.gov/api-key-signup.html
2. Fill the form → API key arrives by email within minutes.
3. Paste into `.env` as `USDA_API_KEY`.

**What you (agent) do in M7:**
- Cache all USDA responses in Redis for 30 days (`SETEX` with 2,592,000s TTL). USDA data is effectively static; do not re-fetch.
- Base URL is `https://api.nal.usda.gov/fdc/v1`.
- Search endpoint: `GET /foods/search?query=...&api_key=...&pageSize=5`.
- Detail endpoint: `GET /food/{fdcId}?api_key=...`.
- Pin one nutrient set — `foundationFoods` first, fall back to `srLegacy`. Document the choice in code.

### 5.4 Sentry (error tracking, optional)

**Cost:** Free tier covers small projects (5k errors/month).

**Steps the user performs (only if they want error tracking):**
1. Go to https://sentry.io → create org → create project → choose **Django**.
2. Copy the DSN.
3. Paste into `.env` as `SENTRY_DSN`.

**What you (agent) do in M8:**
- Install `sentry-sdk[django]` pinned.
- Initialize in `settings/production.py` only, guarded on `SENTRY_DSN`:
  ```python
  if env("SENTRY_DSN", default=""):
      import sentry_sdk
      from sentry_sdk.integrations.django import DjangoIntegration
      sentry_sdk.init(dsn=env("SENTRY_DSN"), integrations=[DjangoIntegration()], traces_sample_rate=0.1, send_default_pii=False)
  ```
- Never initialize Sentry in development settings.

---

## 6. Local environment setup

The user has these installed (verify before M0):

| Tool             | Required by | Install                                                                 |
|------------------|-------------|-------------------------------------------------------------------------|
| Python 3.11+     | M0          | https://www.python.org/downloads/                                       |
| `uv` (preferred) | M0          | `curl -LsSf https://astral.sh/uv/install.sh \| sh`                      |
| PostgreSQL 16    | M0          | macOS: `brew install postgresql@16` / Linux: distro package / Docker    |
| Redis 7          | M6          | macOS: `brew install redis` / Linux: distro package / Docker            |
| Docker (opt.)    | M8          | https://docs.docker.com/get-docker/                                     |

**Postgres setup commands (the user can run these):**
```bash
# macOS Homebrew
brew services start postgresql@16
createuser -s nutriplan
createdb -O nutriplan nutriplan
# Set a password if needed:
psql -c "ALTER USER nutriplan WITH PASSWORD 'nutriplan';"
```

Resulting `DATABASE_URL=postgres://nutriplan:nutriplan@localhost:5432/nutriplan`.

**Redis setup (when M6 starts):**
```bash
brew services start redis
redis-cli ping  # expect PONG
```

---

## 7. Django architecture & coding standards (enforced)

You will follow these. Every module. No drift.

### 7.1 Project layout (locked, from spec)

```
nutriplan-backend/
├── manage.py
├── pyproject.toml
├── .env.example
├── .gitignore
├── requirements/
│   ├── base.txt          # pinned exact versions
│   ├── dev.txt           # -r base.txt + pytest, black, ruff, mypy, factory-boy
│   └── prod.txt          # -r base.txt + gunicorn, sentry-sdk
├── nutriplan/            # project package (NOT an app)
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── api_router.py     # /api/v1/ includes live here
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py
├── core/                 # shared, cross-app, NO models
│   ├── authentication.py # PlaceholderAuthentication (M0) → FirebaseAuthentication (M1)
│   ├── exceptions.py
│   ├── pagination.py
│   ├── permissions.py
│   ├── mixins.py
│   ├── logging.py
│   └── utils/
│       ├── nutrition_math.py
│       └── slugs.py
├── apps/                 # all domain code
│   ├── accounts/
│   ├── profiles/
│   ├── recipes/
│   ├── mealplans/
│   ├── tracker/
│   └── chat/
├── tests/                # cross-app integration tests
├── scripts/              # management-command companions
└── secrets/              # gitignored, local only
```

### 7.2 Per-app layout (locked)

```
apps/<name>/
├── __init__.py
├── apps.py               # AppConfig with name="apps.<name>"
├── admin.py
├── models.py             # ONLY model definitions, NO logic
├── serializers.py        # ONLY (de)serialization, NO logic
├── views.py              # thin: parse → service → serialize
├── urls.py
├── services/             # ALL business logic lives here
│   ├── __init__.py
│   └── <domain>.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_services.py
│   └── test_views.py
└── migrations/
```

### 7.3 Architectural rules

**The service layer is sacred.**
- Views: parse input → call service → serialize output. That's the whole view. No `if`/`else` business logic, no DB queries beyond what serializers do, no external calls.
- Services: take plain Python args (not request objects), return plain Python or model instances, raise typed exceptions from `core/exceptions.py`. **Services know nothing about HTTP.**
- Models: define schema + simple invariants (`clean()`, `save()` for derived fields). **No external API calls. No business workflows.** A model's `save()` may compute derived fields (e.g., `DietaryProfile.save()` recomputes targets via `core.utils.nutrition_math`) but must not hit the network or call signals that do.

**Why this matters:** every service function is unit-testable without spinning up Django's request cycle. Every view is trivially correct because it has no logic to be wrong about.

**Settings split.**
- `settings/base.py` — everything shared, reads from env via `django-environ`.
- `settings/development.py` — `DEBUG=True`, console logging, dev DB defaults.
- `settings/production.py` — `DEBUG=False`, JSON logging, HSTS, secure cookies, Sentry init.

**URLs.**
- All API endpoints under `/api/v1/`. Versioning is non-negotiable.
- `nutriplan/urls.py` includes `nutriplan/api_router.py` at `/api/v1/`.
- Each app's `urls.py` is included from `api_router.py`.
- Each app's `urls.py` uses DRF routers where it makes sense; explicit `path()` otherwise.

**Pagination.**
- One pagination class: `core.pagination.StandardCursorPagination`, `page_size=20`, `ordering='-created_at'`.
- Configurable per-request via `?page_size=` up to a hard ceiling of 100.

**Errors.**
- One exception hierarchy in `core/exceptions.py`: `AppException` → `AppValidationError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `ExternalServiceError`.
- One DRF exception handler that returns the canonical envelope:
  ```json
  {"error": {"code": "...", "message": "...", "details": {}}}
  ```
- All error codes registered in `core/exceptions.py` as constants, listed in the spec's `error_codes_registry`.

**Authentication.**
- M0: `core.authentication.PlaceholderAuthentication` (no-op stub).
- M1+: `apps.accounts.authentication.FirebaseAuthentication`. No alternatives, no fallback.
- `request.user` is the only source of identity. Treat `request.data["user_id"]` as user input that must be rejected if present.

**Logging.**
- `python-json-logger` in production, plain console in development.
- Every service function logs entry/exit at `DEBUG` (no PII), errors at `ERROR` with stacktrace and request ID.
- Structured fields: `event`, `user_id`, `module`, `duration_ms`, `error_code`.

**Database.**
- Postgres only. Use `ArrayField` and `JSONField` where the spec asks (recipes' tags, micronutrients).
- Add GIN indexes on `ArrayField`s used for filtering.
- Every model has `created_at` and `updated_at` via a `TimestampedModel` mixin in `core/mixins.py`.
- Foreign keys use `on_delete` explicitly — pick `CASCADE`, `SET_NULL`, or `PROTECT` deliberately, not by reflex.
- All migrations checked in. Never edit a migration after it's been applied to a shared environment.

**Async tasks (Celery, from M6).**
- Tasks live in `apps/<name>/tasks.py`.
- Tasks are thin wrappers: receive ids (not model instances), call services, log result.
- `bind=True, max_retries=3, default_retry_delay=60` on tasks that hit external services.
- Schedules go in `django-celery-beat` (DB-backed), not hard-coded in `celery.py`.

**Tests.**
- `pytest` + `pytest-django` + `factory-boy`. Never Django's `TestCase` directly.
- One factory per model in `tests/factories.py` (project-level) or `apps/<name>/tests/factories.py` (app-level).
- Mock external services (Firebase, OpenAI, USDA) with `pytest` monkeypatch / fixtures. Never hit real endpoints in tests.
- `random.seed(0)` in any test of the recommendation engine.

---

## 8. Hard rules — PR-blockers

If you would violate any of these, STOP and ask first. These are the most-violated rules from the spec, surfaced here so they're impossible to miss.

- **PostgreSQL only.** No SQLite anywhere, including tests.
- **Custom User model from M1.** Never `django.contrib.auth.User`.
- **Service layer enforced.** Business logic in `apps/<app>/services/`. Not in views, serializers, signals, or `save()`.
- **`request.user` only.** Never trust client-supplied identity.
- **Never trust GPT macros.** Always re-derive from USDA before storing or showing.
- **No external API calls in `save()` or signals.** Always explicit service calls.
- **No new libraries** beyond the spec's `tech_stack` without asking.
- **Every dependency pinned** to exact version in `requirements/base.txt` (e.g., `Django==5.1.15`, not `Django>=5.0`).
- **Secrets via env only** (django-environ). Update `.env.example` whenever a new env var is introduced. Never commit real secrets.
- **Tests not optional.** ≥80% coverage on services. Every endpoint has at least one test.
- **Migrations ship in the same commit as the model change.** No "I'll add the migration later."
- **One module at a time.** Do not start M(n+1) before M(n) acceptance + context update is complete.

Full list: `things_to_explicitly_avoid` in the spec.

---

## 9. Code style & tooling

- **`black`** — line length 100.
- **`ruff`** — rule sets `E, F, I, B, UP, N`.
- **`mypy --strict`** on `apps/` and `core/`. Use explicit types everywhere; no implicit `Any`.
- **Imports:** stdlib → third-party → first-party → local, separated by blank lines. `ruff` enforces this (rule `I`).
- **Naming:** snake_case for modules/functions/variables, PascalCase for classes, UPPER_SNAKE for constants. `ruff` rule `N`.
- **Docstrings:** every service function gets a one-line docstring stating *what* it does, not *how*.
- **Type hints:** every public function. Use `typing` (or 3.10+ `|` syntax — pick one and stay consistent).

Configure all three in `pyproject.toml`. Make `make lint` run all three.

---

## 10. Standard commands

```bash
# Setup
make install          # install deps via uv
make migrate          # apply migrations
make seed             # seed recipe DB (after M3)
make superuser        # createsuperuser

# Dev loop
make run              # runserver (sync) — use M0 onwards
make run-asgi         # uvicorn — required from M7
make test             # pytest with coverage
make lint             # ruff + black --check + mypy
make format           # ruff --fix + black

# Celery (from M6)
make worker
make beat

# DB ops
make dbreset          # drop+recreate (dev only, asks for confirmation)
make shell            # python manage.py shell
```

Document every command and its purpose in `docs/RUNBOOK.md` (created in M0, maintained every module).

---

## 11. When you're stuck or unsure

From the spec's `agent_usage_instructions`:

> "When ambiguous, surface the question — never invent."

Specifically:
- If the spec is silent on something, ask.
- If two parts of the spec conflict, point to both and ask.
- If you think a different approach is better, propose it as a question. Do not unilaterally substitute.
- If a dependency in `tech_stack` seems insufficient, ask before adding another.
- If a prerequisite from Section 4 is missing, STOP and tell the user how to fix it (use Section 5 as the script).

---

## 12. Context update protocol — MANDATORY

**This runs at Step 5 of every module. It is not optional. A module is not "done" until this is complete.**

At the end of every module, you must:

### 12.1 Append to `docs/PROGRESS.md`

Use this exact format, newest at top:

```
## M<n> — <Module Name>
- **Completed:** YYYY-MM-DD
- **Commit:** <short SHA>
- **Tests:** <count> tests passing, <coverage>% coverage on apps/ + core/
- **Acceptance criteria:** all met / partial (with notes)
- **Deviations from spec:** None | <bullet list with justification>
- **New env vars:** <list, or "none">
- **New external services touched:** <list, or "none">
- **What the next module needs to know:** <2-4 bullets max>
```

### 12.2 Update Section 3 of this file

- Move active module to "Last completed."
- Set "Active module" to the next one in the build order.
- Update any version pins (Python, Django, etc.) decided during the module.

### 12.3 Update `.env.example`

If you introduced any new env var, add it with:
- A comment explaining what it is and which module needs it.
- A sensible placeholder value (`OPENAI_API_KEY=sk-replace-me`).
- Never a real secret.

### 12.4 Update `docs/RUNBOOK.md`

If you added new make targets, management commands, or workflows, document them.

### 12.5 Update Section 13 below

If a convention emerged during the module that wasn't already in the spec or in Section 7 — for example, "we decided to use `attrs` for service-layer data classes" — add it as a bullet in Section 13 so future modules follow the same pattern.

### 12.6 Verify

Run, in order:
```bash
make lint
make test
git status              # show what's staged
git diff CLAUDE.md docs/PROGRESS.md .env.example docs/RUNBOOK.md
```

Then commit. Use:
```
feat(M<n>): <module name> — <one-line summary>

- <bullet of major thing done>
- <bullet of major thing done>
- tests: <count> passing, <coverage>% coverage
- closes: M<n> acceptance criteria
```

**If any of 12.1–12.5 are missing when you ask the user to approve the module, that is a protocol violation. Self-correct before asking.**

---

## 13. Conventions discovered

> Append here whenever you make a decision that wasn't already in the spec or Section 7. Future modules read this. Keep it short — one bullet per convention, with date.

- 2026-05-16 — `core/authentication.py::PlaceholderAuthentication` is the M0 stub for `FirebaseAuthentication`. M1 replaces it and updates `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` in `settings/base.py` to point to `apps.accounts.authentication.FirebaseAuthentication`. (M0)
- 2026-05-16 — `nutriplan/api_router.py` is the single file that gathers all `/api/v1/` URL includes. Each new app adds one `include()` line here. `nutriplan/urls.py` does not change after M0. (M0)
- 2026-05-16 — `django-environ` has no `py.typed` marker; it is added to `[[tool.mypy.overrides]] ignore_missing_imports` in `pyproject.toml`. Same pattern applies for any third-party package missing stubs. (M0)
- 2026-05-16 — `mypy` is run as `mypy apps/ core/` (not the whole project). The django-stubs plugin pulls in the settings module automatically via `[tool.django-stubs] django_settings_module`. (M0)
- 2026-05-16 — The spec names the base exception `AppException` which violates ruff rule N818. Suppress with `# noqa: N818` on the class definition — do not rename, the spec is authoritative. (M0)
- 2026-05-16 — The spec's `AppException → ValidationError` hierarchy: our DRF-facing subclass is named `AppValidationError` (not `ValidationError`) to avoid shadowing `rest_framework.exceptions.ValidationError`. (M0)

---

**To start work:** read `docs/PROJECT_SPEC.json` end to end, run the prerequisite gate for the active module (Section 4), propose the plan, and wait for confirmation.
