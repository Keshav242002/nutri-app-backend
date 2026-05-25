# M4 — MealPlans + Recommendation Engine: Implementation Plan

**Author:** Antigravity Agent
**Date:** 2026-05-25
**Prerequisite:** M3 + M3.5 complete (136 recipes in DB). M4 gate: ≥130 recipes ✅ (136/130). Thin cells documented in §11.

---

## 0. Module Purpose

Pure-Python recommendation engine. Generates weekly meal plans (Mon–Sun, breakfast/lunch/dinner) for a user given their `DietaryProfile`. **Deterministic, no LLM calls.** Output: persisted `MealPlan` rows, each containing 3 Recipe references (one per slot) for a single date. The engine runs in milliseconds per user. This is **Layer 2** of the spec's three-layer recipe architecture.

---

## 1. Prerequisite Gate Check (CLAUDE.md §4 M4)

- [x] M3 acceptance criteria met — committed 2026-05-24
- [x] M3.5 seed expansion complete — 43 recipes added, total 136
- [x] ≥130 recipes seeded — **PASSED** (136 ≥ 130). Gate lowered from ≥200 per user decision; thin cells documented in `test_engine_thin_cell_inventory`.
- [x] `make seed` runs cleanly
- [x] `ruff + black --check + mypy --strict` all pass

> [!NOTE]
> **Recipe gate lowered to ≥130** (was ≥200). 136 recipes cover veg/vegan/eggetarian/non-veg across all 3 meal types. Known-thin cells are documented as a hardcoded constant in `test_engine_thin_cell_inventory` and logged at INFO for ops visibility. M7 AI fallback will fill gaps for impossible profile combos.

---

## 2. Model Architecture Decision

### Option A: MealPlan with 3 FKs per Row (one row = one day)

```
MealPlan
├── user FK
├── plan_date (DateField, indexed)
├── breakfast FK → Recipe (nullable, SET_NULL)
├── lunch FK → Recipe (nullable, SET_NULL)
├── dinner FK → Recipe (nullable, SET_NULL)
├── generated_by: CharField (rules | ai)
├── generated_at: DateTimeField
├── regeneration_count: JSONField ({"breakfast": 0, "lunch": 0, "dinner": 0})
└── unique_together: (user, plan_date)
```

**Pros:**
- Spec explicitly defines this structure: `MealPlan: user FK, plan_date, breakfast/lunch/dinner FKs` (PROJECT_SPEC M4_mealplans.model)
- One row per day = clean `SELECT` for "today's plan" — single query, no joins
- Regenerating a slot is `UPDATE meal_plans SET breakfast_id=? WHERE ...` — single-row update
- `regeneration_count` as JSONField per spec: `{"breakfast": 1, "lunch": 0, "dinner": 2}`
- Week view = 7 rows with 3 Recipe FKs each — simple queryset
- Index on `(user, -plan_date)` gives fast lookups

**Cons:**
- 3 FKs per row is slightly denormalized (vs. one FK + slot enum)
- Adding "snack" slot in the future requires a migration (not just a new row)
- Can't easily have 2 recipes per slot (irrelevant for v1)

### Option B: MealPlanItem (one row = one slot)

```
MealPlanItem
├── user FK
├── plan_date DateField
├── slot: CharField (breakfast | lunch | dinner)
├── recipe FK → Recipe
├── unique_together: (user, plan_date, slot)
```

**Pros:**
- Maximum flexibility: adding slots = no migration, just new enum values
- Each row is independently regenerable
- Normalized: one recipe FK per row

**Cons:**
- "Get today's plan" requires 3 rows + aggregation or annotation
- Regeneration count needs a separate field or a parent `MealPlan` model anyway
- 3× more rows in the table long-term
- Doesn't match spec's model definition

### ✅ Recommendation: Option A (MealPlan with 3 FKs)

**Rationale:** This matches the spec exactly. The 3-slot structure is locked for v1 (breakfast/lunch/dinner). Option B adds complexity for flexibility we won't use. The `regeneration_count` JSONField is specifically called out in the spec's M4 model definition.

---

## 3. Model Definition

### `MealPlan` (inherits `TimestampedModel`)

