# M7 — Chat + AI Integration (Provider-Agnostic LLM Layer)

GPT-4o / Gemini / OpenRouter-powered chatbot with two modes (free chat + ingredient-to-recipe), USDA macro validation, AI-generated recipe promotion into the curated library, and engine fallback for `NoSuitableRecipeError`. Provider-agnostic: switch between 4 LLM backends by changing a single env var.

**Reference implementation files:** `docs/files/llm_config.py`, `docs/files/llm_client.py`, `docs/files/SETTINGS_AND_ENV.py` — Claude Code should adapt these to match our actual `core/exceptions.py` and `core/error_codes.py`.

---

## Prerequisites & Requirements

> [!IMPORTANT]
> **At least one LLM key must be set before M7 code can be tested.** The cheapest path is a free OpenRouter key or a free Google AI Studio key. No paid API required.

### ① LLM Provider Key (one of the following)

| Provider | Key env var | Where to get it | Cost |
|----------|------------|-----------------|------|
| **OpenRouter** (default) | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | Free models available (`:free` suffix) |
| OpenAI | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Paid (~$0.01–$0.05/chat) |
| Gemini (OpenAI-compat) | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Free tier available |
| Gemini (native SDK) | `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Free tier available |

**Recommended dev setup (zero cost):** `AI_PROVIDER=openrouter` with `OPENROUTER_MODEL=openrouter/free`, OR `AI_PROVIDER=gemini_openai` with a free Google AI Studio key.

### ② USDA FoodData Central API Key
- **What:** Free API key from [fdc.nal.usda.gov](https://fdc.nal.usda.gov/api-key-signup.html)
- **Cost:** Free. Rate limit 1,000 requests/hour per key. No credit card.
- **Steps:** Fill the form → key arrives by email in minutes → paste into `.env` as `USDA_API_KEY`

### ③ Cost Awareness
- If using OpenAI (paid), user must acknowledge costs — GPT-4o ≈ $2.50/1M input tokens, $10/1M output tokens. Recommend $20/month hard limit.
- Free providers (OpenRouter `:free` models, Gemini free tier) have no cost but may have rate limits and lower quality.
- Token usage logged to structured logs for all providers.

### Pre-existing Prerequisites (already met)
- [x] M6 acceptance criteria met — 376 tests, 95% coverage
- [x] Redis 7 running (needed for USDA response caching)
- [x] `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TIMEOUT_SECONDS` already declared in `settings/base.py` (will be kept + new vars added)
- [x] `USDA_API_KEY`, `USDA_BASE_URL` already declared in `settings/base.py`
- [x] Error codes `OPENAI_FAILURE`, `USDA_FAILURE`, `RATE_LIMITED` already in `core/error_codes.py`
- [x] `CHAT_RATE_LIMIT` setting already in `settings/base.py` (default `30/h`)
- [x] `ASGI_APPLICATION` already set in `settings/base.py`
- [x] `make run-asgi` target already in Makefile

---

## Resolved Decisions

> [!NOTE]
> **Q1 — Rate limiting: CONFIRMED.**
> Service-layer rate limiting in M7: count `ChatMessage` rows (role=`user`) in last hour per user. Raise `RateLimitError` if count ≥ `CHAT_RATE_LIMIT` (default 30/h). `django-ratelimit` decorator hardening deferred to M8.

> [!NOTE]
> **Q2 — Chat session limits: CONFIRMED.**
> No limit on number of sessions per user in M7. Only message rate is limited.

> [!NOTE]
> **Q3 — Engine fallback scope: CONFIRMED.**
> Build `select_recipe_with_fallback` in `plan_service.py`, but keep it opt-in. `select_recipe` remains the active path in all views. The fallback is wired in only after M7 is proven stable.

---

## Core Design: Provider-Agnostic LLM Layer

### Why

The original M7 plan hardcoded the OpenAI SDK. We want to switch freely between providers without code changes:
- **openrouter** (default) — OpenAI-compatible gateway, has free models
- **openai** — native OpenAI, paid, future option
- **gemini_openai** — Gemini via its OpenAI-compatible endpoint, free tier
- **gemini_native** — Gemini via google-genai SDK, free tier

The first three all speak the OpenAI Chat Completions protocol, so they share one code path (OpenAI SDK pointed at different `base_url`s). `gemini_native` uses `google-genai` and is adapted to return the same shape.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Downstream code (chat_service, prompt_builder,          │
│  ai_recipe_validator, engine fallback)                   │
│                                                          │
│  Calls ONLY:                                             │
│    llm_client.chat_completion(messages, ...)             │
│    llm_client.structured_completion(messages, schema)    │
└────────────────────────┬────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           │     llm_client.py          │
           │  (provider-agnostic API)   │
           └─────────────┬──────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
 ┌────────────┐  ┌────────────┐  ┌────────────┐
 │  OpenAI    │  │  OpenAI    │  │  Gemini    │
 │  compat    │  │  compat    │  │  native    │
 │ (openai    │  │ (gemini    │  │ (google-   │
 │  SDK)      │  │  _openai)  │  │  genai)    │
 └────────────┘  └────────────┘  └────────────┘
     ▲                ▲
     │                │
 openrouter      openai (native)
```

