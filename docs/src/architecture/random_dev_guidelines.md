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