| Field | Type | Constraints | Index | Notes |
|-------|------|-------------|-------|-------|
| `id` | `AutoField` (PK) | — | PK | — |
| `user` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name="meal_plans")` | not null | B-tree (FK) | — |
| `plan_date` | `DateField` | not null | B-tree | — |
| `breakfast` | `ForeignKey(Recipe, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | — | B-tree (FK) | `SET_NULL` per spec: recipe deletion doesn't delete plan |
| `lunch` | `ForeignKey(Recipe, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | — | B-tree (FK) | — |
| `dinner` | `ForeignKey(Recipe, null=True, blank=True, on_delete=SET_NULL, related_name="+")` | — | B-tree (FK) | — |
| `generated_by` | `CharField(max_length=10, choices=GEN_BY_CHOICES, default="rules")` | not null | — | enum: `rules`, `ai` |
| `generated_at` | `DateTimeField(auto_now_add=True)` | not null | — | — |
| `regeneration_count` | `JSONField(default=dict)` | not null | — | Schema: `{"breakfast": 0, "lunch": 0, "dinner": 0}` — tracks per-slot regenerations, capped at 3 per slot per week |
| `full_plan_regenerations` | `PositiveSmallIntegerField(default=0)` | not null | — | Count of full-plan regenerations for this date. Capped at 3 per week (enforced by querying `MealPlan.objects.filter(user=user, plan_date__range=week_range, full_plan_regenerations__gt=0).count()`) |
| `created_at` | via `TimestampedModel` | — | — | — |
| `updated_at` | via `TimestampedModel` | — | — | — |

**Constraints:**
- `unique_together = [("user", "plan_date")]`

**Indexes:**
- `(user, -plan_date)` — composite index for fast "most recent plan" lookups
- FK indexes auto-created for `breakfast`, `lunch`, `dinner`

**`on_delete` justification:**
- `user → CASCADE`: deleting user removes all their plans
- `breakfast/lunch/dinner → SET_NULL`: deleting a recipe nulls the slot (plan stays, slot shown as "recipe unavailable" in UI)

**`__str__`:** `f"MealPlan({self.user_id}, {self.plan_date})"`

**Choice constants:**

```python
GEN_BY_RULES = "rules"
GEN_BY_AI = "ai"

GEN_BY_CHOICES = [
    (GEN_BY_RULES, "Rules"),
    (GEN_BY_AI, "AI"),
]

SLOT_BREAKFAST = "breakfast"
SLOT_LUNCH = "lunch"
SLOT_DINNER = "dinner"

SLOT_CHOICES = [
    (SLOT_BREAKFAST, "Breakfast"),
    (SLOT_LUNCH, "Lunch"),
    (SLOT_DINNER, "Dinner"),
]
```

---

## 4. Engine Algorithm

### Location: `apps/mealplans/services/engine.py`

### Constants

```python
SLOT_CALORIE_RATIO: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.40,
    "dinner": 0.35,
}

SLOT_BUDGET_RATIO: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.40,
    "dinner": 0.35,
}

VARIETY_LOOKBACK_DAYS: int = 7
CANDIDATE_POOL_CAP: int = 200

# --- Scoring weights ---
SCORE_CUISINE_MATCH: int = 30
SCORE_MACRO_MATCH_MULTIPLIER: int = 20
SCORE_RECENT_PENALTY: int = -50
SCORE_RANDOM_TIEBREAKER_MAX: int = 5
SCORE_BUDGET_FIT_BASE: int = 25
SCORE_FIBER_BOOST: int = 15
SCORE_BATCH_COOKABLE_BOOST: int = 10
SCORE_QUICK_RECIPE_BOOST: int = 15

# --- Budget thresholds ---
BUDGET_STRICT_GRACE: float = 1.15   # 15% grace
BUDGET_RELAXED_GRACE: float = 1.40  # 40% fallback

# --- Calorie window ---
CALORIE_WINDOW_LOW: float = 0.75   # slot_target × 0.75
CALORIE_WINDOW_HIGH: float = 1.25  # slot_target × 1.25

# --- Diet hierarchy ---
# Profile diet_pattern → which recipe diet_tags are acceptable
DIET_HIERARCHY: dict[str, list[str]] = {
    "vegan": ["vegan"],
    "vegetarian": ["vegetarian", "vegan"],
    "eggetarian": ["eggetarian", "vegetarian", "vegan"],
    "pescatarian": ["pescatarian", "vegetarian", "vegan"],
    "non_vegetarian": [],  # no diet_tag filter — all recipes OK
    "jain": ["jain", "vegetarian", "vegan"],  # deferred but defined
}
```

### `select_recipe(profile, slot, plan_date, exclude_recipe_ids=None, rng=None) → Recipe`

Pure-ish function. Takes a `DietaryProfile`, a slot string, a date, optional exclusion list, and an optional `random.Random` instance (for test determinism).

**Pipeline (10 steps):**

#### Step 1: HARD FILTER — Base Pool
```python
pool = Recipe.objects.filter(
    meal_type=slot,
    is_active=True,
    prep_time_min__lte=profile.max_prep_time_min,
)
```

#### Step 2: DIET FILTER
```python
allowed_tags = DIET_HIERARCHY.get(profile.diet_pattern, [])
if allowed_tags:
    # Recipe must have AT LEAST ONE of the allowed diet_tags
    pool = pool.filter(diet_tags__overlap=allowed_tags)
else:
    # non_vegetarian: no filter — all recipes are acceptable
    pass
```

**Diet hierarchy handling:**
- `vegan` profile → recipe must have `"vegan"` in `diet_tags`
- `vegetarian` profile → recipe must have `"vegetarian"` OR `"vegan"` in `diet_tags` (vegan ⊂ vegetarian)
- `eggetarian` profile → recipe must have `"eggetarian"` OR `"vegetarian"` OR `"vegan"` in `diet_tags`
- `non_vegetarian` profile → no `diet_tags` filter at all (every recipe is fair game, including veg/vegan)
- `jain` profile → recipe must have `"jain"` OR `"vegetarian"` OR `"vegan"` — further constraint: exclude recipes using `no_onion_garlic` ingredients if `profile.no_onion_garlic=True` (defer detailed implementation to v2)

#### Step 3: ALLERGEN EXCLUSION
```python
if profile.allergies:
    pool = pool.exclude(allergen_tags__overlap=profile.allergies)
