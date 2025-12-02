# Tech Stack Overview

This document provides a concise reference to the core technologies
used in the CO2 Calculator project. It focuses on essential facts to
minimize maintenance burden. For detailed rationale and alternatives
considered, see [Architectural Decisions](./14-architectural-decisions.md).

**Last Updated:** 2025-11-11

---

## Core Requirements

- **Open Source**: GPL-3.0 license, EPFL owns the code
- **Architecture**: Stateless web application (SPA + API), horizontally scalable
- **Deployment**: docker-compose (local/dev), Kubernetes/Helm (production)
- **Database**: PostgreSQL (production), SQLite (development fallback)
- **Authentication**: JWT-based RBAC, pluggable for OIDC/OAuth2

---

## Runtime & Package Management

### Backend

- **Python**: 3.12 (target: 3.13 when stable in Alpine)
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Dependency File**: `backend/pyproject.toml`

### Frontend

- **Node**: 24.x LTS
- **Package Manager**: npm (v10+)
- **Dependency File**: `frontend/package.json`

---

## Frontend Stack

### Core Technologies

- **Framework**: Vue 3 (Composition API)
- **UI Library**: Quasar 2.x (Material Design components)
- **Build Tool**: Vite (via Quasar CLI)
- **State Management**: Pinia
- **Routing**: vue-router
- **Internationalization**: vue-i18n
- **HTTP Client**: ky

### Development

- **Testing**: Playwright (E2E + component tests)
- **Linting**: ESLint + Prettier
- **Type Checking**: TypeScript (gradual adoption)

### Deployment

- **Build Output**: Static SPA assets (`/dist/spa`)
- **Server**: Nginx (Alpine-based, port 8080, non-root)
- **Container**: Multi-stage build (`node:24-alpine` → `nginx:stable-alpine-slim`)

---

## Backend Stack

### Core Technologies

- **Web Framework**: FastAPI
- **ASGI Server**: Uvicorn
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Database Drivers**: psycopg (PostgreSQL), aiosqlite (SQLite)
- **Config Management**: pydantic-settings
- **JWT Handling**: joserfc
- **Password Hashing**: passlib (bcrypt)
- **HTTP Client**: httpx

### Development

- **Testing**: pytest + pytest-asyncio + pytest-cov
- **Linting**: ruff
- **Type Checking**: mypy
- **Load Testing**: locust

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
- `postgres` (PostgreSQL 15-alpine)
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
