# Tech Stack Overview

This document provides a concise reference to the core technologies
used in the CO₂ Calculator project. It focuses on essential facts to
minimize maintenance burden. For detailed rationale and alternatives
considered, see [Architectural Decisions](./14-architectural-decisions.md).

**Last Updated:** 2025-12-11

---

## Core Requirements

- **Open Source**: GPL-3.0 license, EPFL owns the code
- **Architecture**: Stateless web application (SPA + API), horizontally scalable
- **Deployment**: [docker-compose](https://docs.docker.com/compose/) (local/dev), [Kubernetes](https://kubernetes.io/) / [Helm](https://helm.sh/) (production)
- **Database**: [PostgreSQL](https://www.postgresql.org/) (production), [SQLite](https://www.sqlite.org/index.html) (development fallback)
- **Authentication**: JWT-based RBAC, pluggable for OIDC/OAuth2

---

## Runtime & Package Management

### Backend

- **Language**: [Python 3.12](https://www.python.org/) (target: 3.13 when stable in Alpine)
- **Package Manager**: [uv](https://docs.astral.sh/uv/)
- **Dependency File**: `backend/pyproject.toml`
- **Lockfile**: `uv.lock`

### Frontend

- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Runtime**: [Node.js 24.x](https://nodejs.org/)
- **Package Manager**: [npm (v10+)](https://www.npmjs.com/)
- **Type Checking**: [vue-tsc](https://deepwiki.com/vuejs/language-tools)
- **Dependency File**: `frontend/package.json`
- **Lockfile**: `package-lock.json`

---

## Frontend Stack

### Core Technologies

- **Framework**: [Vue 3](https://vuejs.org/) (Composition API)
- **UI Library**: [Quasar 2.x](https://quasar.dev/) (Material Design components)
- **Build Tool**: [Vite](https://vitejs.dev/) (via Quasar CLI)
- **State Management**: [Pinia](https://pinia.vuejs.org/)
- **Routing**: [vue-router](https://router.vuejs.org/)
- **Internationalization**: [vue-i18n](https://vue-i18n.intlify.dev/)
- **HTTP Client**: [ky](https://github.com/sindresorhus/ky)

### Internationalization resources

- Build integrates `@intlify/unplugin-vue-i18n` to load messages from `src/i18n/**/*.json` and `src/assets/i18n/**/*.json|md`, with `runtimeOnly: false` to support named tokens.

### Development

- **Testing**: [Playwright](https://playwright.dev/) (E2E + component tests)
- **Linting**: [ESLint](https://eslint.org/) + [Prettier](https://prettier.io/)
- **Type Checking**: [TypeScript](https://www.typescriptlang.org/) (gradual adoption)
- **Styles**: [CSS/SCSS](https://sass-lang.com/) (Stylelint configuration present)

### Deployment

- **Build Output**: Static SPA assets (`/dist/spa`)
- **Server**: Nginx (Alpine-based, port 8080, non-root)
- **Container**: Multi-stage build (`node:24-alpine` → `nginx:stable-alpine-slim`)

---

## Backend Stack

### Core Technologies

- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
- **ORM**: [SQLAlchemy 2.0 (async)](https://docs.sqlalchemy.org/en/20/)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
- **Database Drivers**: [psycopg](https://www.psycopg.org/) (PostgreSQL), [aiosqlite](https://aiosqlite.omnilib.dev/en/stable/) (SQLite)
- **Config Management**: [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **JWT Handling**: [joserfc](https://jose.authlib.org/en/#)
- **Password Hashing**: [passlib](https://passlib.readthedocs.io/en/stable/) (bcrypt)
- **HTTP Client**: [httpx](https://www.python-httpx.org/)

### Development

- **Testing**: [pytest](https://docs.pytest.org/en/stable/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/en/latest/) + [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/)
- **Linting**: [ruff](https://docs.astral.sh/ruff/)
- **Type Checking**: [mypy](https://mypy-lang.org/)
- **Load Testing**: [locust](https://locust.io/)

### Deployment

- **Container**: `ghcr.io/astral-sh/uv:python3.12-alpine` (multi-stage build)
- **Runtime User**: `appuser` (UID/GID 1001, non-root)
- **Exposed Port**: 8000

---

## Database Configuration

### Development (Default)

SQLite with aiosqlite driver at `./co2_calculator.db`.

### Production (Recommended)

External PostgreSQL 15+ managed service.

### Configuration Options

Via `pydantic-settings` in `backend/app/core/config.py`:

```bash
# Option 1: Full URL (takes precedence)
DB_URL="postgresql://user:pass@host:5432/db"

```

**Migrations**: Alembic in `backend/alembic/versions` (code review required).

---

## Deployment

### Local Development

docker-compose with services:

- `backend` (FastAPI on port 8000)
- `frontend` (Nginx on port 8080)
- `postgres` (PostgreSQL 18-alpine)
- `pgadmin` (database UI)
- `reverse-proxy` (Traefik — routes `/api/*` to backend, `/*` to frontend)

### Production (Kubernetes)

Helm chart in `helm/` with:

- Backend deployment (2+ replicas, HPA optional)
- Frontend deployment (2+ replicas, HPA optional)
- nginx-ingress controller (EPFL standard)
- TLS via cert-manager
- External PostgreSQL (recommended) or local SQLite (dev/testing)

**Security**: Non-root containers, read-only filesystems, no privilege escalation.

---

## CI/CD & Security

### Active Workflows (`.github/workflows`)

- **test.yml**: pytest (backend), Playwright (frontend)
- **security.yml**: npm audit, uv audit, Bandit, TruffleHog, CodeQL
- **quality-check.yml**: ruff, mypy, ESLint, Prettier (PRs)
- **deploy.yml**: Multi-arch container builds → ghcr.io (on main)
- **publish_chart.yaml**: Helm chart publishing (on version change)
- **deploy-mkdocs.yml**: Documentation deployment (GitHub Pages)
- **lighthouse.yml**: Frontend performance audits (PRs)
- **release-please.yml**: Automated semantic versioning

For complete workflow details, see
[CI/CD Workflows](cicd-workflows.md).

### Security Tools

- **SAST**: Bandit (Python), CodeQL, ESLint security rules
- **Dependency Scanning**: npm audit, uv audit
- **Secrets Detection**: TruffleHog (git history scan)

For security scanning details, see
[CI/CD Pipeline](06-cicd-pipeline.md#security-scanning).

---

## Documentation

MkDocs with Material theme at `docs/`. Deployed to GitHub Pages via
workflow. Supports Markdown, Mermaid diagrams, search, and git metadata.

---

## Performance & Scaling

Stateless design with JWT-based auth enables horizontal scaling via
HPA or manual replica adjustments. Database connection pooling handled
by SQLAlchemy (PgBouncer templates available in Helm but not
production-tested).

---

## Related Documentation

- [Architectural Decisions](./14-architectural-decisions.md) — Detailed rationale for tech choices
- [Deployment Topology](./11-deployment-topology.md) — Infrastructure diagrams and patterns
- [CI/CD Pipeline](./06-cicd-pipeline.md) — Workflow details and integration points
- Frontend: `frontend/package.json` — Exact dependency versions
- Backend: `backend/pyproject.toml` — Exact dependency versions
