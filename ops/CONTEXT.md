# Ops Context

## Infrastructure

| Component | Where it runs |
|-----------|--------------|
| Worker (Python) | Local developer machine |
| Dashboard (Next.js) | Vercel — auto-deploys on push to `main` via GitHub integration |
| Database | Supabase (Postgres + Realtime) — managed cloud |

## CI/CD

GitHub Actions runs on every pull request targeting `main`:

- **Python:** `ruff` lint + format check, `mypy` type check, `pytest` test suite
- **Dashboard:** `eslint` lint, `next build`

No automated deployment pipeline for the worker — it is started manually with `uv run python -m worker.main`.

## Scripts

`ops/scripts/` contains operational scripts:

| Path | Purpose |
|------|---------|
| `ops/scripts/supabase/` | Database migrations — run manually via the Supabase SQL editor |

To apply a migration: open the Supabase project dashboard → SQL Editor → paste and run the migration file.

## Monitoring

Current state: none beyond local `structlog` JSON output.

Aspirational:
- Alerting when the worker crashes or a task enters a permanent failure state
- Log aggregation for structured JSON worker output
