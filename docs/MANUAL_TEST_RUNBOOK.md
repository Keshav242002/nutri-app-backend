# NutriPlan Backend — Manual Test Runbook

**Purpose:** Manually verify M0 (`/healthz`), M1 (auth), and M2 (profiles) endpoints against a live
dev server before committing the M2 implementation.

**Response envelope (all endpoints):**
- Success: `{"status": "success", "message": "...", "data": {...}}`
- Error: `{"status": "error", "message": "...", "error": {"code": "...", "details": {...}}}`

**When to use this runbook:** After `make test` and `make lint` are both green, before the §12
context-update commit.

---

> **Two testing modes — read this first.**
>
> - **Dev bypass mode (Sections 2–6):** uses a fixed fake user; no real Firebase token or Flutter
>   client needed. Faster, and isolated from Firebase wiring issues. Covers full endpoint and DB
>   verification coverage.
> - **Real Firebase mode (Section 7):** uses an actual Firebase ID token obtained via the Firebase
>   REST API. End-to-end verification that the Admin SDK token verification path works correctly.
>
> **Recommended workflow:** walk through Sections 2–6 with the dev bypass for full coverage, then
> run Section 7 to verify real Firebase auth works on the happy path.

---

## Section 1 — Environment setup

### 1.1 Enable the dev bypass

Add these two lines to your `.env` file (they default to `False`/`off` — you must flip them):

```
DEV_AUTH_BYPASS_ENABLED=True
DEV_AUTH_BYPASS_TOKEN=dev-bypass-token-do-not-ship
```

> **Important:** Restart the server after editing `.env`. Django only reads the file at startup.

### 1.2 Start the server
m
```bash
make run
# Server listens on http://localhost:8000
# You should see: "*** WARNING: DEV_AUTH_BYPASS_ENABLED is True. …" on stderr.
# That warning is expected and confirms the bypass is active.
```

### 1.3 The auth header

Every authenticated request needs exactly this header:

```
Authorization: Bearer dev-bypass-token-do-not-ship
```

The first request that carries this header auto-creates a dev user:
- `firebase_uid`: `dev-bypass-uid-001`
- `email`: `dev@nutriplan.test`
- `display_name`: `Dev User`

### 1.4 Base URL

```
http://localhost:8000
```

---

## Section 2 — Endpoint-by-endpoint tests

---

### 2.1 GET /healthz

**No auth required.**

**Expected:** `200 OK`

```json
{"status": "ok", "db": "ok"}
```

**curl:**
```bash
curl -s http://localhost:8000/healthz | python3 -m json.tool
```

**Postman:** `GET http://localhost:8000/healthz` — no headers needed.

---

### 2.2 POST /api/v1/auth/register

**Auth required.** Body can be empty JSON `{}`.

#### First call — creates user

**Expected:** `200 OK`, `data.created: true`

```json
{
  "status": "success",
  "message": "User registered successfully.",
  "data": {
    "id": 1,
    "firebase_uid": "dev-bypass-uid-001",
    "email": "dev@nutriplan.test",
    "display_name": "Dev User",
    "has_profile": false,
    "created": true
  }
}
```

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

#### Second call — idempotent

**Expected:** `200 OK`, `data.created: false`, same `id` and `firebase_uid`.

```json
{
  "status": "success",
  "message": "User already registered.",
  "data": {
    "id": 1,
    "firebase_uid": "dev-bypass-uid-001",
    "email": "dev@nutriplan.test",
    "display_name": "Dev User",
    "has_profile": false,
    "created": false
  }
}
```

---

### 2.3 GET /api/v1/auth/me

**Auth required.** Returns the authenticated user's record.

**Expected:** `200 OK`

```json
{
  "status": "success",
  "message": "User retrieved.",
  "data": {
    "id": 1,
    "firebase_uid": "dev-bypass-uid-001",
    "email": "dev@nutriplan.test",
    "display_name": "Dev User",
    "has_profile": false
  }
}
```

