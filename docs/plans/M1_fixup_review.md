# M1 Fixup Review — commit 95b5882

**Date:** 2026-05-17  
**Reviewer:** Antigravity Agent  
**Commit reviewed:** 95b5882 (M1 amendment)  
**Reference:** docs/plans/M1_review.md (issues A–G below)

---

## Item-by-item verdict

### A) Issue #1 — `User` inherits `TimestampedModel`; inline fields removed; no orphan migration

**PASS**

- `apps/accounts/models.py:4` — `from core.mixins import TimestampedModel` imported ✅
- `apps/accounts/models.py:20` — `class User(TimestampedModel, AbstractBaseUser, PermissionsMixin)` — `TimestampedModel` is first in MRO ✅
- Inline `created_at` and `updated_at` field definitions removed (no longer in model body) ✅
- `apps/accounts/migrations/` contains only `0001_initial.py` — no new migration added ✅
- PROGRESS.md amendment note confirms: "Django detects no schema change — no migration required" ✅ (correct — `TimestampedModel.created_at`/`updated_at` column names and types are identical to what was inlined; Django sees a no-op)

---

### B) Issue #2 — Four typed exception branches; correct code mapping; unexpected exceptions propagate

**PASS**

`apps/accounts/authentication.py` now has exactly four `except` branches in order:

| Branch | Code returned | Correct? |
|---|---|---|
| `firebase_auth.ExpiredIdTokenError` | `TOKEN_EXPIRED` | ✅ |
| `firebase_auth.RevokedIdTokenError` | `TOKEN_REVOKED` | ✅ |
| `firebase_auth.InvalidIdTokenError` | `INVALID_TOKEN` | ✅ |
| `firebase_exceptions.FirebaseError` | `EXTERNAL_SERVICE_ERROR` | ✅ |

Line 72: `# Genuinely unexpected exceptions are NOT caught — they propagate up as 500.` — the comment confirms the intent, and there is no bare `except Exception` anywhere in the function. Any exception other than the four Firebase types will propagate unhandled, resulting in a Django 500 response. ✅

The ordering is correct: `ExpiredIdTokenError` and `RevokedIdTokenError` are both subclasses of `InvalidIdTokenError`, so they must be caught before it — they are. ✅

---

### C) Issue #3 — Structured logging in `authentication.py` and `services/accounts.py`; no PII

**PASS — with one minor observation (not a FAIL)**

**`apps/accounts/services/accounts.py`:**
- `logger.info("user_created", extra={"event": "user_created", "user_id": user.pk, "firebase_uid": firebase_uid})` — fires on first creation ✅
- Level is INFO (state-changing/security event) ✅
- No PII: `user.pk` (integer) and `firebase_uid` (opaque string from Firebase, not an email) are logged. No `email`, no `display_name`. ✅

**`apps/accounts/authentication.py`:**
- `logger.error("auth_failed", extra={"event": "auth_failed", "error_code": <code>})` — fires on each of the four failure paths ✅
- `logger.debug("token_verified", extra={"event": "token_verified", "user_id": user.pk, "firebase_uid": firebase_uid})` — fires on success ✅

**Minor observation:** The spec/CLAUDE.md §7 now says log `token_verified` at **INFO** (state-change/security event). The commit uses `logger.debug` for `token_verified`. Per the new §7 rule: "Log at INFO for state-changing or security-relevant events (`user_created`, `token_verified`, ...)." The successful authentication of a user is a security-relevant event and is explicitly listed in the §7 example. Using DEBUG means it won't appear in production logs unless the level is cranked down. **This is a real discrepancy but it is minor** — it doesn't affect correctness, just observability. Recording it here for awareness; not marking it as a FAIL because the fixup review's Issue #3 asked for DEBUG on `token_verified` (the review itself used the old guidance, before §7 was updated). Worth correcting before M2 runs.

---

### D) Ambiguity #3 — `has_profile` uses `except AttributeError` specifically