```

#### Step 4: CALORIE WINDOW
```python
slot_target = int(profile.target_calories * SLOT_CALORIE_RATIO[slot])
cal_low = int(slot_target * CALORIE_WINDOW_LOW)
cal_high = int(slot_target * CALORIE_WINDOW_HIGH)
pool = pool.filter(
    cached_calories_per_serving__gte=cal_low,
    cached_calories_per_serving__lte=cal_high,
)
```

Uses the denormalized B-tree indexed `cached_calories_per_serving` column — no JSON extraction needed.

#### Step 5: BUDGET FILTER (if profile.daily_food_budget_inr set)
```python
if profile.daily_food_budget_inr:
    slot_budget = float(profile.daily_food_budget_inr) * SLOT_BUDGET_RATIO[slot]
    strict_limit = slot_budget * BUDGET_STRICT_GRACE  # 1.15×
    
    # Strict filter: cost_known=True AND cost_per_serving ≤ strict_limit
    # IMPORTANT: Use ExpressionWrapper with explicit DecimalField to avoid
    # silent precision loss (same fix as M3 filters.py applied).
    budget_pool = pool.filter(cost_known=True).annotate(
        cost_per_serving=ExpressionWrapper(
            F("cached_cost_inr") / F("servings"),
            output_field=DecimalField(max_digits=7, decimal_places=2),
        )
    ).filter(cost_per_serving__lte=strict_limit)
    
    if budget_pool.exists():
        pool = budget_pool
    else:
        # Fallback: relax to 1.40× AND include cost_known=False recipes
        log.info(event="budget_too_tight", slot=slot, strict_limit=strict_limit)
        relaxed_limit = slot_budget * BUDGET_RELAXED_GRACE
        # Re-annotate with same ExpressionWrapper for relaxed pool
        pool = pool.annotate(
            cost_per_serving=ExpressionWrapper(
                F("cached_cost_inr") / F("servings"),
                output_field=DecimalField(max_digits=7, decimal_places=2),
            )
        ).filter(
            Q(cost_known=False) |
            Q(cost_known=True, cost_per_serving__lte=relaxed_limit)
        )
```

#### Step 6: EXCLUSION (explicit exclude_recipe_ids)
```python
if exclude_recipe_ids:
    pool = pool.exclude(id__in=exclude_recipe_ids)
```

#### Step 7: VARIETY LOOKUP
```python
recent_recipe_ids = _get_recent_recipe_ids(
    user=profile.user, slot=slot, days=VARIETY_LOOKBACK_DAYS, plan_date=plan_date
)
# Don't hard-exclude (pool might be too small), but penalize in scoring
```

#### Step 8: PROTEIN VARIETY (non-veg only, same slot scope)

**Resolved (Q1):** Protein rotation applies within the **same slot only** — no chicken lunch 2 days in a row is penalized, but chicken lunch + chicken dinner on the same day is fine. Cross-slot rotation is too aggressive and would thin the pool unnecessarily.

```python
if profile.diet_pattern == "non_vegetarian":
    yesterday_protein = _get_yesterday_protein_source(
        user=profile.user, slot=slot, plan_date=plan_date  # same slot only
    )
    # Don't hard-exclude, but penalize same protein_source in scoring (step 9)
```

#### Step 9: SCORE remaining candidates

Cap pool at `CANDIDATE_POOL_CAP` (200) for performance — `.order_by("?")[:200]` if pool larger (random 200 subset).

For each candidate recipe:

```python
score = 0.0

# Cuisine match: +30 if recipe.cuisine in user's cuisine preferences
cuisine_prefs = _get_cuisine_preferences(profile)
if recipe.cuisine in cuisine_prefs:
    score += SCORE_CUISINE_MATCH  # +30

# Macro match: +20 × match_score (0.0 to 1.0)
slot_macros = _compute_slot_macro_targets(profile, slot)
macro_score = _compute_macro_match(recipe, slot_macros)
score += SCORE_MACRO_MATCH_MULTIPLIER * macro_score  # +0 to +20

# Variety penalty: -50 if used in last 7 days
if recipe.id in recent_recipe_ids:
    score += SCORE_RECENT_PENALTY  # -50

# Budget fit: +25 base, minus overshoot penalty
if profile.daily_food_budget_inr and recipe.cost_known:
    overshoot = _compute_budget_overshoot(recipe, slot_budget)
    score += SCORE_BUDGET_FIT_BASE - overshoot  # +25 max, can go negative

# Cooking frequency adjustment
if profile.cooking_frequency == "daily":
    if (recipe.prep_time_min + recipe.cook_time_min) <= 30:
        score += SCORE_QUICK_RECIPE_BOOST  # +15
elif profile.cooking_frequency in ("weekends_only", "rarely"):
    if recipe.servings >= 4:
        score += SCORE_BATCH_COOKABLE_BOOST  # +10