**curl:**
```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" | python3 -m json.tool
```

---

### 2.4 GET /api/v1/profiles/me — before onboarding

**Auth required.** No profile exists yet.

**Expected:** `404 Not Found`

```json
{
  "status": "error",
  "message": "Profile not found.",
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "details": {}
  }
}
```

**curl:**
```bash
curl -s http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" | python3 -m json.tool
```

---

### 2.5 POST /api/v1/profiles/onboarding — create profile

**Auth required.** This is the six-step questionnaire submitted as one payload.

**Request body:**
```json
{
  "date_of_birth": "1998-01-15",
  "sex": "male",
  "height_cm": 175,
  "weight_kg": "72.0",
  "activity_level": "moderate",
  "goal": "maintain",
  "primary_cuisine_region": "north_indian",
  "secondary_cuisine_preferences": ["punjabi"],
  "spice_tolerance": "medium",
  "diet_pattern": "vegetarian",
  "no_onion_garlic": false,
  "allergies": ["peanuts"],
  "dislikes": ["mushroom", "bitter gourd"],
  "daily_food_budget_inr": "200.00",
  "household_size": 2,
  "cooking_frequency": "daily",
  "max_prep_time_min": 30,
  "skill_level": "intermediate",
  "disclaimer_acknowledged": true
}
```

**Expected:** `200 OK`

Key fields to verify in `data`:

| Field | Expected value |
|---|---|
| `target_calories` | `2602` |
| `target_protein_g` | `162.6` |
| `target_carbs_g` | `325.2` |
| `target_fat_g` | `72.3` |
| `target_fiber_g` | `36.4` |
| `weekly_food_budget_inr` | `"1400.00"` (derived from daily × 7) |
| `age` | `28` |
| `no_onion_garlic` | `false` |
| `disclaimer_acknowledged` | *absent from response* (write-only) |

**Full example response:**
```json
{
  "status": "success",
  "message": "Profile created successfully.",
  "data": {
    "date_of_birth": "1998-01-15",
    "sex": "male",
    "height_cm": 175,
    "weight_kg": "72.0",
    "activity_level": "moderate",
    "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": ["punjabi"],
    "spice_tolerance": "medium",
    "diet_pattern": "vegetarian",
    "no_onion_garlic": false,
    "allergies": ["peanuts"],
    "dislikes": ["mushroom", "bitter gourd"],
    "daily_food_budget_inr": "200.00",
    "weekly_food_budget_inr": "1400.00",
    "household_size": 2,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "intermediate",
    "target_calories": 2602,
    "target_protein_g": 162.6,
    "target_carbs_g": 325.2,
    "target_fat_g": 72.3,
    "target_fiber_g": 36.4,
    "age": 28,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

> On the **second POST** (idempotency check), `message` changes to `"Profile updated successfully."` and the `data` shape is identical.

**curl:**
```bash
curl -s -X POST http://localhost:8000/api/v1/profiles/onboarding \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{
    "date_of_birth": "1998-01-15",
    "sex": "male",
    "height_cm": 175,
    "weight_kg": "72.0",
    "activity_level": "moderate",
    "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": ["punjabi"],
    "spice_tolerance": "medium",
    "diet_pattern": "vegetarian",
    "no_onion_garlic": false,
    "allergies": ["peanuts"],
    "dislikes": ["mushroom", "bitter gourd"],
    "daily_food_budget_inr": "200.00",
    "household_size": 2,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "intermediate",
    "disclaimer_acknowledged": true
  }' | python3 -m json.tool
