# Planning Context

## What We're Building

Agentic Job Hunter — an autonomous multi-agent system that takes job search criteria (title, location, salary, keywords) and applies to matching jobs end-to-end with no human intervention. A Next.js dashboard tracks progress in real time.

## Current Priorities

1. **Refactor** — reorganize the codebase into the new `src/components/backend` / `src/components/frontend` structure before adding features
2. **Expand capabilities** — ATS detection, new job boards, cover letter generation
3. **Improve success rate** — target 50%+ application submission success

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | CrewAI (sequential crew, evolving toward orchestrator pattern) |
| LLM runtime | Ollama (local, default); configurable via env vars for external APIs |
| Browser automation | Playwright (headless Chromium) |
| Database | Supabase (Postgres + Realtime) |
| Dashboard | Next.js 14 (App Router) on Vercel |
| Package management | uv |

## Architectural Principles

- **Structured outputs** — all inter-agent data uses frozen Pydantic models; no raw dicts
- **Configurable LLM backend** — Ollama by default; any model can be swapped via `FAST_MODEL` / `REASONING_MODEL` env vars to support external API keys
- **Single responsibility agents** — each CrewAI agent owns one step; tools handle the unexpected
- **Privacy by default** — `personal/` (resume, credentials, personal data) is gitignored and never committed; used only at runtime

## Locked-In Decisions

- Supabase as the only data store
- Next.js dashboard hosted on Vercel
- CrewAI as the agent orchestration framework (sequential crew today, orchestrator pattern under consideration)

## Spec and Decision Docs

- `planning/specs/` — feature specs and PRDs
- `planning/architecture/` — system design and component diagrams
- `planning/decisions/` — ADRs for significant architectural choices
