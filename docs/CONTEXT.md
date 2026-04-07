# Docs Context

## Purpose

Documentation serves two audiences equally:
1. **Human contributors and users** — developers forking, contributing, or setting up the project
2. **AI agents** (e.g., Claude Code) — context files that help AI assistants understand the system before making changes

## What Lives Here

| Path | Content |
|------|---------|
| `docs/api/` | Worker API docs — agent interfaces, tool contracts, Pydantic model schemas |
| `docs/guides/` | How-to guides (adding a new agent, configuring a different LLM, setting up Gmail) |
| `docs/changelog/` | Version changelog |

The root `README.md` stays at the project root — it is not duplicated here.

## Documentation Standards

- **Audience-first** — write for someone who has never seen this codebase
- **Concise** — setup steps, commands, gotchas only; no padding
- **AI-readable** — use clear headings and structured lists so context files load cleanly into agent sessions
- **Code examples** — include runnable snippets wherever a concept isn't obvious from prose alone

## In-Code Documentation

- **Google-style docstrings** on all public functions and classes in the worker
- Docstrings describe what a function does, its arguments, and what it returns — not how it does it
- Complex logic gets an inline comment explaining *why*, not *what*
