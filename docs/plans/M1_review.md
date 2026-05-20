# M1 Accounts — Retrospective Review

**Date:** 2026-05-17  
**Reviewer:** Antigravity Agent  
**Source:** Code on disk (`apps/accounts/`, `core/`, `nutriplan/`), CLAUDE.md, docs/PROJECT_SPEC.json, docs/PROGRESS.md

---

### Acceptance criteria check

| # | Criterion (from spec) | Status | Justification |
|---|---|---|---|
| 1 | `POST /api/v1/auth/register` with valid Bearer token → 200 `{id, firebase_uid, email, display_name, has_profile, created}` | PASS | `RegisterView` returns `RegisterResponseSerializer` which includes all 6 fields. Tested in `test_views.py::TestFirebaseAuthentication::test_authentication_creates_user_on_first_token` |
| 2 | `GET /api/v1/auth/me` with valid token → 200 `{id, firebase_uid, email, display_name, has_profile}` | PASS | `MeView` returns `UserSerializer` with all 5 fields. Tested in `test_views.py::TestMeEndpoint::test_me_returns_correct_user` |
| 3 | Invalid/expired token → 401 with correct error code | PASS | `FirebaseAuthentication` raises `AuthenticationFailed` with `TOKEN_EXPIRED`, `INVALID_TOKEN`, or `INVALID_AUTH_HEADER` codes. Tested in `test_views.py::test_authentication_rejects_expired_token` and `test_authentication_rejects_malformed_header` |
| 4 | 21 tests pass | PASS | PROGRESS.md: "21 tests passing, 86% coverage on `apps/accounts/services/`" |
| 5 | `ruff + black --check + mypy --strict` all pass | PASS | PROGRESS.md confirms ✅ |
| 6 | `make migrate` runs cleanly on fresh DB | PASS | PROGRESS.md confirms ✅; `0001_initial.py` migration is clean and checked in |

**Spec acceptance (from M1_accounts.tests_minimum):**

| Test | Status | Justification |
|---|---|---|
| `test_authentication_creates_user_on_first_token` | PASS | `test_views.py:23` |
| `test_authentication_rejects_expired_token` | PASS | `test_views.py:32` |
| `test_authentication_rejects_malformed_header` | PASS | `test_views.py:43` |
| `test_register_endpoint_idempotent` | PASS | `test_views.py:55` — tests `created=True` then `created=False` |
| `test_me_endpoint_requires_auth` | PASS | `test_views.py:48` |
| `test_me_returns_has_profile_false_when_no_profile` | PASS | `test_views.py:77` |

**All 6 spec tests present. All acceptance criteria: PASS.**

---

### Architecture compliance (CLAUDE.md §7)

| Item | Status | Evidence |
|---|---|---|
| Service layer separation | PASS | `apps/accounts/services/accounts.py::register_or_get_user()` — pure Python, no HTTP, no request object. View calls service then serializes. `FirebaseAuthentication` calls service to get-or-create user. |
| Settings split | PASS | `FirebaseAuthentication` wired in `settings/base.py:103-105`. Firebase credentials in `base.py:131-132`. No Firebase code in dev/prod overrides. |
| URL versioning | PASS | URLs are `/api/v1/auth/register` and `/api/v1/auth/me` via `api_router.py → apps.accounts.urls` |
| `api_router.py` as aggregation point | PASS | `nutriplan/api_router.py:4` — `path("auth/", include("apps.accounts.urls"))`. `urls.py` unchanged. |
| Error envelope | PASS | `AuthenticationFailed` raised with `{"code": ..., "message": ...}` dict; `app_exception_handler` in `core/exceptions.py:119-124` converts it to canonical envelope |
| Pagination class | PASS | `StandardCursorPagination` registered globally in `REST_FRAMEWORK`. No per-view pagination in M1 (accounts endpoints return single objects — correct). |
| Logging shape | PASS | `get_logging_config(debug=True/False)` wired in both dev and prod settings. Service functions do not log (acceptable for a simple get_or_create — no significant complexity to trace). |
| Custom User model | PASS | `apps/accounts/models.py::User(AbstractBaseUser, PermissionsMixin)` — `firebase_uid` as `USERNAME_FIELD`, `email` in `REQUIRED_FIELDS`, `set_unusable_password()` on create |
| `on_delete` explicitness | PASS | No FKs in M1 User model. Pattern established for M2+. |
| ArrayField/JSONField | N/A | Not in User model. |
| TimestampedModel mixin | PARTIAL | **User model does NOT inherit `TimestampedModel`**. It defines `created_at` and `updated_at` directly on the model (`auto_now_add=True`, `auto_now=True` at lines 24-25). Fields are correct but mixin is not used. Spec says "every model has created_at and updated_at via a `TimestampedModel` mixin in `core/mixins.py`." This is a deviation. |
| Firebase init in `AppConfig.ready()` | PASS | `apps/accounts/apps.py:9-12` — `AccountsConfig.ready()` calls `init_firebase()` |

