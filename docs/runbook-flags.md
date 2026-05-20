
### 2.7 PATCH /api/v1/profiles/me — change weight

**Auth required.**

**Request body:**
```json
{"weight_kg": "68.0"}
```

**Expected:** `200 OK`, `target_calories` drops from `2602` → `2540` (lighter person burns slightly less).

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
for all requests
  output:
  {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Disclaimer must be acknowledged to submit a profile.",
        "details": {}
    }
} [2026-05-19 18:09:01,517] WARNING django.request Bad Request: /api/v1/profiles/me
[2026-05-19 18:09:01,517] WARNING django.server "PATCH /api/v1/profiles/me HTTP/1.1" 400 115
[2026-05-19 18:09:13,871] DEBUG django.db.backends (0.002) SELECT "accounts_user"."id", "accounts_user"."password", "accounts_user"."last_login", "accounts_user"."is_superuser", "accounts_user"."created_at", "accounts_user"."updated_at", "accounts_user"."firebase_uid", "accounts_user"."email", "accounts_user"."display_name", "accounts_user"."is_active", "accounts_user"."is_staff" FROM "accounts_user" WHERE "accounts_user"."firebase_uid" = 'dev-bypass-uid-001' LIMIT 21; args=('dev-bypass-uid-001',); alias=default
[2026-05-19 18:09:13,876] DEBUG django.db.backends (0.002) SELECT "profiles_dietaryprofile"."id", "profiles_dietaryprofile"."created_at", "profiles_dietaryprofile"."updated_at", "profiles_dietaryprofile"."user_id", "profiles_dietaryprofile"."date_of_birth", "profiles_dietaryprofile"."sex", "profiles_dietaryprofile"."height_cm", "profiles_dietaryprofile"."weight_kg", "profiles_dietaryprofile"."activity_level", "profiles_dietaryprofile"."goal", "profiles_dietaryprofile"."primary_cuisine_region", "profiles_dietaryprofile"."secondary_cuisine_preferences", "profiles_dietaryprofile"."spice_tolerance", "profiles_dietaryprofile"."diet_pattern", "profiles_dietaryprofile"."no_onion_garlic", "profiles_dietaryprofile"."allergies", "profiles_dietaryprofile"."dislikes", "profiles_dietaryprofile"."daily_food_budget_inr", "profiles_dietaryprofile"."weekly_food_budget_inr", "profiles_dietaryprofile"."household_size", "profiles_dietaryprofile"."cooking_frequency", "profiles_dietaryprofile"."max_prep_time_min", "profiles_dietaryprofile"."skill_level", "profiles_dietaryprofile"."target_calories", "profiles_dietaryprofile"."target_protein_g", "profiles_dietaryprofile"."target_carbs_g", "profiles_dietaryprofile"."target_fat_g", "profiles_dietaryprofile"."target_fiber_g" FROM "profiles_dietaryprofile" WHERE "profiles_dietaryprofile"."user_id" = 1 LIMIT 21; args=(1,); alias=default
[2026-05-19 18:09:13,876] WARNING django.request Bad Request: /api/v1/profiles/me
[2026-05-19 18:09:13,877] WARNING django.server "PATCH /api/v1/profiles/me HTTP/1.1" 400 115
[2026-05-19 18:09:30,365] DEBUG django.db.backends (0.002) SELECT "accounts_user"."id", "accounts_user"."password", "accounts_user"."last_login", "accounts_user"."is_superuser", "accounts_user"."created_at", "accounts_user"."updated_at", "accounts_user"."firebase_uid", "accounts_user"."email", "accounts_user"."display_name", "accounts_user"."is_active", "accounts_user"."is_staff" FROM "accounts_user" WHERE "accounts_user"."firebase_uid" = 'dev-bypass-uid-001' LIMIT 21; args=('dev-bypass-uid-001',); alias=default
[2026-05-19 18:09:30,369] DEBUG django.db.backends (0.001) SELECT "profiles_dietaryprofile"."id", "profiles_dietaryprofile"."created_at", "profiles_dietaryprofile"."updated_at", "profiles_dietaryprofile"."user_id", "profiles_dietaryprofile"."date_of_birth", "profiles_dietaryprofile"."sex", "profiles_dietaryprofile"."height_cm", "profiles_dietaryprofile"."weight_kg", "profiles_dietaryprofile"."activity_level", "profiles_dietaryprofile"."goal", "profiles_dietaryprofile"."primary_cuisine_region", "profiles_dietaryprofile"."secondary_cuisine_preferences", "profiles_dietaryprofile"."spice_tolerance", "profiles_dietaryprofile"."diet_pattern", "profiles_dietaryprofile"."no_onion_garlic", "profiles_dietaryprofile"."allergies", "profiles_dietaryprofile"."dislikes", "profiles_dietaryprofile"."daily_food_budget_inr", "profiles_dietaryprofile"."weekly_food_budget_inr", "profiles_dietaryprofile"."household_size", "profiles_dietaryprofile"."cooking_frequency", "profiles_dietaryprofile"."max_prep_time_min", "profiles_dietaryprofile"."skill_level", "profiles_dietaryprofile"."target_calories", "profiles_dietaryprofile"."target_protein_g", "profiles_dietaryprofile"."target_carbs_g", "profiles_dietaryprofile"."target_fat_g", "profiles_dietaryprofile"."target_fiber_g" FROM "profiles_dietaryprofile" WHERE "profiles_dietaryprofile"."user_id" = 1 LIMIT 21; args=(1,); alias=default
[2026-05-19 18:09:30,370] WARNING django.request Bad Request: /api/v1/profiles/me
[2026-05-19 18:09:30,370] WARNING django.server "PATCH /api/v1/profiles/me HTTP/1.1" 400 115