```

> **Idempotency check:** POST the exact same payload again. Should return `200` with the same
> `target_calories`. Only one row should exist in the DB (see Section 4, query 2).

---

### 2.6 GET /api/v1/profiles/me — after onboarding

**Auth required.** Profile now exists.

**Expected:** `200 OK`

```json
{
  "status": "success",
  "message": "Profile retrieved.",
  "data": { "...same fields as onboarding response above..." }
}
```

Verify `data.age: 28` and `data.target_calories: 2602` are present.

**curl:**
```bash
curl -s http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" | python3 -m json.tool
```

> Also verify `has_profile` on `/auth/me` is now `true`:
> ```bash
> curl -s http://localhost:8000/api/v1/auth/me \
>   -H "Authorization: Bearer dev-bypass-token-do-not-ship" | python3 -m json.tool
> ```

---

### 2.7 PATCH /api/v1/profiles/me — change weight

**Auth required.**

**Request body:**
```json
{"weight_kg": "68.0"}
```

**Expected:** `200 OK`

```json
{
  "status": "success",
  "message": "Profile updated successfully.",
  "data": { "...full profile with updated values..." }
}
```

`data.target_calories` drops from `2602` → `2540` (lighter person burns slightly less).

| Field | Before | After |
|---|---|---|
| `weight_kg` | `"72.0"` | `"68.0"` |
| `target_calories` | `2602` | `2540` |

**curl:**
```bash
curl -s -X PATCH http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{"weight_kg": "68.0"}' | python3 -m json.tool
```

---

### 2.8 PATCH /api/v1/profiles/me — change goal to lose_weight

**Auth required.**

**Request body:**
```json
{"goal": "lose_weight"}
```

**Expected:** `200 OK`. Calorie target drops by ~500 kcal, macro split shifts to higher protein.

| Field | Before (maintain) | After (lose_weight) |
|---|---|---|
| `goal` | `"maintain"` | `"lose_weight"` |
| `target_calories` | `2540` | `2040` |
| `target_protein_g` | `158.8` | `178.5` ↑ (35% of kcal) |
| `target_carbs_g` | `317.5` | `204.0` ↓ (40% of kcal) |
| `target_fat_g` | `70.6` | `56.7` ↓ |
| `target_fiber_g` | `35.6` | `28.6` |

**curl:**
```bash
curl -s -X PATCH http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{"goal": "lose_weight"}' | python3 -m json.tool
```

---

### 2.9 PATCH /api/v1/profiles/me — switch to jain diet

**Auth required.**

**Request body:**
```json
{"diet_pattern": "jain"}
```

**Expected:** `200 OK`. The Jain rule auto-sets `no_onion_garlic: true` regardless of input.

| Field | Before | After |
|---|---|---|
| `diet_pattern` | `"vegetarian"` | `"jain"` |
| `no_onion_garlic` | `false` | **`true`** (auto-set by service) |
| `target_calories` | `2040` | `2040` (unchanged — no biometric change) |

**curl:**
```bash
curl -s -X PATCH http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{"diet_pattern": "jain"}' | python3 -m json.tool
```

---

### 2.10 PATCH /api/v1/profiles/me — switch to eat_healthier goal

**Auth required.**

**Request body:**
```json
{"goal": "eat_healthier"}
```

**Expected:** `200 OK`. Calories same as `maintain` (no delta), but fiber target jumps to 18g/1000 kcal.

| Field | Before (lose_weight) | After (eat_healthier) |
|---|---|---|
| `goal` | `"lose_weight"` | `"eat_healthier"` |
| `target_calories` | `2040` | `2540` |
| `target_fiber_g` | `28.6` | **`45.7`** (18g/1000 kcal vs 14g/1000 kcal) |

The fiber jump (28.6 → 45.7) is the key signal here. `eat_healthier` is identical to `maintain` in
calories but uses an elevated fiber density target to emphasise micronutrient-rich recipes in M4.

**curl:**
```bash
curl -s -X PATCH http://localhost:8000/api/v1/profiles/me \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{"goal": "eat_healthier"}' | python3 -m json.tool
```

---

## Section 3 — Validation error cases

All validation errors return `400 Bad Request` with this envelope:

```json
{
  "status": "error",
  "message": "...",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {}
  }
}
```

For each test below, POST to `/api/v1/profiles/onboarding` with the full happy-path payload from
§2.5, replacing only the field(s) described.

---

### 3.1 Age below 13

Replace `date_of_birth` with a date that makes the user 12 years old:

```json
{"date_of_birth": "2014-05-19"}
```

**Expected:** `400`, `"code": "VALIDATION_ERROR"`, message mentions age.

```bash
curl -s -X POST http://localhost:8000/api/v1/profiles/onboarding \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" \
  -H "Content-Type: application/json" \
  -d '{ ...full payload..., "date_of_birth": "2014-05-19" }' | python3 -m json.tool