### Provider Registry (`llm_config.py`)

**Reference:** `docs/files/llm_config.py`

- `Provider` enum: `OPENROUTER`, `OPENAI`, `GEMINI_OPENAI`, `GEMINI_NATIVE`
- `ProviderConfig` frozen dataclass: `provider`, `api_key`, `model`, `base_url` (None for native SDKs), `timeout_seconds`, `supports_strict_schema`
- `get_provider_config()`: resolves from `settings.AI_PROVIDER` at request time (lazy, never at import — tests don't need real keys)
- Per-provider defaults table including `base_url`, `model_env`, `model_default`, `key_env`, `supports_strict_schema`

| Provider | base_url | Default model | Key env | Strict schema? |
|----------|----------|---------------|---------|---------------|
| openrouter | `https://openrouter.ai/api/v1` | `openrouter/free` | `OPENROUTER_API_KEY` | No |
| openai | `https://api.openai.com/v1` | `gpt-4o` | `OPENAI_API_KEY` | Yes |
| gemini_openai | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` | `GEMINI_API_KEY` | No |
| gemini_native | None (SDK-managed) | `gemini-2.5-flash` | `GEMINI_API_KEY` | Yes |

### Provider-Agnostic Client (`llm_client.py`)

**Reference:** `docs/files/llm_client.py`

Two public functions — all downstream code calls only these:

| Function | Signature | Description |
|----------|-----------|-------------|
| `chat_completion` | `(messages, *, json_mode=False, stream=False) -> str \| Iterator[str]` | Returns assistant text (or token iterator if streaming). Routes to OpenAI-compatible path or Gemini native path based on active provider. |
| `structured_completion` | `(messages, schema) -> dict` | Returns parsed JSON dict. Calls `chat_completion` with `json_mode=True`, then `_parse_json_strict()`. |

**Implementation paths:**

1. **OpenAI-compatible** (`openrouter`, `openai`, `gemini_openai`): Uses `openai.OpenAI(api_key=..., base_url=...)`. OpenRouter gets attribution headers (`HTTP-Referer`, `X-Title`).
2. **Gemini native** (`gemini_native`): Uses `google.genai.Client(api_key=...)`. Converts OpenAI-style messages to Gemini's format:
   - `system` role messages → concatenated into `system_instruction`
   - All other role messages → concatenated into `contents`
   - `json_mode=True` → `response_mime_type="application/json"`

**Error handling:**
- Retry max 2× on transient errors (timeout, connection, ratelimit, 502, 503, overloaded) with 1.5s delay
- Hard failure → `ExternalServiceError(code=LLM_FAILURE)`
- Token usage logged to structured logs: `event=llm_completion`, `provider`, `model`, `prompt_tokens`, `completion_tokens`

**Streaming:**
- OpenAI-compatible: `client.chat.completions.create(stream=True)` → yield `chunk.choices[0].delta.content`
- Gemini native: `client.models.generate_content_stream(...)` → yield `chunk.text`
- Both yield text chunks through the same `StreamingHttpResponse` path in the view

### Strict JSON Contract (Core Resilience Strategy)

> [!IMPORTANT]
> **We do NOT trust any provider's JSON schema enforcement.** It varies across providers, and free Gemini models are unreliable here. Instead, we use a 4-layer defense:

1. **Prompt-level:** `prompt_builder` ALWAYS embeds the exact JSON schema in the prompt text and instructs: *"Return ONLY valid JSON matching this schema. No markdown, no prose, no code fences."*
2. **Response format:** Request `json_object` response_format where supported (tells the model to return valid JSON, but no schema enforcement)
3. **Defensive parsing:** `_parse_json_strict()` strips markdown fences (`\`\`\`json ... \`\`\``) — common with free Gemini models despite json_mode — and parses. Raises `LLM_FAILURE` on non-JSON or non-dict output.
4. **Downstream validation:** `ai_recipe_validator` validates the parsed structure and REJECTS anything malformed (unknown ingredients, implausible calories, etc.)

