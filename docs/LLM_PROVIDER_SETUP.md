# LLM Provider Setup Guide

NutriPlan supports 4 LLM backends, switchable by a single env var. No code changes needed — just set `AI_PROVIDER` and the matching API key, then restart the server.

---

## Provider Comparison

| Provider | `AI_PROVIDER` | Key env var | Model env var | Default model | Cost | Strict schema? | Notes |
|----------|--------------|-------------|---------------|---------------|------|---------------|-------|
| **OpenRouter** | `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` | `openrouter/free` | **Free** models available | No | Default. Gateway to hundreds of models. |
| OpenAI | `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-4o` | Paid (~$0.01–$0.05/chat) | Yes | Best quality. Needs billing. |
| Gemini (OpenAI-compat) | `gemini_openai` | `GEMINI_API_KEY` | `GEMINI_MODEL` | `gemini-2.5-flash` | **Free** tier available | No | Gemini via OpenAI endpoint. |
| Gemini (native SDK) | `gemini_native` | `GEMINI_API_KEY` | `GEMINI_MODEL` | `gemini-2.5-flash` | **Free** tier available | Yes | Uses google-genai SDK. |

---

## Quick Start (Free Development)

### Option A: OpenRouter (recommended — simplest)

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys) → create an account → generate API key
2. Add to `.env`:
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-v1-your-key-here
   OPENROUTER_MODEL=openrouter/free
   ```
3. `make run-asgi` → chat endpoints are live

The `:free` suffix on the model slug selects OpenRouter's free tier — no billing needed.

### Option B: Google Gemini (free tier)

1. Go to [aistudio.google.com](https://aistudio.google.com) → sign in with Google → get API key
2. Add to `.env`:
   ```
   AI_PROVIDER=gemini_openai
   GEMINI_API_KEY=AIza-your-key-here
   GEMINI_MODEL=gemini-2.5-flash
   ```
3. `make run-asgi` → chat endpoints are live

Both `gemini_openai` and `gemini_native` use the same key. Use `gemini_openai` for simplicity (shares the OpenAI SDK code path) or `gemini_native` for native SDK features.

---

## How to Switch Providers

1. Change `AI_PROVIDER` in `.env` to one of: `openrouter`, `openai`, `gemini_openai`, `gemini_native`
2. Set the matching API key env var (see table above)
3. Optionally change the model via the matching model env var
4. Restart the server (`make run-asgi`)

That's it. No code changes needed. All downstream code (chat service, prompt builder, recipe validator, engine fallback) calls provider-agnostic functions in `llm_client.py`.

---

## Getting Each Key

### OpenRouter
1. [openrouter.ai/keys](https://openrouter.ai/keys) → Sign up → Generate key
2. Free tier: models with `:free` suffix have no cost
3. Paid models: add credits at [openrouter.ai/credits](https://openrouter.ai/credits)

### OpenAI
1. [platform.openai.com](https://platform.openai.com) → Sign in
2. **Billing → Payment methods** → add card → set monthly hard limit (recommend $20 for dev)
3. **API keys → Create new secret key** → copy the `sk-...` value

### Google Gemini
1. [aistudio.google.com](https://aistudio.google.com) → Sign in with Google
2. Click "Get API Key" → create key for a new or existing Google Cloud project
3. Free tier: 15 RPM / 1M TPM / 1,500 RPD (varies by model)

### USDA FoodData Central (separate — not an LLM)
1. [fdc.nal.usda.gov/api-key-signup.html](https://fdc.nal.usda.gov/api-key-signup.html) → fill form
2. Key arrives by email in minutes
3. Free: 1,000 requests/hour per key, no credit card

---

## Architecture: Why Provider-Agnostic?

```
┌──────────────────────────────────────────┐
│  chat_service / ai_recipe_validator /     │
│  prompt_builder / engine fallback         │
│                                           │
│  Calls ONLY:                              │
│    llm_client.chat_completion(...)        │
│    llm_client.structured_completion(...)  │
└────────────────────┬─────────────────────┘
                     │
      ┌──────────────┴──────────────┐
      │       llm_client.py         │
      │  (provider-agnostic API)    │
      └──────────────┬──────────────┘
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
 ┌──────────┐  ┌──────────┐  ┌──────────┐
 │ OpenAI   │  │ OpenAI   │  │ Gemini   │
 │ compat   │  │ compat   │  │ native   │
 │ path     │  │ path     │  │ path     │
 └──────────┘  └──────────┘  └──────────┘
   openrouter    openai       gemini_native
                 gemini_openai
```

The first three providers all speak the OpenAI Chat Completions protocol, so they share one code path — the OpenAI SDK pointed at different `base_url`s. `gemini_native` uses the `google-genai` SDK and adapts its output to the same shape.

---

## The Strict JSON Contract

> **We do NOT trust any provider's JSON schema enforcement.**

Free Gemini models in particular are unreliable at following schema constraints — they often wrap JSON in markdown fences (\`\`\`json ... \`\`\`) despite being told not to.

Our defense-in-depth strategy:

1. **Prompt-level:** Every structured prompt embeds the exact JSON schema in the prompt text and instructs: *"Return ONLY valid JSON matching this schema. No markdown, no prose, no code fences."*

2. **Response format:** We request `json_object` response_format where supported. This asks the model to return valid JSON, but doesn't enforce a specific schema.

3. **Defensive parsing:** `_parse_json_strict()` in `llm_client.py`:
   - Strips markdown fences if present
   - Parses JSON
   - Raises `LLM_FAILURE` if output is not valid JSON or not a dict

4. **Downstream validation:** `ai_recipe_validator.validate_and_persist_ai_recipe()`:
   - Every ingredient must exist in our DB
   - Quantities must be in valid ranges
   - Computed calories must be plausible
   - Rejects anything that doesn't pass

This means the **same validation pipeline works identically for every provider**, regardless of how well (or poorly) they honor schema constraints. A model that returns perfect structured JSON and a model that wraps JSON in markdown fences are both handled correctly.

---

## Settings Reference

All settings with defaults (from `nutriplan/settings/base.py`):

```python
AI_PROVIDER         = "openrouter"                        # Which backend
LLM_TIMEOUT_SECONDS = 30                                  # Request timeout

OPENROUTER_API_KEY  = ""                                   # Key for OpenRouter
OPENROUTER_MODEL    = "openrouter/free"  # Model slug

OPENAI_API_KEY      = ""                                   # Key for OpenAI
OPENAI_MODEL        = "gpt-4o"                            # Model slug

GEMINI_API_KEY      = ""                                   # Key for Gemini
GEMINI_MODEL        = "gemini-2.5-flash"                  # Model slug

USDA_API_KEY        = ""                                   # USDA FoodData Central
USDA_BASE_URL       = "https://api.nal.usda.gov/fdc/v1"

CHAT_RATE_LIMIT     = "30/h"                              # Max messages per user per hour
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ExternalServiceError: No API key configured` | Key env var empty for active provider | Set the matching key in `.env` |
| `ValueError: Invalid AI_PROVIDER 'xxx'` | Typo in `AI_PROVIDER` | Must be one of: `openrouter`, `openai`, `gemini_openai`, `gemini_native` |
| `ExternalServiceError: LLM call failed` | Provider API error | Check API key validity, rate limits, model availability |
| JSON parse failure in logs | Model returned non-JSON despite json_mode | Expected with some free models; `ai_recipe_validator` catches and rejects |
| `USDA_FAILURE` | USDA API down or key invalid | Check key, retry; USDA caches aggressively so this is rare |