```

---

### 3.2 Age above 100

```json
{"date_of_birth": "1920-01-01"}
```

**Expected:** `400`, `"code": "VALIDATION_ERROR"`.

---

### 3.3 Height out of range

```json
{"height_cm": 50}
```

or

```json
{"height_cm": 300}
```

**Expected:** `400`. Valid range is 100–250 cm.

---

### 3.4 Weight out of range

```json
{"weight_kg": "10.0"}
```

or

```json
{"weight_kg": "500.0"}
```

**Expected:** `400`. Valid range is 30.0–300.0 kg.

---

### 3.5 Budget both set but inconsistent

```json
{
  "daily_food_budget_inr": "100.00",
  "weekly_food_budget_inr": "1000.00"
}
```

`1000 ÷ 7 = 142.86`. `|142.86 - 100| / 142.86 ≈ 30%`, which exceeds the 5% tolerance.

**Expected:** `400`, message mentions budget inconsistency.

---

### 3.6 Neither budget field set

Remove both `daily_food_budget_inr` and `weekly_food_budget_inr` from the payload entirely.

**Expected:** `400`, message requires at least one budget field.

---

### 3.7 Disclaimer not acknowledged

```json
{"disclaimer_acknowledged": false}
```

**Expected:** `400`.

---

### 3.8 Invalid goal value

```json
{"goal": "ripped"}
```

**Expected:** `400`. Valid values: `lose_weight`, `maintain`, `gain_muscle`, `gain_weight_healthy`, `eat_healthier`.

---

### 3.9 Invalid primary_cuisine_region

```json
{"primary_cuisine_region": "european"}
```

**Expected:** `400`. Valid values: `north_indian`, `south_indian`, `east_indian`, `west_indian`.

---

### 3.10 Empty allergies array — should be ACCEPTED

```json
{"allergies": []}
```

**Expected:** `200 OK`. Empty array is valid; the field is optional.

---

### 3.11 Allergy from outside controlled vocab

```json
{"allergies": ["lavender"]}
```

**Expected:** `400`. Valid values: `dairy`, `eggs`, `gluten`, `peanuts`, `tree_nuts`, `soy`,
`shellfish`, `fish`, `sesame`, `mustard`.

---

## Section 4 — DBeaver verification

### 4.1 Connection details

| Setting | Value |
|---|---|
| **Host** | `localhost` |
| **Port** | `5432` |
| **Database** | `nutriplan` |
| **User** | `nutriplan` |
| **Password** | value of `DATABASE_URL` in `.env` (default: `nutriplan`) |

Connection string for reference: `postgres://nutriplan:nutriplan@localhost:5432/nutriplan`

---

### 4.2 SQL queries to run after the test flow above

Run these in order after completing all steps in Section 2.

**Query 1 — Verify the dev user row was created:**
```sql
SELECT id, firebase_uid, email, display_name, created_at
FROM accounts_user
WHERE firebase_uid = 'dev-bypass-uid-001';
```
Expected: exactly 1 row.

---

**Query 2 — Verify the profile row is linked and has computed targets:**
```sql
SELECT
    u.email,
    p.date_of_birth,
    p.goal,
    p.weight_kg,
    p.target_calories,
    p.target_fiber_g,
    p.daily_food_budget_inr,
    p.weekly_food_budget_inr,
    p.no_onion_garlic,
    p.diet_pattern
FROM profiles_dietaryprofile p
JOIN accounts_user u ON u.id = p.user_id
WHERE u.firebase_uid = 'dev-bypass-uid-001';
```
Expected after §2.10:
- `goal = 'eat_healthier'`
- `weight_kg = 68.0`
- `target_calories = 2540`
- `target_fiber_g = 45.7`
- `daily_food_budget_inr = 200.00`, `weekly_food_budget_inr = 1400.00`
- `no_onion_garlic = true` (set by Jain rule in §2.9)
- `diet_pattern = 'jain'`