This means the same downstream validation works for every provider, regardless of how well (or poorly) they honor schema constraints.

---

## New Dependencies

| Package | Version (pin) | Purpose |
|---------|--------------|---------|
| `openai` | `1.82.0` | OpenAI-compatible path (openrouter, openai, gemini_openai) |
| `httpx` | `0.28.1` | USDA HTTP client + openai SDK dependency |
| `google-genai` | `1.20.0` | Gemini native path; safe to install always, only used when `AI_PROVIDER=gemini_native` |

All three pinned in `requirements/base.txt`. Add `openai.*` and `google.*` to mypy `ignore_missing_imports` in `pyproject.toml`.

---

## Error Codes

#### [MODIFY] `core/error_codes.py`

Add `LLM_FAILURE = "LLM_FAILURE"` as the canonical error code for all LLM calls. Keep `OPENAI_FAILURE` in the registry (backward compat / may alias `LLM_FAILURE`). `USDA_FAILURE` unchanged (USDA client still uses it).

All M7 LLM-related code uses `LLM_FAILURE`, not `OPENAI_FAILURE`.

---

## Proposed Changes

### New Django App: `apps/chat/`

Full per-app layout per CLAUDE.md §7.2.

#### [NEW] `apps/chat/__init__.py`
#### [NEW] `apps/chat/apps.py`
- `ChatConfig(AppConfig)` with `name = "apps.chat"`

#### [NEW] `apps/chat/models.py`

| Model | Fields | Notes |
|-------|--------|-------|
| `ChatSession` | `user` (FK User, indexed), `title` (CharField blank, max 200), `started_at` (auto_now_add), `last_message_at` (DateTimeField, updated on each message) | Inherits `TimestampedModel` |
| `ChatMessage` | `session` (FK ChatSession, indexed), `role` (CharField enum: `user` / `assistant` / `system`), `content` (TextField), `metadata` (JSONField, null=True — stores `{recipes: [...], validated: bool, provider: str, model: str, tokens: {prompt, completion}}` for ingredient mode), `created_at` (auto_now_add) | Inherits `TimestampedModel`. Index on `(session, created_at)` for paginated message retrieval. Note: `metadata` stores `provider` (not just `model`) for provenance tracking. |

#### [NEW] `apps/chat/migrations/0001_initial.py`
- Auto-generated migration for both models

---

### Service Layer (6 files)

#### [NEW] `apps/chat/services/llm_config.py`

Provider registry. **Adapt from reference:** `docs/files/llm_config.py`

- `Provider` enum (4 values)
- `ProviderConfig` frozen dataclass
- `get_provider_config()` — lazy resolution from settings
- `_PROVIDER_DEFAULTS` dict

Claude Code must adapt to use our `core/exceptions.py::ExternalServiceError` pattern. Raise `ValueError` (not an `ExternalServiceError`) for invalid `AI_PROVIDER` — this is a configuration error, not a runtime service failure.

#### [NEW] `apps/chat/services/llm_client.py`

Provider-agnostic LLM client. **Adapt from reference:** `docs/files/llm_client.py`

