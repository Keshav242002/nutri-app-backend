# NutriPlan Backend — Progress Log

Append one entry per completed module. Newest at the top.

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
