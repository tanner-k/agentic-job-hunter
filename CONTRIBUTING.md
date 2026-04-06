# Contributing

Contributions are welcome. Please follow these steps:

## Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Write tests first, then implement
4. Ensure the test suite passes and linting is clean:
   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format .
   uv run mypy worker/
   ```
5. Open a pull request against `main` with a clear description of the change

## Commit Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`

## Pull Request Guidelines

- Keep PRs focused on a single concern
- Include test coverage for any new behaviour
- Reference any related issues in the PR description
- Ensure CI passes before requesting review

## Development Setup

See [README.md](README.md#quick-start) for the full setup guide.

```bash
uv sync
uv run pre-commit install
uv run playwright install chromium
```