- Two public functions: `chat_completion()`, `structured_completion()`
- OpenAI-compatible path: `_openai_compatible_completion()`, `_stream_openai()`
- Gemini native path: `_gemini_native_completion()`, `_stream_gemini()`
- Helpers: `_is_transient()`, `_parse_json_strict()`
- All errors → `ExternalServiceError(code=LLM_FAILURE)` from `core/error_codes.py`
- Imports are **lazy** (inside functions) so tests don't need the packages installed with real keys

#### [NEW] `apps/chat/services/prompt_builder.py`

| Function | Signature | Description |
|----------|-----------|-------------|
| `build_system_prompt` | `(profile: DietaryProfile, today_plan: MealPlan \| None) -> str` | System prompt with: targets, diet pattern, allergies (**CRITICAL: explicit "never recommend foods containing X"**), today's plan, recent adherence. |
| `build_ingredient_prompt` | `(ingredients: list[str], profile: DietaryProfile, available_ingredient_names: list[str], count: int) -> list[dict]` | System + user messages for ingredient mode. **Embeds the full JSON schema in the prompt text** and instructs: "Return ONLY valid JSON matching this schema. No markdown, no prose." Passes the list of valid `Ingredient.name` values so the model is constrained to use existing ingredients. |

**Schema embedding pattern:** The prompt includes the recipe JSON schema literally (as a string in the system message), NOT via `response_format.json_schema`. This ensures schema instructions work identically across all providers, including those that don't support strict schema enforcement.

#### [NEW] `apps/chat/services/usda_client.py`

USDA FoodData Central API client with Redis caching. Unchanged from original plan.

| Function | Signature | Description |
|----------|-----------|-------------|
| `search_food` | `(query: str) -> list[dict]` | `GET /foods/search?query=...&pageSize=5`. Cached in Redis 30 days. |
| `get_food_nutrients` | `(fdc_id: int) -> dict` | `GET /food/{fdcId}`. Cached in Redis 30 days. |
| `macros_per_100g` | `(query: str) -> dict \| None` | Convenience: search → pick best match → extract macros. Returns `None` if no match. |

Uses `httpx` for HTTP. Redis cache TTL: 2,592,000s (30 days). Errors → `ExternalServiceError(code=USDA_FAILURE)`. Prioritizes `foundationFoods`, falls back to `srLegacy`.

#### [NEW] `apps/chat/services/ai_recipe_validator.py`

Validates and persists AI-generated recipes. Unchanged from original plan except it now receives output from `llm_client.structured_completion()` (not directly from OpenAI).

| Function | Signature | Description |
|----------|-----------|-------------|
| `validate_and_persist_ai_recipe` | `(recipe_json: dict, user: User) -> Recipe` | Validation pipeline (see below) |

**Validation pipeline:**
1. Every `ingredient_name` MUST exist in `Ingredient` table → fail with `VALIDATION_ERROR`
2. `quantity_grams` in `(1, 5000)` range per ingredient
3. `servings` in `(1, 12)`
4. `meal_type` in valid enum
5. Compute nutrition via existing `compute_recipe_nutrition` (no USDA call — ingredients already have nutrition data)
6. Computed `calories/serving` must be in `(50, 1500)`
7. Persist as `Recipe` with `source='ai_generated'`, `is_active=True`
8. Return saved `Recipe`

AI-generated recipes are first-class Layer 1 recipes — the engine can select them in future meal plans.

#### [NEW] `apps/chat/services/chat_service.py`

Main orchestrator. Calls `llm_client` functions (never OpenAI or Gemini directly).