---

**Query 3 — Verify ArrayFields are stored as PostgreSQL arrays:**
```sql
SELECT id, allergies, dislikes, secondary_cuisine_preferences
FROM profiles_dietaryprofile;
```
Expected:
- `allergies`: `{peanuts}`
- `dislikes`: `{mushroom,"bitter gourd"}`
- `secondary_cuisine_preferences`: `{punjabi}`

---

**Query 4 — Verify GIN indexes exist:**
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'profiles_dietaryprofile'
ORDER BY indexname;
```
Expected: at least 2 GIN indexes named `profile_allergies_gin` and `profile_cuisine_pref_gin`.

---

**Query 5 — Verify `disclaimer_acknowledged` is NOT a stored column:**
```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'profiles_dietaryprofile'
ORDER BY ordinal_position;
```
Expected: no `disclaimer_acknowledged` column in the list.

---

**Query 6 — Verify `age` is NOT a stored column:**

Same query as above. Expected: no `age` column — only `date_of_birth` is stored. Age is derived
live from `date_of_birth` on every read.

---

**Query 7 — Verify only one profile row exists (idempotency):**
```sql
SELECT COUNT(*) FROM profiles_dietaryprofile
WHERE user_id = (
    SELECT id FROM accounts_user WHERE firebase_uid = 'dev-bypass-uid-001'
);
```
Expected: `1`.

---

## Section 5 — Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `401 Unauthorized` on any endpoint | Wrong or missing auth header | Header must be exactly `Authorization: Bearer dev-bypass-token-do-not-ship` (note the space after `Bearer`) |
| `401` even with correct header | `DEV_AUTH_BYPASS_ENABLED=False` in `.env`, or server not restarted after editing | Set `True` in `.env`, restart `make run` |
| `401` even after restart | `DJANGO_DEBUG=False` in `.env` — bypass requires `DEBUG=True` | Ensure `DJANGO_DEBUG=True` (default in dev settings) |
| No `*** WARNING ***` on server start | Bypass is still disabled | Check `.env` for `DEV_AUTH_BYPASS_ENABLED=True` and restart |
| `404` on `/healthz` | Server not running, or wrong port | `make run` in the repo root; default port is 8000 |
| `500 Internal Server Error` | Unhandled exception in view or service | Check terminal output where `make run` is running |
| `psycopg2.errors.UndefinedTable` on startup | Migration not applied | `make migrate` |
| DBeaver can't connect | PostgreSQL not running | `pg_isready -h localhost`; if not ready: `brew services start postgresql@16` |
| `\d profiles_dietaryprofile` shows nothing | Wrong database selected in DBeaver | Confirm the connection is to database `nutriplan`, not `postgres` |
| `target_calories` is `null` | Profile created but `save()` failed silently | Should not happen; if it does, check server logs for `profile_validation_failed` event |

---

## Section 6 — Cleanup after testing

### 6.1 Delete the dev test data

Run in psql or DBeaver after all testing is complete:

```sql
DELETE FROM profiles_dietaryprofile
WHERE user_id = (
    SELECT id FROM accounts_user WHERE firebase_uid = 'dev-bypass-uid-001'
);

