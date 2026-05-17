# NutriPlan Backend — Runbook

Living document. The agent updates this at the end of every module (CLAUDE.md §12.4).

---

## Quick start (after M0)

```bash
# 1. Install deps
make install

# 2. Set up env
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DATABASE_URL, etc.

# 3. Initialize DB
make migrate

# 4. Run dev server
make run
# → http://localhost:8000/healthz
# → http://localhost:8000/api/docs/
```

---

## Common workflows

> The agent fills these in as modules complete. Examples below — replace with real instructions as they emerge.

### Reset local database (dev only)
TBD — added in M0.

### Seed recipe data
TBD — added in M3.

### Run a Celery worker locally
TBD — added in M6.

### Trigger a one-off task manually
TBD — added in M6.

---

## Environment variables

See `.env.example` for the full list with comments. Required vars by module:

| Module | New vars introduced |
|--------|---------------------|
| M0     | TBD                 |
| M1     | TBD                 |
| ...    |                     |

---

## Troubleshooting

> Append entries here as the agent encounters and resolves issues.

### "no module named 'psycopg'"
TBD

### Firebase token verification fails locally
TBD

---

## Deployment

> Filled in during M8.

### Railway
TBD

### Render
TBD