| Function | Signature | Description |
|----------|-----------|-------------|
| `create_session` | `(user: User, title: str = "") -> ChatSession` | Creates a new chat session. |
| `list_sessions` | `(user: User) -> QuerySet` | Returns sessions ordered by `-last_message_at`. |
| `get_session_messages` | `(session_id: int, user: User) -> QuerySet` | Returns messages ordered by `created_at`. Validates ownership. |
| `send_message_chat` | `(session: ChatSession, content: str, user: User) -> ChatMessage` | Free-chat mode: load profile + today's plan → `prompt_builder.build_system_prompt()` → `llm_client.chat_completion()` → save user + assistant messages → return assistant message. |
| `send_message_chat_stream` | `(session: ChatSession, content: str, user: User) -> Iterator[str]` | Streaming variant: builds same messages → `llm_client.chat_completion(stream=True)` → yields SSE chunks, saves full response after stream completes. |
| `send_message_ingredient` | `(session: ChatSession, content: str, ingredients: list[str], user: User) -> ChatMessage` | Ingredient mode: `prompt_builder.build_ingredient_prompt()` → `llm_client.structured_completion()` → validate each recipe via `ai_recipe_validator` → save message with `metadata.recipes`. |
| `check_rate_limit` | `(user: User) -> None` | Counts `ChatMessage` rows (role=`user`) in last hour. Raises `RateLimitError(code=RATE_LIMITED)` if count ≥ `settings.CHAT_RATE_LIMIT`. |

---

### Serializers

#### [NEW] `apps/chat/serializers.py`

| Serializer | Purpose |
|------------|---------|
| `ChatSessionSerializer` | Read: `id`, `title`, `started_at`, `last_message_at`, `message_count` |
| `ChatMessageSerializer` | Read: `id`, `role`, `content`, `metadata`, `created_at` |
| `SendMessageSerializer` | Write: `content` (required), `mode` (enum: `chat` / `ingredient`), `ingredients` (list of str, required when mode=`ingredient`) |
| `CreateSessionSerializer` | Write: `title` (optional, blank default) |

---

### Views & URLs

#### [NEW] `apps/chat/views.py`

| View | Method | URL | Description |
|------|--------|-----|-------------|
| `ChatSessionListCreateView` | `POST` | `/api/v1/chat/sessions/` | Create session |
| `ChatSessionListCreateView` | `GET` | `/api/v1/chat/sessions/` | List sessions (paginated, newest first) |
| `ChatMessageListCreateView` | `GET` | `/api/v1/chat/sessions/<id>/messages/` | List messages (paginated, oldest first) |
| `ChatMessageListCreateView` | `POST` | `/api/v1/chat/sessions/<id>/messages/` | Send message (handles both modes + streaming) |

**Streaming negotiation:** If `Accept: text/event-stream` header is present and `mode=chat`, use `StreamingHttpResponse` with `async def`. Otherwise, return full JSON response. Streaming works for all providers — OpenAI-compatible via SDK stream, Gemini native via `generate_content_stream`.

#### [NEW] `apps/chat/urls.py`
- Two URL patterns mapping to the views above

#### [MODIFY] `nutriplan/api_router.py`
- Add `path("chat/", include("apps.chat.urls"))`

---

### Settings & Config Changes

#### [MODIFY] `nutriplan/settings/base.py`

**Reference:** `docs/files/SETTINGS_AND_ENV.py`

Add to `LOCAL_APPS`: `"apps.chat"`

Replace the current OpenAI-only settings block with provider-agnostic settings:

```python
# ── LLM Provider (M7) ────────────────────────────────────
AI_PROVIDER: str = env("AI_PROVIDER", default="openrouter")
LLM_TIMEOUT_SECONDS: int = env.int("LLM_TIMEOUT_SECONDS", default=30)

# --- OpenRouter ---
OPENROUTER_API_KEY: str = env("OPENROUTER_API_KEY", default="")
OPENROUTER_MODEL: str = env("OPENROUTER_MODEL", default="openrouter/free")

# --- OpenAI (native, paid) ---
OPENAI_API_KEY: str = env("OPENAI_API_KEY", default="")
OPENAI_MODEL: str = env("OPENAI_MODEL", default="gpt-4o")

# --- Gemini (both gemini_openai and gemini_native) ---
GEMINI_API_KEY: str = env("GEMINI_API_KEY", default="")
GEMINI_MODEL: str = env("GEMINI_MODEL", default="gemini-2.5-flash")
```

