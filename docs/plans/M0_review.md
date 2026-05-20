# M0 Bootstrap — Retrospective Review

**Date:** 2026-05-17  
**Reviewer:** Antigravity Agent  
**Source:** Code on disk, CLAUDE.md, docs/PROJECT_SPEC.json, docs/PROGRESS.md

---

### Acceptance criteria check

| # | Criterion (from spec) | Status | Justification |
|---|---|---|---|
| 1 | `python manage.py migrate` succeeds against Postgres | PASS | PROGRESS.md confirms ✅; Django + psycopg[binary]==3.3.4 wired to DATABASE_URL |
| 2 | `runserver` starts | PASS | PROGRESS.md confirms ✅; WSGI_APPLICATION and ASGI_APPLICATION both set |
| 3 | `GET /healthz` returns `{"status":"ok","db":"ok"}` | PASS | Endpoint implemented in `nutriplan/urls.py:8-18`; tested in `tests/test_health.py` |
| 4 | `GET /api/docs/` renders Swagger | PASS | drf-spectacular wired at `api/docs/`, `api/redoc/`, `api/schema/` in urls.py |
| 5 | `pytest` runs (0 tests at M0, exit 0) | PASS | PROGRESS.md: 8 tests pass at M0. Spec says "0 tests, exit 0" — 8 tests is better. |
| 6 | `ruff + black --check + mypy` all pass | PASS | PROGRESS.md confirms ✅; pyproject.toml has correct config |

**All 6 acceptance criteria: PASS.**

---

### Architecture compliance (CLAUDE.md §7)

| Item | Status | Evidence |
|---|---|---|
| Service layer separation | PASS | M0 has no domain services (correct — none are scoped to M0). Pattern established by M1. |
| Settings split (base/dev/prod) | PASS | `nutriplan/settings/{base,development,production}.py` all exist with correct split |
| URL versioning under `/api/v1/` | PASS | `nutriplan/urls.py:27` — `path("api/v1/", include("nutriplan.api_router"))` |
| `api_router.py` as single aggregation point | PASS | `nutriplan/api_router.py` exists; `urls.py` doesn't change after M0 |
| Error envelope `{"error":{...}}` | PASS | `core/exceptions.py` — `_error_envelope()` + `app_exception_handler` |
| Pagination class | PASS | `core/pagination.py` — `StandardCursorPagination(page_size=20, ordering="-created_at", max_page_size=100)` |
| Logging shape (console dev / JSON prod) | PASS | `core/logging.py` — `get_logging_config(debug=)` switches formatters; prod uses `pythonjsonlogger` |
| Custom User model | PASS | `AUTH_USER_MODEL = "accounts.User"` set in `settings/base.py:45`. M0 stub wires it. |
| `on_delete` explicitness | PASS | M0 has no FKs to check. Constraint applies from M1+. |
| ArrayField/JSONField usage | N/A | No models with these fields in M0. |
| TimestampedModel mixin | PASS | `core/mixins.py` — abstract `TimestampedModel` with `created_at`, `updated_at` |
| PlaceholderAuthentication stub | PASS | `core/authentication.py` — no-op returning `None`; `settings/base.py` wires `FirebaseAuthentication` directly (M1 did this; M0 spec allowed placeholder) |

**Note on auth:** CLAUDE.md §7 and spec say M0 should have `PlaceholderAuthentication` in `REST_FRAMEWORK`, upgraded in M1. The current `settings/base.py` shows `FirebaseAuthentication` already wired — M1 upgraded it correctly. The `core/authentication.py` placeholder still exists as dead code but is harmless.

---

### Hard-rule audit (CLAUDE.md §8)

| Rule | Status | Notes |
|---|---|---|
| PostgreSQL only (no SQLite) | PASS | `DATABASES = env.db("DATABASE_URL")` — postgres URL only. `db.sqlite3` is in `.gitignore`. |
| Custom User model from M1 | PASS | `AUTH_USER_MODEL = "accounts.User"` set in `settings/base.py`. Model defined in M1. |
| Service layer enforced | PASS | No business logic in views/serializers — M0 has only healthz (no views to check). |
| `request.user` only | PASS | No user identity flow in M0. |
| Never trust GPT macros | N/A | No GPT in M0. |
| No external API calls in `save()` or signals | PASS | No models with save() logic in M0. |
| No new libraries beyond spec | PASS | All packages in `base.txt` are in `tech_stack`. |
| Every dependency pinned | PASS | All 11 packages in `base.txt` use exact versions (`==`). |
| Secrets via env only | PASS | `django-environ` throughout; `.env.example` pre-populates all vars. |
| Tests not optional (≥80% services) | PASS | 8 tests at M0; no services in M0 so ≥80% doesn't apply yet. Spec explicitly allows this. |
| Migrations ship with model change | PASS | `AUTH_USER_MODEL` set in M0; actual migration ships in M1 (when User model is created). Acceptable staging. |
| One module at a time | PASS | M0 is complete before M1 began. |