# eat_healthier goal: fiber boost
if profile.goal == "eat_healthier":
    nutrition = recipe.cached_nutrition or {}
    if nutrition.get("fiber_g", 0) >= 5:
        score += SCORE_FIBER_BOOST  # +15

# Protein variety penalty (non-veg only, SAME SLOT scope — Q1 resolved)
if profile.diet_pattern == "non_vegetarian" and yesterday_protein:
    if recipe.protein_source == yesterday_protein and recipe.protein_source != "none":
        score -= 25  # penalize same protein in same slot 2 days in a row

# Random tiebreaker (seeded for tests)
score += rng.uniform(0, SCORE_RANDOM_TIEBREAKER_MAX)  # 0–5
```

#### Step 10: PICK MAX SCORE
```python
if not candidates:
    raise NoSuitableRecipeError(slot=slot, plan_date=plan_date)
return max(candidates, key=lambda c: c.score)
```

### Helper Functions

```python
def _get_cuisine_preferences(profile: DietaryProfile) -> set[str]:
    """Union of primary_cuisine_region + secondary_cuisine_preferences."""

def _compute_slot_macro_targets(profile: DietaryProfile, slot: str) -> dict:
    """Compute per-slot macro targets from profile totals × slot ratio."""

def _compute_macro_match(recipe: Recipe, slot_macros: dict) -> float:
    """0.0–1.0 score: how well recipe macros match slot target macros."""

def _get_recent_recipe_ids(user, slot, days, plan_date) -> set[int]:
    """Recipe IDs used in this slot in the last N days for this user."""

def _get_yesterday_protein_source(user, slot, plan_date) -> str | None:
    """protein_source of recipe in this slot yesterday, or None."""

def _compute_budget_overshoot(recipe, slot_budget) -> float:
    """Penalty proportional to how much cost exceeds budget."""
```

### `generate_week(profile, start_date) → list[MealPlan]`

Generates 7 days (Mon–Sun or any 7-day window). Returns list of 7 MealPlan objects (not yet saved).

**Generation strategy (Q3 resolved):** M4 uses **lazy generation** — plans are created on first `GET` via `get_or_generate_plan()`. M6 will add a Celery beat wrapper (`generate_plan_for_user` task) that calls the same service function on a cron schedule (hourly, gated by user timezone). The engine is fully testable without Celery in M4.

```python
def generate_week(profile: DietaryProfile, start_date: date) -> list[dict]:
    """Generate 7 days of meal selections. Pure function, no DB writes."""
    plans = []
    for day_offset in range(7):
        plan_date = start_date + timedelta(days=day_offset)
        day_plan = {}
        for slot in ["breakfast", "lunch", "dinner"]:
            recipe = select_recipe(
                profile=profile,
                slot=slot,
                plan_date=plan_date,
                exclude_recipe_ids=None,
                rng=rng,
            )
            day_plan[slot] = recipe
        plans.append({"plan_date": plan_date, **day_plan})
    return plans
```

### `NoSuitableRecipeError`

```python
class NoSuitableRecipeError(Exception):
    """Raised when the engine cannot find any recipe matching constraints."""
    def __init__(self, slot: str, plan_date: date, reason: str = ""):
        self.slot = slot
        self.plan_date = plan_date
        self.reason = reason
        super().__init__(f"No suitable recipe for {slot} on {plan_date}: {reason}")
```

---

## 5. Services

### `apps/mealplans/services/engine.py`

Core functions (described in §4):
- `select_recipe(profile, slot, plan_date, exclude_recipe_ids, rng) → Recipe`
- `generate_week(profile, start_date) → list[dict]`
- `NoSuitableRecipeError`
- All helper functions (`_get_cuisine_preferences`, `_compute_macro_match`, etc.)

### `apps/mealplans/services/plan_service.py`

```python
def get_or_generate_plan(user: User, plan_date: date) -> MealPlan:
    """Return existing MealPlan or generate and save a new one."""
    try:
        return MealPlan.objects.select_related(
            "breakfast", "lunch", "dinner"
        ).get(user=user, plan_date=plan_date)
    except MealPlan.DoesNotExist:
        profile = user.profile  # raises if no profile
        breakfast = select_recipe(profile, "breakfast", plan_date)
        lunch = select_recipe(profile, "lunch", plan_date)
        dinner = select_recipe(profile, "dinner", plan_date)
        plan = MealPlan(
            user=user,
            plan_date=plan_date,
            breakfast=breakfast,
            lunch=lunch,
            dinner=dinner,
            generated_by="rules",
            regeneration_count={"breakfast": 0, "lunch": 0, "dinner": 0},
        )
        plan.full_clean()
        plan.save()
        return plan