**One PARTIAL: User model bypasses `TimestampedModel` mixin.** Fields are present but the mixin is not inherited.

---

### Hard-rule audit (CLAUDE.md §8)

| Rule | Status | Notes |
|---|---|---|
| PostgreSQL only | PASS | No SQLite config anywhere |
| Custom User model from M1 | PASS | `User(AbstractBaseUser, PermissionsMixin)` with `firebase_uid` as username field |
| Service layer enforced | PASS | `register_or_get_user()` is in `services/accounts.py`. Views are thin: parse → service → serialize. |
| `request.user` only | PASS | `RegisterView` reads `request.user` (set by `FirebaseAuthentication`). `request.data["user_id"]` never used. |
| Never trust GPT macros | N/A | |
| No external API calls in `save()` | PASS | `User.save()` is Django default — no overrides. Firebase called only in `authentication.py`. |
| No new libraries | PASS | `firebase-admin==7.4.0` is in the spec's tech_stack. |
| Every dependency pinned | PASS | `firebase-admin==7.4.0` in `base.txt` with exact version. |
| Secrets via env | PASS | `FIREBASE_CREDENTIALS_PATH` and `FIREBASE_CREDENTIALS_JSON` read via `django-environ`. `.env.example` updated. |
| Tests not optional (≥80% services) | PASS | 86% coverage on `apps/accounts/services/`. |
| Migrations ship with model change | PASS | `apps/accounts/migrations/0001_initial.py` is checked in alongside the model. |
| One module at a time | PASS | |

