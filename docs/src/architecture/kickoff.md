# 🧭 Developer Kickoff Brief — Calculateur CO₂ @ EPFL

**Project purpose:**
A modular, open-source web application allowing EPFL labs to record, visualise and simulate CO₂ emissions from research activities — built according to EPFL IT & security standards.

---

## 1 — Technical Overview

| Layer                | Stack                                                                                | Purpose / Notes                                                   |
| :------------------- | :----------------------------------------------------------------------------------- | :---------------------------------------------------------------- |
| **Frontend**         | Vue 3 + Vite + Quasar + Pinia + Vue-Router + Vue-i18n + eCharts + Marked             | Responsive SPA, modular UI kit, built-in i18n and theming         |
| **Backend**          | Python 3.13 / FastAPI / Uvicorn / SQLAlchemy + asyncpg + Alembic / Dynaconf / Poetry | High-performance REST + WebSocket API, async, typed, OpenAPI docs |
| **Auth & Sessions**  | OIDC / OAuth 2 via MS Entra ID + enacit4r-auth                                       | EPFL SSO, JWT-based stateless sessions                            |
| **Database**         | PostgreSQL 15+                                                                       | Main data store; strict migrations, role-based access             |
| **Cache / Broker**   | Redis 7+                                                                             | Caching, rate-limiting, background jobs, token blacklist          |
| **Workers**          | Celery + Redis                                                                       | Async CSV imports, report generation, e-mail tasks                |
| **Containerisation** | Docker / docker-compose + Traefik (dev) / Kubernetes + nginx-ingress (prod)          | Dev reproducibility + scalable deployment                         |
| **Observability**    | Prometheus + Grafana + OpenTelemetry + EPFL SIEM logs                                | Metrics, dashboards, alerting, traceability                       |
| **CI/CD**            | GitHub Actions                                                                       | Lint → Test → Build → Scan → Deploy (GitOps)                      |

---

## 2 — Repository Layout

```
root/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── stores/          # Pinia stores
│   │   ├── charts/          # eCharts configs
│   │   ├── i18n/            # locale JSONs
│   │   └── router/
│   ├── public/
│   ├── vite.config.ts
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routers
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # business logic
│   │   ├── auth/            # OIDC adapter
│   │   ├── workers/         # Celery tasks
│   │   └── core/            # config, logging, metrics
│   ├── migrations/          # Alembic
│   ├── tests/
│   ├── pyproject.toml       # uv
│   └── Dockerfile
│
├── infra/
│   ├── docker-compose.yml
│   ├── traefik/
│   └── k8s/                 # manifests / Helm chart
│
└── docs/
    ├── architecture.md
    ├── api_reference.md
    └── contributing.md
```

---