Remove the old `OPENAI_TIMEOUT_SECONDS` (replaced by `LLM_TIMEOUT_SECONDS`). Keep `OPENAI_API_KEY` and `OPENAI_MODEL` (now used when `AI_PROVIDER=openai`).

#### [MODIFY] `requirements/base.txt`
```
openai==1.82.0
httpx==0.28.1
google-genai==1.20.0
```

#### [MODIFY] `pyproject.toml`
Add to mypy `ignore_missing_imports` overrides:
- `openai.*`
- `google.*`

#### [MODIFY] `.env.example`
Replace the current OpenAI section with the full provider block from `SETTINGS_AND_ENV.py` reference.

#### [MODIFY] `core/error_codes.py`
Add `LLM_FAILURE = "LLM_FAILURE"`.

---

### Engine Fallback Hook

#### [MODIFY] `apps/mealplans/services/plan_service.py`

- Add `select_recipe_with_fallback(profile, slot, plan_date, exclude_ids, user)` that wraps `select_recipe`
- On `NoSuitableRecipeError`: call `llm_client.structured_completion()` to generate a recipe matching constraints → validate via `ai_recipe_validator.validate_and_persist_ai_recipe()` → return persisted Recipe
- **Per spec:** Do NOT wire into views yet. `select_recipe` stays the active path. The fallback is available but opt-in, switched after M7 is confirmed stable.

---

### New Documentation

#### [NEW] `docs/LLM_PROVIDER_SETUP.md`

Full provider setup guide. See separate file created alongside this plan. Covers:
- The 4 providers, cost, where to get each key
- How to switch: change `AI_PROVIDER` + set matching key, restart
- The free path: OpenRouter `:free` models or Gemini free tier
- Strict JSON contract and why we don't trust provider schema enforcement
- Provider comparison table

---

## File Summary

| Action | File | Category |
|--------|------|----------|
| [NEW] | `apps/chat/__init__.py` | App scaffold |
| [NEW] | `apps/chat/apps.py` | App scaffold |
| [NEW] | `apps/chat/models.py` | Models |
| [NEW] | `apps/chat/admin.py` | Admin |
| [NEW] | `apps/chat/migrations/0001_initial.py` | Migration |
| [NEW] | `apps/chat/services/__init__.py` | Services |
| [NEW] | `apps/chat/services/llm_config.py` | Services — provider registry |
| [NEW] | `apps/chat/services/llm_client.py` | Services — provider-agnostic LLM client |
| [NEW] | `apps/chat/services/prompt_builder.py` | Services — prompt construction |
| [NEW] | `apps/chat/services/usda_client.py` | Services — USDA API client |
| [NEW] | `apps/chat/services/ai_recipe_validator.py` | Services — AI recipe validation |
| [NEW] | `apps/chat/services/chat_service.py` | Services — orchestrator |
| [NEW] | `apps/chat/serializers.py` | Serializers |
| [NEW] | `apps/chat/views.py` | Views |
| [NEW] | `apps/chat/urls.py` | URLs |
| [NEW] | `apps/chat/tests/__init__.py` | Tests |
| [NEW] | `apps/chat/tests/test_models.py` | Tests |
| [NEW] | `apps/chat/tests/test_services.py` | Tests |
| [NEW] | `apps/chat/tests/test_views.py` | Tests |
| [NEW] | `docs/LLM_PROVIDER_SETUP.md` | Documentation |
| [MODIFY] | `nutriplan/api_router.py` | URL routing |
| [MODIFY] | `nutriplan/settings/base.py` | Config — provider-agnostic settings |
| [MODIFY] | `requirements/base.txt` | Dependencies (+3 packages) |
| [MODIFY] | `pyproject.toml` | Tooling config (mypy overrides) |
| [MODIFY] | `.env.example` | Env vars — provider block |
| [MODIFY] | `core/error_codes.py` | Add `LLM_FAILURE` |
| [MODIFY] | `apps/mealplans/services/plan_service.py` | Engine fallback (opt-in) |

**Total: 20 new files, 7 modified files**

---

## Verification Plan

### Automated Tests

All LLM tests mock at the `llm_client` boundary (`chat_completion` / `structured_completion`) so they are provider-independent.