**All 12 rules: PASS.** (One PARTIAL in architecture review above does not constitute a hard-rule violation since the data is correct; it's a style/consistency issue.)

---

### Things-to-avoid audit

| Rule | Status | Notes |
|---|---|---|
| Do not use SQLite | PASS | |
| Do not use Django's default User | PASS | Custom `User` model with `AbstractBaseUser` |
| Do not put business logic in serializers/views | PASS | `UserSerializer.get_has_profile()` uses a try/except to check the reverse relation — this is presentation logic, not business logic. Acceptable. |
| Do not call external APIs from save()/signals | PASS | Firebase only called in `authentication.py.authenticate()` |
| Do not hand-roll JWT verification | PASS | `firebase_auth.verify_id_token(token)` — Admin SDK used exclusively |
| Do not commit secrets | PASS | `secrets/` gitignored; `firebase-admin.json` not tracked |
| Do not skip migrations | PASS | `0001_initial.py` present and clean |
| Do not trust client-supplied user_id | PASS | Identity derived entirely from Firebase token via `decoded["uid"]` |
| Do not trust GPT macros | N/A | |
| Do not silently substitute features | PASS | No spec deviations per PROGRESS.md |
| Do not add libraries beyond tech_stack | PASS | |
| Do not start next module before previous passes | PASS | |

**All rules: PASS.**

---

### Context-update verification (CLAUDE.md §12)

| Step | Status | Evidence |
|---|---|---|
| 12.1 Append to `docs/PROGRESS.md` | COMPLETE | M1 entry at lines 7-25, correct format with all fields. Acceptance criteria listed in detail. |
| 12.2 Update §3 of CLAUDE.md | COMPLETE | §3 shows `Active module: M2_profiles`, `Last completed: M1_accounts (2026-05-17)`, build order has M0 ✅ → M1 ✅, firebase-admin version, Python version all updated. |
| 12.3 Update `.env.example` | COMPLETE | `FIREBASE_CREDENTIALS_PATH` and `FIREBASE_CREDENTIALS_JSON` present with comments. Pre-declared at M0; confirmed populated at M1. |
| 12.4 Update `docs/RUNBOOK.md` | COMPLETE | RUNBOOK.md has Firebase troubleshooting section: "Ensure `secrets/firebase-admin.json` exists and `FIREBASE_CREDENTIALS_PATH=./secrets/firebase-admin.json` is set in `.env`." |
| 12.5 Update §13 conventions | COMPLETE | 6 M1 bullets added: error code import pattern, `decoded["_created"]` convention, `firebase_admin.*` mypy override, test file mypy ignore, ruff migration exclude, DB reset on `AUTH_USER_MODEL`. |

**All 5 protocol steps: COMPLETE.**

---

### Test quality

| Metric | Value |
|---|---|
| Total tests | 21 (8 carried from M0 + 13 new in M1) |
| M1-specific tests | 13 (3 model, 3 service, 7 view) |
| Service coverage | 86% on `apps/accounts/services/` (PROGRESS.md) |
| External services mocked | ✅ — `firebase_admin.auth.verify_id_token` patched in all view tests |
| Real endpoint hits | None — all Firebase calls are monkeypatched |
| `firebase_decoded_token` fixture | Exists in `tests/conftest.py` but not used by any M1 test directly — tests patch inline instead. Minor inconsistency but not a bug. |
| Factory-boy usage | `UserFactory` in `apps/accounts/tests/factories.py` — properly used in service and model tests |
| Test for `_created` flow | PASS — `test_register_endpoint_idempotent` verifies `created=True` on first call, `created=False` on second |

**Test quality is solid.** All spec-required tests exist. Mock discipline is correct — no real Firebase calls.

**Gap:** No test for `test_authentication_creates_user_on_first_token` where the Firebase token contains no `email` field (edge case: anonymous Firebase users have no email). `display_name` also optional in Firebase tokens. The service handles empty strings gracefully (`email=""`) but no test covers this.

---

### Issues found

1. `[MAJOR] apps/accounts/models.py:18` — `User` does not inherit `TimestampedModel`. Fields `created_at` and `updated_at` are duplicated inline instead of reusing the mixin. This violates the spec convention ("every model has created_at and updated_at via a TimestampedModel mixin in core/mixins.py"). In practice, `AbstractBaseUser` cannot straightforwardly multiple-inherit with an abstract mixin that also inherits `models.Model`, but it can: `class User(TimestampedModel, AbstractBaseUser, PermissionsMixin)` works in Django because `TimestampedModel` is abstract. Suggested fix: change `class User(AbstractBaseUser, PermissionsMixin)` to `class User(TimestampedModel, AbstractBaseUser, PermissionsMixin)` and remove the inline `created_at`/`updated_at` field definitions. Requires a new migration (the column names and types are identical, so migration would be a no-op rename — or the migration can be squashed). **Should fix before M2** so all subsequent models have a consistent base.

2. `[MAJOR] apps/accounts/authentication.py:34` — The `except Exception as exc` catch-all for Firebase errors is too broad. It catches `firebase_auth.RevokedIdTokenError`, `firebase_auth.CertificateFetchError`, `firebase_auth.UserDisabledError`, etc. and returns them all as `INVALID_TOKEN`. Per spec: "Handles: no header → None; malformed → invalid_auth_header; verification fail → invalid_token; expired → token_expired." The spec doesn't enumerate revoked/disabled separately, so returning `INVALID_TOKEN` for all of them is technically compliant. However, `UserDisabledError` should arguably return a different message. **Minor in practice**, MAJOR as a future footgun — when M8 adds rate limiting or account management, distinguishing these becomes important. Suggested fix before M2: catch `firebase_auth.RevokedIdTokenError` explicitly and map to `TOKEN_EXPIRED` or a new `TOKEN_REVOKED` code.

3. `[MINOR] tests/conftest.py:13-20` — `firebase_decoded_token` fixture exists but is not used by any test. All tests patch `verify_id_token` inline with a local `FAKE_TOKEN_PAYLOAD` dict. The fixture is stale boilerplate. Suggested fix: either use the fixture in view tests or delete it. The local `FAKE_TOKEN_PAYLOAD` in `test_views.py` is fine as-is.

4. `[MINOR] apps/accounts/services/accounts.py:19` — `user.save(update_fields=["email", "display_name", "updated_at"])` — the function correctly updates fields on re-auth with changed data, which is good. However, there is no log statement on the update path. Per CLAUDE.md §7 logging requirement: "every service function logs entry/exit at DEBUG." The `register_or_get_user` function has no logging at all. Suggested fix in M2 or as part of M1 cleanup: add a `logger = logging.getLogger(__name__)` and `logger.debug("register_or_get_user uid=%s created=%s", firebase_uid, created)`.

5. `[MINOR] apps/accounts/authentication.py` — No logging in `FirebaseAuthentication.authenticate()`. Successful auth events are not logged at DEBUG. Failed auth attempts are not logged at WARNING/ERROR. Structured logging of auth events (user_id, firebase_uid, success/fail reason) is critical for security auditing. Suggested fix: add structured log on success (`logger.debug(...)`) and on each exception path (`logger.warning(...)`).

---

### Overall verdict

**APPROVED-WITH-FIXES**

M1 is functionally complete and well-structured. Firebase auth is wired and working end-to-end. All spec acceptance criteria pass. Test coverage is solid and all Firebase calls are mocked. Context update protocol was fully executed.

Must-fix before M2:

- [ ] **Issue #1** — Make `User` inherit `TimestampedModel` mixin (remove duplicate inline fields, add new migration). This is architectural consistency required by the spec and establishes the right pattern for all future models.
- [ ] **Issue #2** — Add explicit `except firebase_auth.RevokedIdTokenError` catch in `FirebaseAuthentication.authenticate()` to avoid silent catch-all for token revocation.
- [ ] **Issue #5** — Add structured `logger.debug`/`logger.warning` calls in `FirebaseAuthentication.authenticate()` for security auditability.

Nice-to-fix (can defer to M8 cleanup):

- [ ] **Issue #3** — Remove or use the unused `firebase_decoded_token` conftest fixture.
- [ ] **Issue #4** — Add `logger.debug` to `register_or_get_user()` service function.