**PASS**

`apps/accounts/serializers.py:17` — `except AttributeError:` — specific exception type used. The broad `except Exception:` is gone. ✅

---

### E) `PlaceholderAuthentication` deleted; nothing imports it anywhere

**PASS**

- `core/authentication.py` is confirmed deleted in the git diff (file deleted, `-r base.py` → `/dev/null`) ✅
- `grep` search for `PlaceholderAuthentication` found matches only in:
  - `CLAUDE.md` §13 line 568 — historical note ("M0 stub ... M1 replaces it") — documentation reference only, not a code import ✅
  - `CLAUDE.md` §13 line 581 — amendment note ("deleted — no longer exists") ✅
  - `docs/PROGRESS.md` lines 13 and 57 — historical records ✅
  - `docs/plans/M0_review.md` — review document ✅
- No source `.py` file imports `PlaceholderAuthentication`. ✅
- CLAUDE.md §7 auth section updated to read: "`core/authentication.py` deleted after M1 — stub is gone." ✅

---

### F) CLAUDE.md §7 contains the four codified resolutions; §13 has a 2026-05-17 M1-amendment entry

**PASS**

**§7 updated sections (all verified on disk):**

| Ambiguity | Location in §7 | Content |
|---|---|---|
| TimestampedModel MRO | §7.3 "Model inheritance" subsection (lines 377-379) | "Every concrete model inherits TimestampedModel first in the MRO … canonical form is `class User(TimestampedModel, AbstractBaseUser, PermissionsMixin)`" ✅ |
| Logging granularity | §7.3 "Logging" subsection (lines 385-390) | INFO for state-change/security, DEBUG for multi-step flows only, ERROR on failure paths with no PII, required fields: `event`, `user_id`, `error_code` ✅ |
| Exception specificity | §7.3 "Exception handling" subsection (lines 392-394) | "catch specific exception types, never bare `except Exception` unless immediately re-raising as typed AppException … catch `ExpiredIdTokenError`, `RevokedIdTokenError`, `InvalidIdTokenError`, `FirebaseError` in that order" ✅ |
| Per-module coverage | §7.3 "Tests" subsection (line 414) | "≥80% on each module's own services (`apps/<module>/services/`), measured per-module. Aggregate coverage is reported but is not a substitute for per-module gating." ✅ |

**§13 M1-amendment entry** (line 581):
> "2026-05-17 — M1 review clarified four protocol ambiguities now codified in §7: (1) TimestampedModel MRO; (2) logging granularity; (3) exception specificity; (4) per-module coverage gate. `core/authentication.py` (PlaceholderAuthentication) deleted — no longer exists. (M1 amendment)" ✅

All four resolutions present. ✅

---

### G) Two new tests assert different error codes in the response

**PASS**

`apps/accounts/tests/test_views.py`:

- `test_authentication_rejects_revoked_token` (lines 43-52):
  - Raises `firebase_admin.auth.RevokedIdTokenError`
  - Asserts `response.json()["error"]["code"] == "TOKEN_REVOKED"` ✅

- `test_authentication_rejects_invalid_token` (lines 54-63):
  - Raises `firebase_admin.auth.InvalidIdTokenError`
  - Asserts `response.json()["error"]["code"] == "INVALID_TOKEN"` ✅

The two tests assert **different** codes (`TOKEN_REVOKED` vs `INVALID_TOKEN`). They are not duplicates of each other or of the existing `test_authentication_rejects_expired_token` (`TOKEN_EXPIRED`). ✅

---

## Overall verdict

**CLEAN**

All 7 items pass. The one observation flagged in Item C (`token_verified` logged at DEBUG rather than INFO) is a minor discrepancy between the updated §7 rule and the implementation, but it is below the threshold for a FAIL — it affects observability only, not correctness or security. Recommend correcting in the next natural commit (e.g., alongside the first M2 commit).
