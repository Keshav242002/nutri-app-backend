# M6 — Celery + Background Jobs

Daily plan pre-generation and nutrition summary safety-net, driven by timezone-aware scheduling. **No new Django apps** — tasks live in existing apps. Key deliverable: users wake up to pre-generated meal plans at 4 AM local time, and yesterday's nutrition summaries are guaranteed correct by 2 AM UTC.

## Prerequisite Gate

- [x] M5 acceptance criteria met — 363 tests, 95% coverage
- [x] Redis 7 running locally (`redis-cli ping` → `PONG`) — Redis 8.8.0 installed via Homebrew
- [x] `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` set in `.env`
- [x] User aware they need `make worker` and `make beat` in separate terminals

---

## Resolved Decisions

> [!NOTE]
> **Q1 — 4 AM timezone window: CONFIRMED.**
> Hourly beat fires `generate_plans_for_all_users`, which checks each user's local time via `profile.timezone`. If `local_now.hour == 4`, the user's plan is dispatched. **Critical**: lazy generation in `GET /mealplans/today/` remains the correctness guarantee. The cron is a **pre-warming optimization**, not the only path. If the worker is down, users still get plans on first API request.

> [!NOTE]
> **Q2 — Today + tomorrow: CONFIRMED.**
> Two `PeriodicTask` rows (`generate-plans-today-hourly` and `generate-plans-tomorrow-hourly`), same function, different `target` arg. Dispatch-side double-firing is harmless because `get_or_generate_plan` is idempotent — no dedup logic needed.

> [!NOTE]
> **Q3 — No new dependencies: CONFIRMED.**
> `zoneinfo` stdlib (Python 3.9+) over `pytz`. `celery` and `django-celery-beat` already in `requirements/base.txt`. No new pip packages.

> [!NOTE]
> **Timezone default: CONFIRMED.**
> `timezone` field defaults to `"Asia/Kolkata"` — Indian-first app, 90%+ users are IST.

---

## Proposed Changes

### DietaryProfile — timezone field

#### [MODIFY] [models.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/profiles/models.py)
- Add `timezone = CharField(max_length=50, default="Asia/Kolkata")` to `DietaryProfile`
- Validate via `zoneinfo.available_timezones()` in `clean()`

#### [NEW] `apps/profiles/migrations/0003_timezone_field.py`
- Migration adding `timezone` column with default `"Asia/Kolkata"`

#### [MODIFY] [serializers.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/apps/profiles/serializers.py)
- Add `timezone` as optional field in `OnboardingSerializer` (default `"Asia/Kolkata"`)
- Add `timezone` to `ProfileSerializer` read output
- Add `timezone` to `ProfileUpdateSerializer` (PATCH-able)

---

### Celery Configuration

#### [MODIFY] [base.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/nutriplan/settings/base.py)
- Add `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` from env

#### [VERIFY] [celery.py](file:///Users/keshavrudo/nutriapp/nutri-app-backend/nutriplan/celery.py)
- Already correct — no changes needed

---

### Celery Tasks

#### [NEW] `apps/mealplans/tasks.py`

| Task | Signature | Description |
|------|-----------|-------------|
| `generate_plan_for_user` | `(user_id: int, plan_date_iso: str)` | `bind=True, max_retries=3, default_retry_delay=60`. Loads user, calls `get_or_generate_plan(user, date)`. Retries on transient DB errors. |
| `generate_plans_for_all_users` | `(target: str)` | Iterates active users with profiles, checks local time 4:00–4:59 AM window via `profile.timezone`, dispatches `generate_plan_for_user.delay()` for qualifying users. |

#### [NEW] `apps/tracker/tasks.py`

| Task | Signature | Description |
|------|-----------|-------------|
| `recompute_yesterday_summaries` | `()` | Iterates active users with yesterday's MealLogs. Calls `recompute_daily_summary(user, yesterday)` for each. Safety-net only. |

---

### Beat Schedule (via data migration)

#### [NEW] `apps/mealplans/migrations/0003_celery_beat_schedule.py`

| Schedule Name | Type | Expression | Task |
|---------------|------|------------|------|
| `generate-plans-today-hourly` | `IntervalSchedule` (60 min) | — | `apps.mealplans.tasks.generate_plans_for_all_users` with `args='["today"]'` |
| `generate-plans-tomorrow-hourly` | `IntervalSchedule` (60 min) | — | `apps.mealplans.tasks.generate_plans_for_all_users` with `args='["tomorrow"]'` |
| `recompute-summaries-daily` | `CrontabSchedule` | `0 2 * * *` (02:00 UTC) | `apps.tracker.tasks.recompute_yesterday_summaries` |

---

### Key Design Decisions

1. **Lazy generation is the correctness guarantee; cron is pre-warming.** `GET /mealplans/today/` calls `get_or_generate_plan()` which creates a plan on-the-fly if none exists. The hourly cron pre-generates plans so users don't wait — but if the worker is down, the API fallback covers them. Do NOT remove lazy generation.

2. **Double-dispatch is harmless.** `get_or_generate_plan` is idempotent (returns existing plan if one exists). If the cron fires for a user who already has today's plan (e.g., from a lazy-gen API call), the task is a no-op. No dedup logic needed.

3. **No new Django app.** Tasks live in `apps/mealplans/tasks.py` and `apps/tracker/tasks.py` per CLAUDE.md §7.

4. **Thin task wrappers.** Tasks receive IDs (not model instances), call existing service functions, log results.

5. **`zoneinfo` over `pytz`.** Python 3.9+ stdlib, no extra dependency.

6. **Data migration for beat schedule.** Avoids manual admin setup. Idempotent via `get_or_create`.

7. **`CELERY_TASK_ALWAYS_EAGER` in tests.** Tasks execute synchronously in-process, no Redis needed during test runs.

---

## Verification Plan

### Automated Tests

| Test | What it verifies |
|------|------------------|
| `test_generate_plan_for_user_creates_plan` | Task creates a MealPlan for the given user+date |
| `test_generate_plan_for_user_idempotent` | Calling twice doesn't duplicate |
| `test_generate_plan_for_user_retries_on_failure` | Task retries on transient error |
| `test_generate_plans_skips_users_in_wrong_tz_window` | Only users in 4 AM window get dispatched |
| `test_generate_plans_dispatches_for_correct_tz_window` | Correct-window users get plan generated |
| `test_generate_plans_target_today_uses_local_date` | `target="today"` resolves to local date |
| `test_generate_plans_target_tomorrow` | `target="tomorrow"` generates for local_date + 1 |
| `test_recompute_yesterday_summaries_runs` | Calls `recompute_daily_summary` for users with logs |
| `test_recompute_yesterday_summaries_skips_users_without_logs` | No-log users skipped |
| `test_timezone_field_default` | New profiles get `"Asia/Kolkata"` |
| `test_timezone_field_accepts_valid_tz` | PATCH with valid tz succeeds |
| `test_timezone_field_rejects_invalid` | PATCH with invalid tz returns 400 |

### Lint & Type Checks
```bash
make lint   # ruff + black --check + mypy --strict
make test   # all tests pass, ≥80% coverage on task files
```

### Manual Verification
- `make worker` (terminal 1) + `make beat` (terminal 2)
- Django admin → Periodic Tasks → 3 tasks present
- Shell: `generate_plan_for_user.delay(1, "2026-05-31")` → check worker logs
