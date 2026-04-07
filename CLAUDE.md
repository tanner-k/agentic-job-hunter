# Agentic Job Hunter

Autonomous multi-agent system that takes job search criteria and applies to matching jobs end-to-end with no human intervention.

## Rules
- Write in plain, clear language
- Ask clarifying questions before making assumptions
- When you are unsure, say so

## Tech Stack
- Frontend: Next.js 14 (App Router) / TypeScript / Tailwind CSS
- Backend: Python 3.12 / CrewAI / Ollama (local LLM)
- Database: Supabase (Postgres + Realtime)
- Deploy: Vercel (dashboard), local machine (worker)

## Workspaces
- `/planning` — Specs, architecture decisions, design docs
- `/src` — Application code (backend worker + frontend dashboard)
- `/docs` — API docs, guides, changelog
- `/ops` — Deployment, migrations, monitoring

## Routing
| Task | Go to | Read | Skills |
|------|-------|------|--------|
| Spec a feature | /planning | CONTEXT.md | brainstorming, superpowers:writing-plans |
| Write code | /src | CONTEXT.md | superpowers:test-driven-development, superpowers:requesting-code-review, systematic-debugging, ui-ux-pro-max |
| Write docs | /docs | CONTEXT.md | superpowers:writing-plans |
| Deploy or debug ops | /ops | CONTEXT.md | systematic-debugging |

## Naming Conventions
- Specs: `feature-name_spec.md`
- Decision records: `YYYY-MM-DD-decision-title.md`
- Python tests: `test_feature_name.py`
- TypeScript components: `PascalCase`
- TypeScript tests: `feature-name.test.ts`
