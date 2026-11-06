# JobTracking

Personal job search helper (in development): will find the jobs I'm most likely to hear back from, send me the top picks on Discord, and track every application. These features are planned and not yet functional.

- Design and decisions: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Work items: GitHub issues `JT-<n>` on the project board

## Requirements
- [uv](https://docs.astral.sh/uv/) (manages Python, the virtual environment and dependencies)
- Git

## First-time setup
```powershell
uv sync                      # installs Python 3.13 (if needed), creates .venv, installs dev tools
uv run pre-commit install    # switches on the commit / commit-msg / pre-push checks
```

## Everyday commands
| Task | Command |
|---|---|
| Run all pre-commit checks on every file | `uv run pre-commit run --all-files` |
| Fast unit tests | `uv run pytest tests/unit` |
| All tests with coverage | `uv run pytest --cov -m "not live"` |
| Format code | `uv run ruff format` |
| Lint (auto-fix) | `uv run ruff check --fix` |
| Type check | `uv run mypy` |

## Workflow
- Branch from `develop`: `type/short-description` (e.g. `feature/jt-1-greenhouse-jobs`).
  Types: `feature`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `build`.
- Commit with [Conventional Commits](https://www.conventionalcommits.org/): `feat: ...`, `fix: ...`, `chore: ...`.
- Open a PR into `develop` with `Closes #<issue>`; merge when CI is green.
- Never commit directly to `develop` or `production` (blocked by the hooks).

## Configuration
Copy the templates below. Note: configuration is still being built out — these templates are placeholders and don’t yet contain usable settings:
```powershell
[ -f config.yaml ] || cp config.example.yaml config.yaml
[ -f .env ] || cp .env.example .env
```