| # | Test | What it verifies |
|---|------|-----------------|
| 1 | `test_llm_client_retries_on_transient_error` | Retries on transient error (timeout/connection), succeeds on 2nd try (mock) |
| 2 | `test_llm_client_raises_on_hard_failure` | `ExternalServiceError(LLM_FAILURE)` on non-transient error (mock) |
| 3 | `test_llm_client_strips_markdown_fences` | `_parse_json_strict` strips `` ```json ... ``` `` fences (free Gemini wraps JSON in fences) |
| 4 | `test_llm_client_raises_on_non_json` | Malformed output → `ExternalServiceError(LLM_FAILURE)` |
| 5 | `test_llm_client_raises_on_non_dict_json` | Valid JSON but array/string → `ExternalServiceError(LLM_FAILURE)` |
| 6 | `test_provider_config_resolves_from_env` | `AI_PROVIDER=gemini_openai` → correct `base_url`, `key_env`, model |
| 7 | `test_provider_config_resolves_default` | No `AI_PROVIDER` set → defaults to `openrouter` |
| 8 | `test_provider_config_invalid_provider_raises` | `AI_PROVIDER=invalid` → `ValueError` |
| 9 | `test_provider_config_missing_key_raises` | Provider set but no key → `ExternalServiceError(LLM_FAILURE)` on call |
| 10 | `test_recipes_from_ingredients_returns_schema_compliant` | Structured output matches recipe JSON schema (mock `structured_completion`) |
| 11 | `test_usda_client_caches_in_redis` | Second call for same query hits Redis, not HTTP (mock USDA) |
| 12 | `test_usda_client_raises_on_failure` | `ExternalServiceError(USDA_FAILURE)` on USDA error |
| 13 | `test_chat_message_persists_user_and_assistant` | Both user and assistant messages saved to DB |
| 14 | `test_chat_respects_rate_limit` | 31st message in an hour → `RateLimitError` |
| 15 | `test_ingredient_mode_returns_recipes_in_metadata` | `metadata.recipes` populated with validated recipes |
| 16 | `test_chat_system_prompt_contains_allergens` | System prompt includes "never recommend foods containing [allergens]" |
| 17 | `test_ai_recipe_rejected_when_unknown_ingredient` | `VALIDATION_ERROR` on ingredient not in DB |
| 18 | `test_ai_recipe_rejected_when_implausible_calories` | `VALIDATION_ERROR` when calories/serving outside (50, 1500) |
| 19 | `test_ai_recipe_persisted_with_correct_source_tag` | `source='ai_generated'`, `is_active=True` |
| 20 | `test_ai_recipe_appears_in_next_meal_plan_pool` | Engine includes `source='ai_generated'` recipes in candidate pool |
| 21 | `test_create_session_endpoint` | `POST /chat/sessions/` → 201 |
| 22 | `test_list_sessions_newest_first` | `GET /chat/sessions/` returns paginated, ordered by `-last_message_at` |
| 23 | `test_send_message_chat_mode` | `POST .../messages/ {mode: chat}` → assistant response (mock `chat_completion`) |
| 24 | `test_send_message_ingredient_mode` | `POST .../messages/ {mode: ingredient}` → recipes (mock `structured_completion`) |
| 25 | `test_session_ownership_enforced` | User A cannot access User B's session → 404 |
| 26 | `test_fallback_generates_recipe_on_no_suitable` | `select_recipe_with_fallback` catches `NoSuitableRecipeError` → LLM → valid Recipe |
| 27 | `test_metadata_stores_provider_info` | `ChatMessage.metadata` includes `provider` and `model` fields |

### Lint & Type Checks
```bash
make lint   # ruff + black --check + mypy --strict
make test   # all tests pass, ≥80% coverage on apps/chat/services/
```

### Manual Verification
- `make run-asgi` → test SSE streaming with `curl -N -H "Accept: text/event-stream"`
- Django admin → ChatSession and ChatMessage records visible
- Switch `AI_PROVIDER` env var → verify same endpoints work with different provider
- Send an ingredient-mode message → verify recipe cards returned with validated macros