**All 12 hard rules: PASS for M0 scope.**

---

### Things-to-avoid audit

| Rule | Status | Notes |
|---|---|---|
| Do not use SQLite anywhere | PASS | Not in settings, not in test config |
| Do not use Django's default User | PASS | `AUTH_USER_MODEL` overrides it |
| Do not put business logic in serializers/views | PASS | No app views in M0 |
| Do not call external APIs from save()/signals | PASS | No app models in M0 |
| Do not hand-roll JWT verification | PASS | firebase-admin SDK used in M1; no JWT code in M0 |
| Do not commit secrets | PASS | `.gitignore` correctly excludes `secrets/`, `.env` |
| Do not skip migrations | PASS | `AUTH_USER_MODEL` set; migration created in M1 when model exists |
| Do not trust client-supplied user_id | PASS | Not applicable in M0 |
| Do not trust GPT-returned macros | N/A | Not applicable in M0 |
| Do not silently substitute features | PASS | No spec deviations per PROGRESS.md |
| Do not add libraries beyond tech_stack | PASS | All packages in spec |
| Do not start next module before previous passes | PASS | M1 starts after M0 criteria met |

**All rules: PASS for M0 scope.**

---

### Context-update verification (CLAUDE.md §12)

| Step | Status | Evidence |
|---|---|---|
| 12.1 Append to `docs/PROGRESS.md` | COMPLETE | M0 entry present (lines 29-47): correct format, all fields populated |
| 12.2 Update §3 of CLAUDE.md | COMPLETE | §3 shows `Active module: M2_profiles`, `Last completed: M1_accounts` — M0 and M1 both rolled through. M0 state was captured. |
| 12.3 Update `.env.example` | COMPLETE | All M0 env vars pre-declared with annotations and module tags |
| 12.4 Update `docs/RUNBOOK.md` | COMPLETE | RUNBOOK.md has full Postgres setup, Makefile table, all workflows. Much richer than the spec's minimum. |
| 12.5 Update §13 with conventions | COMPLETE | 6 M0 bullets present in §13 covering `PlaceholderAuthentication`, `api_router.py`, `django-environ`, `mypy`, ruff N818, and `AppValidationError` naming |

**All 5 protocol steps: COMPLETE.**

---

### Test quality

| Metric | Value |
|---|---|
| Total tests at M0 | 8 (1 healthz + 7 exception handler tests) |
| Service coverage | N/A — no services in M0 |
| External services mocked | N/A — no external services touched in M0 |
| Real endpoint hits | None — healthz only hits local DB |
| Test locations | `tests/test_health.py`, `tests/test_exceptions.py` |
| Test tool | pytest + pytest-django (no Django TestCase) ✅ |
| Factory-boy | Imported in dev deps but not used in M0 (correct) |

**Notable:** The 7 exception handler tests in `tests/test_exceptions.py` cover all 5 exception types + DRF `NotAuthenticated` + DRF `ValidationError`. Excellent coverage of `core/exceptions.py` at M0.

---

### Issues found

1. `[MINOR] core/authentication.py` — `PlaceholderAuthentication` is now dead code. M1 replaced it in `settings/base.py` but the file still exists. No runtime impact but creates mild confusion. Suggested fix: add a `# DEPRECATED — replaced by apps.accounts.authentication.FirebaseAuthentication in M1` comment, or delete in M2 cleanup.

2. `[MINOR] nutriplan/settings/base.py:45` — `AUTH_USER_MODEL = "accounts.User"` is set in `base.py` which means it was always pointing at the custom model even before the M1 migration was created. This is the correct approach (M1 immediately creates the migration), but means any developer who installs M0 alone without running M1 migration would get an `accounts_user` table missing error on `migrate`. This is by design and documented, but could confuse newcomers. No fix needed; worth a comment.

3. `[MINOR] pyproject.toml` — `django-ratelimit` and `django-filter` are in `tech_stack.backend` but `django-ratelimit` is not in `requirements/base.txt`. This is fine for M0 (rate limiting is an M8 concern), but should be noted — the spec lists it in the stack. Add it when M8 starts.

---

### Overall verdict

**APPROVED**

M0 is a clean, well-structured bootstrap. All acceptance criteria pass. The spec-required files are all present, properly split, and in the right locations. The test suite is small but well-targeted, covering the two pieces of M0 behaviour that have actual logic (healthz + exception handler). Context update protocol was fully executed. No blockers.