http://localhost:8000/api/v1/profiles/onboarding
{
    "date_of_birth": "1998-01-15",
    "sex": "male",
    "height_cm": "175",
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
    "daily_food_budget_inr": "10.00",
    "household_size": 2,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "intermediate",
    "disclaimer_acknowledged": true
  }
  {
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Validation failed.",
        "details": {
            "fields": {
                "daily_food_budget_inr": [
                    "Ensure this value is greater than or equal to 50."
                ]
            }
        }
    }
}
daily budget should be atleast 150+




### 3.6 Neither budget field set

Remove both `daily_food_budget_inr` and `weekly_food_budget_inr` from the payload entirely.

**Expected:** `400`, message requires at least one budget field.
http://localhost:8000/api/v1/profiles/onboarding
{
    "date_of_birth": "1998-01-15",
    "sex": "male",
    "height_cm": "175",
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
    "household_size": 2,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "intermediate",
    "disclaimer_acknowledged": true
  }
  {
    "date_of_birth": "1998-01-15",
    "sex": "male",
    "height_cm": 175,
    "weight_kg": "72.0",
    "activity_level": "moderate",
    "goal": "maintain",
    "primary_cuisine_region": "north_indian",
    "secondary_cuisine_preferences": [
        "punjabi"
    ],
    "spice_tolerance": "medium",
    "diet_pattern": "vegetarian",
    "no_onion_garlic": false,
    "allergies": [
        "peanuts"
    ],
    "dislikes": [
        "mushroom",
        "bitter gourd"
    ],
    "daily_food_budget_inr": "100.00",
    "weekly_food_budget_inr": "700.00",
    "household_size": 2,
    "cooking_frequency": "daily",
    "max_prep_time_min": 30,
    "skill_level": "intermediate",
    "target_calories": 2602,
    "target_protein_g": "162.6",
    "target_carbs_g": "325.2",
    "target_fat_g": "72.3",
    "target_fiber_g": "36.4",
    "age": 28,
    "created_at": "2026-05-19T18:04:06.217200Z",
    "updated_at": "2026-05-20T02:46:07.295702Z"
} even after removing daily budget it was giving 200 OK