## 3 — Environment setup

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run build    # → dist/
```

### Backend

```bash
cd backend
uv sync
poetry run uvicorn app.main:app --reload
```

### Docker (local full stack)

```bash
docker compose up --build
# services: traefik, frontend, backend, postgres, redis, pgadmin
```

### Kubernetes

- Manifests: `infra/k8s/`
- Deploy with `kubectl apply -k infra/k8s` or via Helm.
- Ingress class: `nginx` (cert-manager handles TLS).

---

## 4 — Coding Standards

### 4.1 Backend (Python / FastAPI)

| Category        | Rule                                                                                          |
| :-------------- | :-------------------------------------------------------------------------------------------- |
| **Style**       | Follow **PEP 8**, **PEP 484** typing, **black** auto-formatter, **isort**, **ruff** for lint. |
| **Async**       | Prefer async/await end-to-end; no blocking I/O inside request handlers.                       |
| **Type safety** | All public functions must be fully type-hinted; use `mypy` in CI.                             |
| **Config**      | Centralize in `app/core/config.py` via Dynaconf. Never hard-code secrets.                     |
| **Routing**     | Group endpoints by domain in `app/api/v1/…`; mount under `/api/v1`.                           |
| **Validation**  | Use Pydantic schemas for all inputs / outputs; never trust user data.                         |
| **Database**    | Access through repository pattern; commit only in service layer.                              |
| **Testing**     | Use **pytest** + **httpx.AsyncClient**; minimum 70 % coverage gate in CI.                     |
| **Docs**        | Ensure FastAPI generates valid OpenAPI 3; keep docstrings up-to-date.                         |
| **Security**    | Validate JWTs on every request; sanitize any Markdown rendered server-side.                   |

### 4.2 Frontend (Vue / Quasar)

| Category     | Rule                                                                                |
| :----------- | :---------------------------------------------------------------------------------- |
| **Language** | Vue 3 composition API, `<script setup>` syntax; TypeScript optional but encouraged. |
| **State**    | Use Pinia for global state; no ad-hoc event bus.                                    |
| **Routing**  | vue-router 4; all routes defined in `src/router/index.ts`.                          |
| **i18n**     | Text never hard-coded; always via `$t()`. Default EN, fallback FR.                  |
| **Styling**  | Scoped SCSS; adhere to EPFL color palette and accessibility contrast ≥ 4.5:1.       |
| **Lint**     | ESLint + Prettier; run `npm run lint` before commit.                                |
| **Security** | Sanitize Markdown with DOMPurify; CSP headers enforced by backend.                  |
| **Testing**  | Vitest + Vue Test Utils; target 80 % coverage.                                      |

---

## 5 — Branching & Version Control

| Branch            | Purpose                                   |
| :---------------- | :---------------------------------------- |
| `main`            | stable, tagged releases, deployed to prod |
| `develop`         | integration branch for next release       |
| `feature/<issue>` | short-lived feature branches              |
| `fix/<issue>`     | bug fixes                                 |
| `chore/…`         | non-functional changes (deps, config)     |

**Conventions**

- Conventional Commits (`feat:`, `fix:`, `chore:` …).
- PRs must reference issue ID and include short description.
- Commit merges only

---

## 6 — CI / CD Pipeline Stages

| Stage              | Tool                             | Key checks                  |
| :----------------- | :------------------------------- | :-------------------------- |
| **Lint & Format**  | black / ruff / ESLint / Prettier | Style compliance            |
| **Test**           | pytest / vitest                  | 70 % coverage               |
| **Build**          | Docker buildx                    | Multi-arch OCI image        |
| **Scan**           | Trivy + Bandit + npm-audit       | Security                    |
| **Deploy-staging** | kubectl / Helm                   | Auto after dev merge + tag  |
| **Manual promote** | CI environment                   | Approval-gated prod release |

Artifacts: versioned docker images tagged `vX.Y.Z` + `latest` `dev`.

---

## 7 — Security & Compliance Practices

- **Authentication** — MS Entra ID (OIDC / OAuth2) + JWT validation in backend.
- **Authorization** — Role-based
- **Transport Security** — HTTPS only; TLS managed by ingress/proxy (load balancer)
- **Secrets** — via env vars / Vault / sealed-secrets; never in git. (.env.example allowed)
- **CORS** — NO CORS.
- **Headers** — HSTS, CSP, Referrer-Policy, X-Frame-Options, etc.
- **Logs** — JSON structured; ingestable by EPFL SIEM.
- **Data Retention** — implement retention periods (10 years / 5 years travel).
- **Dependency updates** — weekly Dependabot + quarterly manual review.

---

## 8 — Testing Pyramid

1. **Unit tests** — 70 % of coverage; pure logic & utils.
2. **Integration tests** — DB, API routes (FastAPI + TestClient).
3. **E2E tests** — Cypress; key user flows only.
4. **Load tests** — k6 or Locust on staging before major releases.

---

## 9 — Observability Guidelines

- Add `/metrics` endpoint (Prometheus).
- Use OpenTelemetry SDK to emit traces to collector.
- Log every request with correlation ID (X-Request-ID).
- Frontend: send analytics events (anonymised) for usage stats.
- Dashboards: latency p95, error rate, CPU / mem, job queue depth.

---

## 10 — Performance & Scalability

| Concern       | Practice                                   |
| :------------ | :----------------------------------------- |
| Statelessness | JWT sessions; no in-memory user state      |
| Caching       | Redis for factor tables + rate limiting    |
| DB pooling    | asyncpg pool / PgBouncer                   |
| Concurrency   | Scale pods via HPA + CPU/mem metrics       |
| Static assets | Served by CDN/efl s3 / Ingress cache layer |
| Heavy tasks   | Offload to Celery workers (csv upload)     |

---

## 11 — Code Review & Merge Process

- **2 reviewers** minimum for backend critical code (auth, DB, security).
- CI must pass before merge.
- Each PR includes:
  - Description + screenshots (if UI)
  - Linked issue #
  - Test evidence (`pytest –k <feature>` output OK)

- Post-merge: auto-deploy to staging, smoke test, then manual prod approval.

---

## 12 — Release & Versioning

- Semantic Versioning: `MAJOR.MINOR.PATCH`.
- Release notes auto-generated from Conventional Commits.
- Tag → GitHub Release → Docker image → Manifest or Helm chart update.
- Each release validated on staging before promotion.

---

## 13 — Documentation & Knowledge Transfer

| Deliverable         | Tool / Format                           |
| :------------------ | :-------------------------------------- |
| Developer Guide     | `/docs/developer_guide.md`              |
| API Docs            | auto-generated Swagger / ReDoc          |
| Infrastructure Docs | `/docs/infra.md` + Helm values          |
| User Guide          | MkDocs site (deployed via CI)           |
| Training            | 1 workshop + 10 internal staff handover |

---

## 14 — Next Steps for Dev Team

1. **Bootstrap repo** using this structure.
2. Configure **Poetry**, **ESLint**, **black/ruff**, **pre-commit hooks**.
3. Implement minimal FastAPI endpoint `/health` + frontend ping page.
4. Add **OIDC login flow** using enacit4r-auth.
5. Create **CI pipeline** skeleton (GitHub Actions YAML).
6. Deliver **first milestone (M1)**: Auth + CRUD for Labs + Dashboard stub.