DELETE FROM accounts_user
WHERE firebase_uid = 'dev-bypass-uid-001';
```

### 6.2 Disable the dev bypass

Edit `.env`:
```
DEV_AUTH_BYPASS_ENABLED=False
```

Restart the server. The `*** WARNING ***` message should no longer appear.

### 6.3 Verify production safety

Open `nutriplan/settings/production.py` and confirm:

```python
# Hard-coded False in production — overrides any env var to prevent accidental exposure.
DEV_AUTH_BYPASS_ENABLED = False
```

This line is present and hardcoded. Even if someone accidentally sets `DEV_AUTH_BYPASS_ENABLED=True`
in a production environment file, this override ensures the bypass is always disabled in production.

---

## Section 8 — GET /api/v1/profiles/onboarding/questions

This endpoint returns the static questionnaire metadata that a client uses to render the onboarding
UI. It requires auth but takes no body.

### 8.1 Happy path

**Expected:** `200 OK`

```json
{
  "status": "success",
  "message": "Onboarding questionnaire retrieved.",
  "data": {
    "version": "1.0.0",
    "steps": [
      {
        "step": 1,
        "title": "Basic Information",
        "fields": [
          {"name": "date_of_birth", "type": "date", "label": "Date of Birth", ...},
          {"name": "sex", "type": "single_select", ...},
          {"name": "height_cm", "type": "number", ...},
          {"name": "weight_kg", "type": "number", ...}
        ]
      },
      ... 5 more steps ...
    ]
  }
}
```

**curl:**
```bash
curl -s http://localhost:8000/api/v1/profiles/onboarding/questions \
  -H "Authorization: Bearer dev-bypass-token-do-not-ship" | python3 -m json.tool
```

**Things to verify:**
- `data.steps` has exactly **6 steps** (Step 1–6)
- Step titles: `"Basic Information"`, `"Activity & Goal"`, `"Cuisine & Region"`,
  `"Dietary Pattern"`, `"Budget & Household"`, `"Cooking Constraints"`
- Step 5 budget fields have `"min_value": 100` (daily) and `"min_value": 700` (weekly)
- Step 6 includes `"name": "disclaimer_acknowledged"` with `"type": "disclaimer_checkbox"`
- All other `name` values map 1:1 to `DietaryProfile` model fields
  (verify by cross-referencing the field list from DBeaver query in §4.2 Query 5)

### 8.2 Auth required

Without an auth header, the endpoint must return `401`:

```bash
curl -s http://localhost:8000/api/v1/profiles/onboarding/questions | python3 -m json.tool
```

**Expected:** `401 Unauthorized`

```json
{
  "status": "error",
  "message": "Authentication credentials were not provided.",
  "error": {
    "code": "NOT_AUTHENTICATED",
    "details": {}
  }
}
```

---

## Appendix — Full happy-path curl sequence

Copy-paste this entire block to run the complete flow end-to-end from a fresh state:

```bash
BASE="http://localhost:8000"
AUTH="Authorization: Bearer dev-bypass-token-do-not-ship"

echo "=== 1. healthz ===" && \
curl -s $BASE/healthz | python3 -m json.tool

echo "=== 2. register ===" && \
curl -s -X POST $BASE/api/v1/auth/register \
  -H "$AUTH" -H "Content-Type: application/json" -d '{}' | python3 -m json.tool

echo "=== 3. auth/me ===" && \
curl -s $BASE/api/v1/auth/me -H "$AUTH" | python3 -m json.tool

echo "=== 3b. onboarding/questions ===" && \
curl -s $BASE/api/v1/profiles/onboarding/questions -H "$AUTH" | python3 -m json.tool

echo "=== 4. profiles/me before onboarding ===" && \
curl -s $BASE/api/v1/profiles/me -H "$AUTH" | python3 -m json.tool

echo "=== 5. onboarding ===" && \
curl -s -X POST $BASE/api/v1/profiles/onboarding \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "date_of_birth": "1998-01-15", "sex": "male",
    "height_cm": 175, "weight_kg": "72.0",
    "activity_level": "moderate", "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": ["punjabi"],
    "spice_tolerance": "medium", "diet_pattern": "vegetarian",
    "no_onion_garlic": false, "allergies": ["peanuts"],
    "dislikes": ["mushroom", "bitter gourd"],
    "daily_food_budget_inr": "200.00",
    "household_size": 2, "cooking_frequency": "daily",
    "max_prep_time_min": 30, "skill_level": "intermediate",
    "disclaimer_acknowledged": true
  }' | python3 -m json.tool

