# CO₂ Calculator — Agent Instructions

See [`docs/src/contributing/guardrails.md`](docs/src/contributing/guardrails.md) for code rules (patterns, style, architecture) — that file has precedence. (`.github/instructions/co2-calculator-rules.md.instructions.md` is a symlink to it.)

## Repo structure

```
backend/      FastAPI + SQLAlchemy + Alembic (Python 3.14, uv package manager)
frontend/     Quasar SPA + Vue 3 + TypeScript
docs/         MkDocs site
helm/         Kubernetes deployment charts
otel/         OpenTelemetry collector config
```

## Dev commands

| Task              | Command                                                       |
| ----------------- | ------------------------------------------------------------- |
| Full setup        | `make install`                                                |
| Run CI locally    | `make ci` (lint → type-check)                                 |
| Run tests         | `make test`                                                   |
| Format everything | `make format`                                                 |
| Start backend     | `cd backend && make dev` (uses `uv run uvicorn`)              |
| Start frontend    | `cd frontend && make dev` (uses `quasar dev`)                 |
| Start DB only     | `make run-db`                                                 |
| DB migrations     | `cd backend && make db-migrate` / `db-revision message="..."` |
| Docs locally      | `cd docs && make serve-docs`                                  |
| Storybook         | `cd frontend && make storybook`                               |

**Never `cd` into a subfolder with `cd` for lint/type-check/test — use the root `make` targets** (`make lint`, `make type-check`). Subfolder `make` calls exist but root targets are the canonical entry points.

## Backend gotchas

- Always run Python commands **through `uv run`** — bare `python` or `pytest` won't find installed packages. The Makefile does this via `PYTEST`, `RUFF`, `MYPY` variables.
- Backend app entrypoint: `app.main:app` (the ASGI app FastAPI creates).
- Tests: `make test` runs `tests/unit` only with 60% coverage. Full suite (`tests/`) is `make test-cov` with 45% threshold.
- Backend env: `backend/.env` is auto-created from `.env.example` on `make install`. Update it manually for local dev.
- DB seeds: `make seed-data`, `make seed-units`, `make seed-generic-data` (all use `uv run`).
- External dependency: `enacit4r-files` is pulled from a GitHub tag — ensure internet access for `uv sync`.
- Alembic migrations live in `backend/alembic/`. Generate with `make db-revision message="..."`.

## Frontend gotchas

- Frontend entrypoint: `quasar dev` (handled by `frontend/Makefile`'s `dev` target).
- Tests split into component tests (`npm run test-ct`) and e2e (`npm run test:e2e`). Root `make test` runs both sequentially.
- Type check uses `vue-tsc --noEmit -p tsconfig.typecheck.json` (not plain `tsc`).
- Lint runs **eslint** (JS/TS/Vue) and **stylelint** (SCSS) separately. Both must pass.
- `npm run dev`, `npm run build` — these use `quasar dev` / `quasar build` directly.
- `.stylelintrc.js` disables `no-invalid-position-at-import-rule` for `@layer` blocks intentionally — do not remove this override.

## Git & CI

- Branch from `dev`, PR back to `dev`.
- Conventional commits enforced (`feat:`, `fix:`, etc.) via commitlint.
- `lefthook` pre-commit hooks: format+lint staged files → full type-check.
- `lefthook` pre-push: runs `make ci` **only** on `dev`, `stage`, `main` branches.
- CI workflows: `.github/workflows/quality-check.yml` (lint+typecheck) and `.github/workflows/test.yml` (pytest + Playwright).

## Architecture notes

- **Postgres** via Docker Compose (port 5432). Admin via pgadmin (port 5050).
- **Reverse proxy**: Traefik in Docker Compose routes `/api` → backend, `/` → frontend.
- **i18n**: `frontend/src/i18n/` — always update **both** `en-US` and `fr-CH` locale files together.
- **Storybook**: `frontend/storybook/` — serves component docs and isolated testing.
- **Makefile delegation**: subfolder `Makefile`s are the real source of truth. Root `Makefile` orchestrates them.

## What to avoid

- Don't run `make ci` on feature branches during active development — only protected branches trigger it pre-push.
- Don't remove `enacit4r-files` from `pyproject.toml` — it's a project dependency, not dev-only.
- Don't use `nvm` or system Python for backend — always `uv`.
- Don't run frontend type-check outside the `frontend/` directory — paths are relative.
