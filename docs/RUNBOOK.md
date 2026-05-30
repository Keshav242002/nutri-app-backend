# NutriPlan Backend — Runbook

Living document. Updated at the end of every module (CLAUDE.md §12.4).

---

## Quick start (after M0)

```bash
# 1. Install deps
make install

# 2. Set up env
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DATABASE_URL, etc.

# 3. Initialize DB (PostgreSQL 16 must be running)
make migrate

# 4. Run dev server
make run
# → http://localhost:8000/healthz
# → http://localhost:8000/api/docs/
# → http://localhost:8000/api/redoc/
```

---

## Postgres setup (one-time, macOS)

```bash
brew install postgresql@16
brew services start postgresql@16

# Verify
pg_isready -h localhost    # → localhost:5432 - accepting connections

# Create user and DB
createuser -s nutriplan
createdb -O nutriplan nutriplan
psql -c "ALTER USER nutriplan WITH PASSWORD 'nutriplan';"

# Smoke test
psql -U nutriplan -d nutriplan -h localhost -c "SELECT 1;"
```

`DATABASE_URL=postgres://nutriplan:nutriplan@localhost:5432/nutriplan`

---

## Standard commands (all via Makefile)

| Command | What it does |
|---------|-------------|
| `make install` | Install dev deps via `uv pip install -r requirements/dev.txt` |
| `make migrate` | Run `python manage.py migrate` |
| `make run` | Start Django dev server on :8000 |
| `make run-asgi` | Start uvicorn ASGI server (required from M7 for streaming) |
| `make test` | Run pytest with coverage |
| `make lint` | Run ruff + black --check + mypy |
| `make format` | Auto-fix with ruff --fix + black |
| `make superuser` | Create Django superuser |
| `make shell` | Open Django shell |
| `make dbreset` | Drop + recreate DB (dev only, asks for confirmation) |
| `make seed` | Seed all recipe data (ingredients → units → recipes) via `seed_recipes` management command |
| `make recompute-nutrition` | Recompute cached nutrition on all active recipes (use after bulk ingredient price updates) |
| `make worker` | Start Celery worker (available after M6) |
| `make beat` | Start Celery beat scheduler (available after M6) |

---

## Environment variables

See `.env.example` for the full annotated list. Required vars by module:

| Module | New vars introduced |
|--------|---------------------|
| M0 | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_SETTINGS_MODULE`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `CORS_ALLOWED_ORIGINS` |
| M1 | `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_JSON` |
| M6 | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| M7 | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS`, `USDA_API_KEY`, `USDA_BASE_URL` |
| M8 | `SENTRY_DSN` (optional), `REGENERATE_RATE_LIMIT`, `CHAT_RATE_LIMIT` |

---

## Common workflows

### Reset local database (dev only)

```bash
make dbreset
# Will prompt for confirmation before dropping the DB
```

### Seed recipe data (after M3)

```bash
make seed
# Runs: python manage.py seed_recipes
# Idempotent — safe to re-run
```

### Run a Celery worker locally (after M6)

```bash
# Terminal 1
make worker

# Terminal 2
make beat
```

### Log a meal and check daily nutrition (after M5)

```bash
# POST a meal log (dev bypass: use dev token or real Firebase token)
curl -s -X POST http://localhost:8000/api/v1/tracker/log/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"log_date": "2026-05-30", "slot": "lunch", "status": "ate_planned", "servings_eaten": "1.00"}'

# Check daily nutrition for a date (requires profile to be set up first)
curl -s "http://localhost:8000/api/v1/nutrition/daily/?date=2026-05-30" \
  -H "Authorization: Bearer <token>"

# List meal logs for a date
curl -s "http://localhost:8000/api/v1/tracker/?date=2026-05-30" \
  -H "Authorization: Bearer <token>"

# List logs over a date range (max 90 days)
curl -s "http://localhost:8000/api/v1/tracker/range/?from=2026-05-26&to=2026-05-30" \
  -H "Authorization: Bearer <token>"

# Weekly nutrition summary
curl -s "http://localhost:8000/api/v1/nutrition/weekly/?from=2026-05-26&to=2026-05-30" \
  -H "Authorization: Bearer <token>"
```

### Trigger a one-off Celery task manually (after M6)

```bash
make shell
# In the shell:
# from apps.mealplans.tasks import generate_plan_for_user
# generate_plan_for_user.delay(user_id=1, plan_date_iso="2026-05-16")
```

---

## Troubleshooting

### "no module named 'psycopg'"

```bash
# Ensure venv is active and deps are installed
make install
# psycopg is psycopg3 (psycopg[binary]==3.3.4), not psycopg2
```

### Postgres connection refused

```bash
brew services start postgresql@16
pg_isready -h localhost
```

### Manual endpoint testing (M2+)

A detailed manual test runbook with curl sequences for every endpoint is at
`docs/MANUAL_TEST_RUNBOOK.md`. It covers the dev bypass flow, real Firebase token flow, DBeaver
SQL queries, and common failure modes.

### Firebase token verification fails locally

Ensure `secrets/firebase-admin.json` exists and `FIREBASE_CREDENTIALS_PATH=./secrets/firebase-admin.json` is set in `.env`. The `secrets/` directory is gitignored.

### DEBUG SQL flooding the console

Set `DJANGO_DEBUG=False` or adjust the `loggers.django` level in development settings. SQL logging is from `django.db.backends` at DEBUG level.

---

## Deployment

> Filled in during M8.

### Railway

TBD — M8

### Render

TBD — M8
