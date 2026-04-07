# Src Context

## Structure

```
src/
├── components/
│   ├── backend/
│   │   └── worker/         # Python CrewAI worker
│   └── frontend/
│       └── dashboard/      # Next.js dashboard
```

## Backend (worker)

**Language:** Python 3.12 | **Package manager:** uv

### Layout

| Directory | Purpose |
|-----------|---------|
| `agents/` | CrewAI agent definitions (one file per agent) |
| `tools/` | CrewAI tool implementations (Playwright, search, resume loader) |
| `models/` | Frozen Pydantic models — all inter-agent data structures |
| `db/` | Supabase client singleton + repository pattern for all DB access |
| `personal/` | Gitignored — resume PDF, personal_data.json, Gmail credentials |
| `tests/` | pytest test suite |

### Conventions

- **Type hints** on all function signatures and class attributes
- **Frozen Pydantic models** for all structured data — no raw dicts, no mutation
- **Google-style docstrings**
- **snake_case** for files, functions, variables
- **Structured logging** via `structlog` JSON output — no bare `print()`
- **`pathlib`** over `os.path` for file handling
- **Context managers** (`with`) for all resource handling

### Patterns to Avoid

- Mutable shared state between agents
- Raw dicts where a Pydantic model exists
- Importing business logic into agent files (keep agents thin; logic goes in tools)

### Testing

- Framework: `pytest`
- Target coverage: 80%+
- Pre-commit hooks: `ruff` (lint + format), `mypy`, trailing-whitespace
- Tests run on `git push` via GitHub Actions

## Frontend (dashboard)

**Language:** TypeScript | **Framework:** Next.js 14 (App Router)

### Conventions

- **PascalCase** for components and types
- **camelCase** for utilities and functions
- **Tailwind CSS** for all styling — no inline styles, no CSS modules
- **Supabase JS client** for data fetching and real-time subscriptions
- No `any` types