echo "=== 6. profiles/me (has_profile check) ===" && \
curl -s $BASE/api/v1/auth/me -H "$AUTH" | python3 -m json.tool

echo "=== 7. patch weight=68 ===" && \
curl -s -X PATCH $BASE/api/v1/profiles/me \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"weight_kg": "68.0"}' | python3 -m json.tool

echo "=== 8. patch goal=lose_weight ===" && \
curl -s -X PATCH $BASE/api/v1/profiles/me \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"goal": "lose_weight"}' | python3 -m json.tool

echo "=== 9. patch diet_pattern=jain ===" && \
curl -s -X PATCH $BASE/api/v1/profiles/me \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"diet_pattern": "jain"}' | python3 -m json.tool

echo "=== 10. patch goal=eat_healthier ===" && \
curl -s -X PATCH $BASE/api/v1/profiles/me \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"goal": "eat_healthier"}' | python3 -m json.tool
```

---

## Section 7 — Real Firebase end-to-end test

This section verifies the actual Firebase token verification path (not the dev bypass). It requires
a Firebase project with a test user. Run this after Sections 2–6 are fully green.

### 7.1 One-time setup

The following steps must be performed in the Firebase console. You only need to do this once per
project.

**Step 1 — Get the Web API Key.**

Go to the [Firebase console](https://console.firebase.google.com) → your project → ⚙️ Project
Settings → **General** tab → scroll to **Your apps**. If no web app is registered, click the `</>`
(Web) icon and register one (a name like `nutriplan-dev-web` is fine; no Hosting needed).

Copy the **Web API Key** (looks like `AIzaSy...`). This is different from the Admin SDK service
account JSON — the Web API Key is a public client-side credential, safe to use in curl requests
and Postman. It does **not** grant admin access to your project.

**Step 2 — Create a test user in Firebase Auth.**

Firebase console → **Build → Authentication → Users** tab → **Add user**:
- Email: `testuser@nutriplan.test`
- Password: choose any password (e.g., `TestPass123!`)

Click **Add user**. The user now exists in Firebase Auth.

> Firebase Auth is the identity provider only. The Django backend creates its own `accounts_user`
> row on first token verification — the two are linked by `firebase_uid`.

---

### 7.2 Two-step token flow

The Firebase client SDK (used by Flutter) normally handles this transparently. For manual testing
we replicate it with a direct REST call.

**Step 1 — Exchange email+password for an ID token.**

```bash
curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=YOUR_WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "testuser@nutriplan.test",
    "password": "YOUR_TEST_PASSWORD",
    "returnSecureToken": true
  }' | python3 -m json.tool