def regenerate_slot(user: User, plan_date: date, slot: str) -> MealPlan:
    """Swap one slot in a MealPlan. Rate limited to 3 per slot per week."""
    plan = MealPlan.objects.get(user=user, plan_date=plan_date)
    regen_count = plan.regeneration_count.get(slot, 0)
    if regen_count >= 3:
        raise RateLimitError(code=REGENERATE_LIMIT)
    
    current_recipe_id = getattr(plan, slot + "_id")
    exclude_ids = [current_recipe_id] if current_recipe_id else []
    
    profile = user.profile
    new_recipe = select_recipe(
        profile=profile,
        slot=slot,
        plan_date=plan_date,
        exclude_recipe_ids=exclude_ids,
    )
    
    setattr(plan, slot, new_recipe)
    plan.regeneration_count[slot] = regen_count + 1
    plan.save(update_fields=[slot, "regeneration_count", "updated_at"])
    return plan


def regenerate_plan(user: User, plan_date: date) -> MealPlan:
    """Full plan regeneration. Rate limited to 3 per week."""
    # Q4 resolved: count full regenerations in the current week
    week_start = plan_date - timedelta(days=plan_date.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday
    week_regen_count = MealPlan.objects.filter(
        user=user,
        plan_date__range=(week_start, week_end),
        full_plan_regenerations__gt=0,
    ).aggregate(total=Sum("full_plan_regenerations"))["total"] or 0
    
    if week_regen_count >= 3:
        raise RateLimitError(code=REGENERATE_LIMIT)
    
    existing = MealPlan.objects.filter(user=user, plan_date=plan_date).first()
    if existing:
        existing.delete()
    
    plan = get_or_generate_plan(user, plan_date)
    plan.full_plan_regenerations = (existing.full_plan_regenerations + 1) if existing else 1
    plan.save(update_fields=["full_plan_regenerations", "updated_at"])
    return plan
```

---

## 6. Serializers

### `MealPlanRecipeSlimSerializer`

Slim recipe representation for non-today days:

```python
class MealPlanRecipeSlimSerializer(ModelSerializer):
    class Meta:
        model = Recipe
        fields = ["id", "name", "slug", "meal_type", "cuisine",
                  "prep_time_min", "cached_calories_per_serving",
                  "image_url", "protein_source"]
```

### `MealPlanRecipeDetailSerializer`

Full recipe detail for today (reuse `RecipeListSerializer` from M3):

```python
# Reuse apps.recipes.serializers.RecipeListSerializer
```

### `MealPlanSerializer`

```python
class MealPlanSerializer(ModelSerializer):
    breakfast = MealPlanRecipeSlimSerializer(read_only=True)
    lunch = MealPlanRecipeSlimSerializer(read_only=True)
    dinner = MealPlanRecipeSlimSerializer(read_only=True)
    
    class Meta:
        model = MealPlan
        fields = ["id", "plan_date", "breakfast", "lunch", "dinner",
                  "generated_by", "generated_at", "regeneration_count"]
```

### `MealPlanDayDetailSerializer`

For single-day detail endpoint (uses full recipe serializer):

```python
class MealPlanDayDetailSerializer(ModelSerializer):
    breakfast = RecipeListSerializer(read_only=True)
    lunch = RecipeListSerializer(read_only=True)
    dinner = RecipeListSerializer(read_only=True)
    
    class Meta:
        model = MealPlan
        fields = ["id", "plan_date", "breakfast", "lunch", "dinner",
                  "generated_by", "generated_at", "regeneration_count"]
```

### `RegenerateSlotSerializer`

```python
class RegenerateSlotSerializer(Serializer):
    date = DateField()
    slot = ChoiceField(choices=SLOT_CHOICES)
```

---

## 7. Endpoints

### `GET /api/v1/mealplans/today/`

- **Auth:** Required
- **Logic:** `get_or_generate_plan(request.user, date.today())`
- **Serializer:** `MealPlanDayDetailSerializer` (full recipe details for today's 3 meals)
- **Response:** Standard envelope `{status: "success", message: "Today's meal plan", data: {...}}`
- **Error:** 404 `PROFILE_NOT_FOUND` if user has no profile

### `GET /api/v1/mealplans/day/<date>/`

- **Auth:** Required
- **Logic:** `get_or_generate_plan(request.user, parsed_date)`
- **Serializer:** `MealPlanDayDetailSerializer`
- **Response:** Standard envelope
- **Use case:** "tomorrow's plan" for push notifications (M6)

### `GET /api/v1/mealplans/week/`

- **Auth:** Required
- **Query params:** `from` (ISO date, defaults to Monday of current week)
- **Logic:** `MealPlan.objects.filter(user=user, plan_date__range=(from_date, from_date + 6))`
- **Serializer:** `MealPlanSerializer` (slim recipe details)
- **Response:** Standard envelope with list of up to 7 MealPlan objects

### `POST /api/v1/mealplans/regenerate-slot/`

- **Auth:** Required
- **Body:** `{date: "2026-05-25", slot: "breakfast"}`
- **Logic:** `regenerate_slot(request.user, date, slot)`
- **Rate limit:** 3 per slot per week (enforced in service via `regeneration_count`)
- **Response:** Standard envelope with updated MealPlan
- **Errors:**
  - 429 `REGENERATE_LIMIT` if slot regenerated 3+ times
  - 422 `NO_SUITABLE_RECIPE` if engine can't find alternative
  - 404 `MEAL_PLAN_NOT_FOUND` if no plan exists for that date

### `POST /api/v1/mealplans/regenerate/`

- **Auth:** Required
- **Body:** `{date: "2026-05-25"}`
- **Logic:** `regenerate_plan(request.user, date)`
- **Rate limit:** 3 per week, enforced in service via `full_plan_regenerations` field (Q4 resolved). Counts all `MealPlan` rows in the same ISO week with `full_plan_regenerations > 0`, sums them, rejects at ≥3.
- **Response:** Standard envelope with new MealPlan
- **Errors:**
  - 429 `REGENERATE_LIMIT` if 3+ full regenerations this week
  - 422 `NO_SUITABLE_RECIPE` if engine can't find recipes

---

## 8. Macro Match Score Algorithm

The `_compute_macro_match(recipe, slot_macros)` function computes a 0.0–1.0 score:

```python
def _compute_macro_match(recipe: Recipe, slot_macros: dict) -> float:
    """
    Compare recipe per-serving macros against slot targets.
    Returns 0.0 (worst) to 1.0 (perfect match).
    """
    nutrition = recipe.cached_nutrition or {}
    
    # Compare protein, carbs, fat
    deviations = []
    for macro in ["protein_g", "carbs_g", "fat_g"]:
        actual = nutrition.get(macro, 0)
        target = slot_macros.get(macro, 0)
        if target > 0:
            deviation = abs(actual - target) / target
            deviations.append(min(deviation, 1.0))  # cap at 100% deviation
        else:
            deviations.append(0.0)
    
    avg_deviation = sum(deviations) / len(deviations) if deviations else 0
    return max(0.0, 1.0 - avg_deviation)
```

---

## 9. Migrations

**1 migration: `apps/mealplans/migrations/0001_initial.py`**

Creates `MealPlan` with:
- All fields per §3
- `unique_together = [("user", "plan_date")]`
- Composite index `(user, -plan_date)`
- FK indexes auto-created

No data migration needed — MealPlan starts empty.

---

## 10. Admin

```python
@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ["user", "plan_date", "breakfast", "lunch", "dinner", "generated_by"]
    list_filter = ["generated_by", "plan_date"]
    search_fields = ["user__email"]
    raw_id_fields = ["user", "breakfast", "lunch", "dinner"]
    readonly_fields = ["generated_at", "regeneration_count"]
```

---

## 11. Tests

**Target: ~55 tests, ≥80% coverage on `apps/mealplans/services/`.**

### Model tests (~6 tests)

1. `test_mealplan_str_representation`
2. `test_mealplan_unique_together_user_plan_date`
3. `test_mealplan_set_null_on_recipe_delete` — verify breakfast/lunch/dinner become NULL when recipe deleted
4. `test_mealplan_cascade_on_user_delete` — verify plans deleted when user deleted
5. `test_mealplan_regeneration_count_default`
6. `test_mealplan_full_plan_regenerations_default_zero`

### Engine tests — hard filters (~12 tests)

6. `test_engine_filters_by_meal_type` — breakfast slot only returns breakfast recipes
7. `test_engine_filters_by_is_active` — inactive recipes excluded
8. `test_engine_respects_max_prep_time` — recipes exceeding prep time excluded
9. `test_engine_excludes_allergens` — profile with `[dairy]` allergy → no dairy recipes
10. `test_engine_respects_diet_pattern_vegetarian` — only veg/vegan recipes
11. `test_engine_respects_diet_pattern_vegan` — only vegan recipes
12. `test_engine_respects_diet_pattern_eggetarian` — eggetarian + veg + vegan OK
13. `test_engine_respects_diet_pattern_nonveg` — all recipes including non-veg
14. `test_engine_respects_calorie_window` — recipes outside 75%–125% excluded
15. `test_engine_calorie_window_boundaries` — test exact boundary values
16. `test_engine_excludes_specified_recipe_ids` — exclude_recipe_ids works
17. `test_engine_raises_when_no_match` — `NoSuitableRecipeError` on impossible constraints

### Engine tests — budget (~5 tests)

18. `test_engine_respects_budget_window` — recipes over budget excluded when budget set
19. `test_engine_budget_grace_factor_1_15` — recipes within 15% grace pass
20. `test_engine_relaxes_budget_when_pool_empty` — falls back to 1.40×
21. `test_engine_budget_includes_cost_unknown_in_fallback` — `cost_known=False` recipes allowed in fallback
22. `test_engine_no_budget_filter_when_budget_not_set` — all recipes pass when no budget

### Engine tests — scoring (~10 tests)

23. `test_engine_cuisine_boost_applied` — cuisine match gets +30
24. `test_engine_macro_match_score_perfect` — recipe matching targets gets 1.0
25. `test_engine_macro_match_score_poor` — recipe far from targets gets ~0.0
26. `test_engine_variety_penalty_for_recent_recipes` — -50 for recipes used in last 7 days
27. `test_engine_protein_variety_penalty_nonveg` — same protein_source 2 days in row penalized
28. `test_engine_cooking_frequency_daily_prefers_quick` — daily cooks get boost for quick recipes
29. `test_engine_cooking_frequency_rarely_prefers_batch` — rarely/weekends_only boosts batch-cookable
30. `test_engine_eat_healthier_fiber_boost` — eat_healthier goal + high-fiber recipe gets +15
31. `test_engine_budget_scoring_prefers_cheaper` — cheaper recipe scores higher when macros equal
32. `test_engine_deterministic_with_seed` — `random.seed(0)` gives same result twice

### Engine tests — diet hierarchy (~4 tests)

33. `test_diet_hierarchy_vegan_gets_vegan_only`
34. `test_diet_hierarchy_vegetarian_gets_veg_plus_vegan`
35. `test_diet_hierarchy_eggetarian_gets_egg_veg_vegan`
36. `test_diet_hierarchy_nonveg_gets_all`

### Service tests — plan_service (~10 tests)

37. `test_get_or_generate_is_idempotent` — calling twice returns same plan
38. `test_get_or_generate_creates_all_three_slots`
39. `test_get_or_generate_requires_profile` — raises when no profile
40. `test_regenerate_slot_returns_different_recipe` — new recipe != old recipe
41. `test_regenerate_slot_increments_count` — regeneration_count incremented
42. `test_regenerate_slot_rate_limited_after_3` — raises `REGENERATE_LIMIT` on 4th attempt
43. `test_regenerate_plan_creates_fresh_plan` — full regeneration
44. `test_regenerate_plan_increments_full_plan_regenerations` — field incremented on regen
45. `test_regenerate_plan_rate_limited_after_3_per_week` — raises `REGENERATE_LIMIT` after 3 full regenerations across the ISO week
46. `test_regenerate_plan_allows_regeneration_in_new_week` — week boundary resets count

### View tests (~11 tests)

45. `test_today_endpoint_returns_200_with_plan`
46. `test_today_endpoint_requires_auth`
47. `test_today_endpoint_creates_plan_lazily`
48. `test_today_endpoint_returns_profile_not_found_without_profile`
49. `test_day_endpoint_returns_specific_date`
50. `test_week_endpoint_returns_up_to_7_plans`
51. `test_regenerate_slot_endpoint_returns_updated_plan`
52. `test_regenerate_slot_endpoint_returns_429_on_limit`
53. `test_regenerate_slot_endpoint_validates_slot_choices`
54. `test_regenerate_endpoint_full_plan`
55. `test_response_envelope_shape` — verify standard `{status, message, data}` shape
56. `test_regenerate_endpoint_returns_429_on_full_plan_limit` — full plan rate limit enforced at endpoint level

### Engine tests — thin cell inventory (~1 test)

57. `test_engine_thin_cell_inventory` — **Regression guard for recipe coverage.**
    - Iterates all `(diet_pattern × slot)` combinations with a synthetic profile (average calories ~2000, no allergies, no budget constraint)
    - Records the candidate pool size after hard filters (steps 1–4 only: meal_type, diet, allergen, calorie window)
    - Hardcodes expected thin cells as a constant, e.g.:
      ```python
      KNOWN_THIN_CELLS: dict[tuple[str, str], int] = {
          # (diet_pattern, slot): expected_min_pool_size
          # Cells with <3 candidates are "thin"
          # Update this dict when seed data changes
      }
      ```
    - Test **PASSES** if known-thin cells are present in the result (expected behavior with 136 recipes)
    - Test **FAILS** if a previously-OK cell (≥3 candidates) degrades to <3 candidates (regression)
    - Generates a report logged at INFO level:
      ```
      event=thin_cell_inventory, total_cells=18, thin_cells=N,
      details=[{diet_pattern: "...", slot: "...", pool_size: N}, ...]
      ```
    - Uses `random.seed(0)` for determinism

**Total: ~57 tests**

---

## 12. Resolved Decisions (formerly open questions)

All 5 questions resolved by user on 2026-05-25:

### Q1: Protein source rotation scope — **RESOLVED: Same slot only**

Protein rotation penalty (-25 score) applies within the **same slot only**. Example: chicken lunch two days in a row is penalized, but chicken lunch + chicken dinner on the same day is fine. Cross-slot rotation would thin the pool unnecessarily. Documented in Step 8 and Step 9 scoring of the engine algorithm (§4).

### Q2: Slot lock mechanism — **RESOLVED: Defer to v2**

No lock mechanism in M4. Added to `future_addons_backlog` in PROJECT_SPEC.json: "Meal plan slot locking — user marks a slot 'I want this recipe' and regeneration preserves it; deferred from M4 to post-v1."

### Q3: Pre-compute vs lazy generation — **RESOLVED: Lazy in M4, Celery in M6**

M4 uses lazy generation via `get_or_generate_plan()` on first GET. M6 will add a Celery beat wrapper (`generate_plan_for_user` task) that calls the same service function on a cron schedule. The engine is fully testable without Celery in M4.

### Q4: Rate limits — **RESOLVED: Two separate counters**

1. **Slot regeneration:** `regeneration_count` JSONField `{"breakfast": N, "lunch": N, "dinner": N}`, capped at 3 per slot per week.
2. **Full plan regeneration:** `full_plan_regenerations` PositiveSmallIntegerField on MealPlan, capped at 3 per week. Week count derived by querying `MealPlan.objects.filter(user=user, plan_date__range=week_range, full_plan_regenerations__gt=0).aggregate(Sum("full_plan_regenerations"))`. `django-ratelimit` hardening is M8 territory.

### Q5: Recipe count gate — **RESOLVED: Lowered to ≥130, thin cells documented**

CLAUDE.md §4 M4 prerequisite changed from "≥200 recipes" to "≥130 recipes, thin cells documented in test_engine_thin_cell_inventory". Current 136 recipes cover veg/vegan/eggetarian/non-veg across all 3 meal types. The `test_engine_thin_cell_inventory` test (§11) iterates all `(diet_pattern × slot)` combinations, records pool sizes, and fails on regression if previously-OK cells degrade below 3 candidates.

---

## 13. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Pool too small for niche combos (jain×weight_loss×dinner) | Medium | `NoSuitableRecipeError` raised cleanly; M7 AI fallback hooks here; test coverage documents thin cells |
| Budget filter empties pool aggressively | Medium | Two-stage filter (1.15× strict → 1.40× relaxed with `cost_known=False` included); logging at INFO for `budget_too_tight` |
| Macro match scoring produces unintuitive results | Low | Scoring is additive with clear weights; deterministic with `random.seed(0)` for tests; easy to tune weights post-launch |
| `regeneration_count` JSONField mutation not saved | Medium | Explicit `save(update_fields=["regeneration_count", ...])` after mutation; test verifies increment persists |
| Race condition: two requests generate same day's plan simultaneously | Low | `unique_together` constraint causes `IntegrityError` on second insert; catch and return existing plan |
| Recipe deletion nulls meal plan slot mid-day | Low | `SET_NULL` preserves plan; UI shows "recipe unavailable, regenerate?"; tested |

---

## 14. Files to Create/Modify

### New files

| File | Purpose |
|------|---------|
| `apps/mealplans/__init__.py` | App init |
| `apps/mealplans/apps.py` | AppConfig with `name="apps.mealplans"` |
| `apps/mealplans/models.py` | MealPlan model |
| `apps/mealplans/admin.py` | Admin registration |
| `apps/mealplans/serializers.py` | 4 serializers |
| `apps/mealplans/views.py` | 5 view classes |
| `apps/mealplans/urls.py` | URL patterns |
| `apps/mealplans/services/__init__.py` | Services init |
| `apps/mealplans/services/engine.py` | Recommendation engine |
| `apps/mealplans/services/plan_service.py` | Plan CRUD service |
| `apps/mealplans/tests/__init__.py` | Tests init |
| `apps/mealplans/tests/factories.py` | MealPlan factory |
| `apps/mealplans/tests/test_models.py` | Model tests |
| `apps/mealplans/tests/test_services.py` | Engine + plan_service tests |
| `apps/mealplans/tests/test_views.py` | Endpoint tests |
| `apps/mealplans/migrations/0001_initial.py` | Initial migration |

### Modified files

| File | Change |
|------|--------|
| `nutriplan/api_router.py` | Add `include("apps.mealplans.urls")` |
| `nutriplan/settings/base.py` | Add `"apps.mealplans"` to `LOCAL_APPS` |
| `core/error_codes.py` | Already has `NO_SUITABLE_RECIPE`, `REGENERATE_LIMIT`, `MEAL_PLAN_NOT_FOUND` — no change needed |
| `CLAUDE.md` §3, §13 | Update active module, conventions |
| `docs/PROGRESS.md` | Append M4 entry |
| `docs/RUNBOOK.md` | Add any new commands |

---

## 15. Estimated Build Order

```
 1. models        → apps/mealplans/models.py (MealPlan + choice constants)
 2. migration     → apps/mealplans/migrations/0001_initial.py
 3. admin         → apps/mealplans/admin.py
 4. engine        → apps/mealplans/services/engine.py (select_recipe, generate_week, helpers)
 5. plan_service  → apps/mealplans/services/plan_service.py (get_or_generate, regenerate_slot/plan)
 6. serializers   → apps/mealplans/serializers.py
 7. views         → apps/mealplans/views.py
 8. urls          → apps/mealplans/urls.py + nutriplan/api_router.py + settings
 9. factories     → apps/mealplans/tests/factories.py
10. tests         → test_models.py, test_services.py, test_views.py
11. run           → make test
12. fix           → iterate until all pass
13. lint          → make lint (ruff + black + mypy)
14. context       → update CLAUDE.md §3/§13, PROGRESS.md, RUNBOOK.md
15. commit        → feat(M4): mealplans — recommendation engine + plan API
```

---

## 16. Estimated Size

| Category | Estimated LOC |
|----------|--------------|
| Models + choices | ~90 |
| Engine service | ~280 |
| Plan service | ~110 |
| Serializers | ~60 |
| Views | ~100 |
| URLs | ~15 |
| Admin | ~15 |
| Factories | ~30 |
| Tests | ~780 |
| **Total** | **~1,480** |

**Test count:** ~57 tests
**Coverage target:** ≥80% on `apps/mealplans/services/`