```

Successful response (truncated):
```json
{
  "kind": "identitytoolkit#VerifyPasswordResponse",
  "localId": "someFirebaseUid123",
  "email": "testuser@nutriplan.test",
  "idToken": "eyJhbGci...very long string...",
  "refreshToken": "...",
  "expiresIn": "3600"
}
```

Copy the `idToken` value. It is ~1000 characters long and expires in 1 hour.

**Step 2 — Use the ID token against the Django backend.**

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Authorization: Bearer eyJhbGci...paste_full_idToken_here..." \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

The backend calls `firebase_admin.auth.verify_id_token()` against Firebase's servers, gets back the
decoded token (including `uid`), and creates or retrieves the Django `User`.

**Postman — auto-extract token into a collection variable.**

Create a request in your Postman collection:
- **Method:** `POST`
- **URL:** `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={{web_api_key}}`
- **Body (raw JSON):**
  ```json
  {
    "email": "testuser@nutriplan.test",
    "password": "YOUR_TEST_PASSWORD",
    "returnSecureToken": true
  }
  ```
- **Tests tab** — add this script to auto-save the token after each sign-in:
  ```javascript
  const json = pm.response.json();
  if (json.idToken) {
      pm.collectionVariables.set("firebase_id_token", json.idToken);
      console.log("firebase_id_token saved ✓");
  }
  ```

Then in every subsequent request, set the `Authorization` header to:
```
Bearer {{firebase_id_token}}
```

Hit the sign-in request once, and all other requests in the collection pick up the token
automatically. When the token expires (1 hour), just hit the sign-in request again.

---

### 7.3 Test sequence with real Firebase token

Run this subset against a running `make run` server. The dev bypass does **not** need to be enabled.

| Step | Request | Expected |
|---|---|---|
| 1 | `POST /api/v1/auth/register` with real token | `200`, `firebase_uid` matches Firebase `localId`, `created: true` |
| 2 | `GET /api/v1/auth/me` | `200`, same `firebase_uid`, `has_profile: false` |
| 3 | `POST /api/v1/profiles/onboarding` (full payload from §2.5) | `200`, computed targets present |
| 4 | `GET /api/v1/profiles/me` | `200`, full profile |

**DBeaver check — two users now exist:**
```sql
SELECT id, firebase_uid, email, created_at
FROM accounts_user
ORDER BY created_at;
```

Expected: 2 rows — one with `firebase_uid = 'dev-bypass-uid-001'` (from Section 2), and one with
the real Firebase UID (a string like `someFirebaseUid123`).

---

### 7.4 Token expiry

ID tokens expire after **1 hour**. After expiry, requests return:

```json
{"error": {"code": "TOKEN_EXPIRED", "message": "Firebase token has expired.", "details": {}}}
```

Fix: rerun the sign-in curl command to get a fresh token. In Postman, just hit the sign-in request
again — the Tests tab script refreshes `{{firebase_id_token}}` automatically.

---

### 7.5 Common failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| `"error": {"message": "API_KEY_INVALID"}` from Firebase | Wrong Web API Key in the sign-in URL | Get the key from Firebase console → Project Settings → General (not from Admin SDK JSON) |
| `"error": {"message": "EMAIL_NOT_FOUND"}` | Test user not created in Firebase Auth | Add via Firebase console → Authentication → Users → Add user |
| `"error": {"message": "INVALID_PASSWORD"}` | Password mismatch | Use the exact password set when creating the test user in the Firebase console |
| `401 TOKEN_EXPIRED` from Django | ID token is older than 1 hour | Re-run the sign-in request to get a fresh token |
| `401 INVALID_TOKEN` from Django with a brand-new token | Admin SDK can't verify the token | Check `FIREBASE_CREDENTIALS_PATH` in `.env` points to the correct service account JSON. Restart after fixing. |
| `401 INVALID_TOKEN` after moving the JSON file | File path changed | Update `FIREBASE_CREDENTIALS_PATH` in `.env`, restart `make run` |
| Token verifies fine locally but fails in CI | Firebase project ID mismatch | The service account JSON and the token must come from the **same Firebase project**. Confirm `project_id` in the JSON matches the project where the test user was created. |

---

### 7.6 Cleanup after Section 7

The real Firebase test creates a second user row in the Django DB. To remove it after testing:

```sql
-- Remove profile if you ran onboarding with the real token
DELETE FROM profiles_dietaryprofile
WHERE user_id IN (
    SELECT id FROM accounts_user
    WHERE firebase_uid != 'dev-bypass-uid-001'
);

-- Remove the real Firebase user row
DELETE FROM accounts_user
WHERE firebase_uid != 'dev-bypass-uid-001';
```

> **Note:** This deletes ALL non-bypass users. If you have other users in the DB (e.g., from
> previous test runs), adjust the `WHERE` clause to target the specific `firebase_uid` instead.

The Firebase test user in the Firebase console persists after you delete the Django row. Delete it
from Firebase console → Authentication → Users → hover the row → delete icon, if you want a clean
slate in Firebase too.
