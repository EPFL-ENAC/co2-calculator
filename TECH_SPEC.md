**we target Python 3.13 at runtime** 
---

# Tech Stack Specification — Calculateur CO2@EPFL

**Audience:** Lead dev / Architects / Dev team
**Date:** 2025-10-06 (EPFL timezone)
**Status:** Proposal / RFC

---

## 1 — High-level constraints & goals

* Must comply with EPFL IT standards (OIDC / OAuth2 support, logging, monitoring, container images, security, backups, SIEM, etc.).
* Open-source; EPFL owns the code.
* Web application (responsive).
* Containerised, deployable via **docker-compose** (local/Ansible flow) and **Kubernetes** (production).
* Stateless app design; horizontally scalable.
* Primary DB: **Postgres**.
* Authentication via EPFL Identity (MS Entra / OIDC), pluggable for other institutions.
* Target production milestone: Q2 2026 (from cahier des charges).

---

## 2 — Summary of selected stack (short)

### Frontend

* **Package manager:** npm (as requested)
* **Bundler / dev server:** Vite
* **Framework / UI:** Vue 3 + Quasar
* **State management:** Pinia
* **Router / i18n:** vue-router, vue-i18n
* **Charts:** eCharts
* **Markdown rendering:** marked (v9.0.3 as provided)

### Backend

* **Language / runtime:** Python **3.13** (target runtime)
* **Web framework:** FastAPI
* **ASGI server:** Uvicorn (worker in production under Gunicorn or using Uvicorn + Gunicorn wrapper)
* **DB driver & ORM:** asyncpg (async driver) + SQLAlchemy (async) + Alembic for migrations; psycopg2 available for tooling/legacy scripts
* **Config / env:** Dynaconf + python-dotenv (cli extras)
* **EPFL helpers:** enacit4r-files, enacit4r-auth, enacit4r-sql (git refs provided)
* **Package manager / dependency tool:** **Poetry** (recommended) — explanation below
* **Container runtime:** OCI-compliant images (Docker / buildx)

### Infrastructure & ops

* **Local dev / small deployment:** docker-compose with Traefik for reverse proxy / routing (to support Ansible-driven flows)
* **Production:** Kubernetes manifests (Helm optional), **nginx-ingress** in k8s as ingress controller (as requested)
* **Reverse proxy / TLS:** nginx-ingress (k8s); Traefik for compose/dev.
* **Cache / ephemeral store / broker:** **Redis** (recommended) — details & tradeoffs below
* **Background jobs:** Celery / Dramatiq / RQ (broker: Redis) — chosen pattern explained later
* **Observability:** Prometheus (metrics), Grafana (dashboards), OpenTelemetry traces, ELK or fluentd/Vector for logs (forwarded to EPFL SIEM)
* **Secrets management:** Kubernetes Secrets in k8s + sealed-secrets / HashiCorp Vault for production; env vars locally with Dynaconf/.env
* **CI/CD:** GitHub Actions or GitLab CI (pipeline: lint, test, build images, scan, push registry, deploy to staging/prod)
* **Container registry:** public or EPFL-approved registry (OCI-compliant).

---

## 3 — Full rationale & detailed choices

### 3.1 Frontend choices (why)

* **npm**: EPFL/industry standard; broad ecosystem; works seamlessly with Vite/Quasar.
* **Vite**: lightning-fast dev server, HMR, small build overhead — ideal for Vue 3 modern stack and faster iteration. Supports SSR or SPA if needed later.
* **Vue 3**: requested; stable, reactive composition API, good developer ergonomics; excellent TypeScript support if needed.
* **Quasar**: component library + layout scaffolding + built-in PWA, i18n-friendly and speeds UI development; fits EPFL need for quick, consistent UI with themable design.
* **Pinia**: modern, lightweight state management for Vue 3; easier to reason about than Vuex; integrates with devtools.
* **eCharts**: powerful, rich charts; good for complex visualizations required by CO2 dashboards. It handles large datasets and interactive charts.
* **vue-i18n**: EPFL needs multiple languages; this is a standard, robust solution.
* **marked**: lightweight markdown renderer; v9 is modern and secure when used with proper sanitization (explain sanitization below).

**Security & accessibility notes for frontend**

* Sanitize any Markdown output (use DOMPurify or similar) before rendering to avoid XSS.
* Implement CSP headers via backend / ingress to reduce client-side risk.
* Ensure accessibility (a11y) — Quasar helps but audits required.

---

### 3.2 Backend choices (why)

* **Python 3.13 runtime**: latest supported stable release increases performance and typing improvements. You listed `python = "^3.10"` in dependencies; that shows compatibility with 3.10+, so selecting 3.13 as runtime keeps compatibility while giving performance/security improvements. If a strict constraint demands 3.10 only, we can downgrade.
* **FastAPI**: excellent async performance, automatic OpenAPI generation (required), good typing and developer speed, plays well with Uvicorn + asyncpg. It also produces clear, machine-readable API docs (Swagger) the cahier requires.
* **Uvicorn** (ASGI server): lightweight, async; production run either with Gunicorn + Uvicorn workers or using Uvicorn and process manager. The list included `uvicorn`.
* **asyncpg**: async Postgres driver with great performance for coroutine-based stack. Use with SQLAlchemy (1.4+ async ORM) or with a lean SQL layer like `databases` if preferred. You included `enacit4r-sql` so integrate with that.
* **psycopg2**: kept for CLI / tooling that prefer sync driver.
* **Alembic**: migrations management standard for SQLAlchemy.
* **Dynaconf + python-dotenv**: structured config that supports env vars, multiple environments; Dynaconf integrates well with Docker/K8s patterns.
* **EPFL enacit4r-* packages**: reuse EPFL-specific helpers (files, auth, sql). Pin exact git revisions for reproducibility.
* **Poetry (recommended)** as package manager: produces lockfile, reproducible installs, good support for building wheels and publishing, great dev experience. It also handles Python dependency resolution and can output `requirements.txt` for docker builds. (If EPFL requires pip-tools / pip, we can easily provide a `requirements.txt` from Poetry).

  * *Why not pip alone?* Pip doesn't produce a lockfile by default; Poetry gives locked, reproducible builds. This is important in production.

**Security & standards**

* Implement JWT/OIDC integration with MS Entra ID using a dedicated module (enacit4r-auth or standard libraries such as `python-jose`, `authlib` or `fastapi_oidc`). Provide an auth module that maps Entra group claims to application roles.
* Auth integration should be a pluggable adapter so the app can be used by other universities without Entra (e.g., simple OAuth2 provider or local SAML plugin).
* Logging structured as JSON (logfmt or JSON) to feed EPFL SIEM. Include request IDs, user GUIDs (where allowed), timestamps, severity, and event types.
* Security scanning: SAST (Bandit/semgrep), dependency scan (safety, Dependabot or GitHub Dependabot), container scanning (Trivy).

---

### 3.3 Data & caching — Redis decision

**Do we need Redis?** — **Recommendation: Yes (recommended)**

**Why Redis is recommended**

* **Cache emission factors** and static lookups (e.g., NACRES mapping, factor sets) to reduce DB queries and speed dashboard loads during peak (February annual load).
* **Rate limiting** (per-user or per-IP) implemented in Redis is standard and helps protect from abusive loads.
* **Short-lived sessions / token revocation lists**: If we use JWTs, sessions are stateless but JWT revocation (logout / forced logout) requires a store. Redis is the natural choice.
* **Background job broker**: Celery/RQ require a broker—Redis is also commonly used here.
* **Feature flags & ephemeral storage**: Redis is handy for locks, counters, and concurrency control.

**Costs & trade-offs**

* Adds operational complexity (another service to manage).
* If you *must* minimize infrastructure and you accept eventual longer response times and no revocation capability, you could omit Redis initially and rely completely on database caching + CDN. But given the expected annual spikes, using Redis early reduces DB load and is safer.

**Conclusion:** Include Redis as an optional-but-highly-recommended service in all environments (dev: single container, staging/prod: managed Redis instance or k8s operator). Use Redis for caching, rate limits, and the job broker.

---

### 3.4 Background processing

* **Option A (recommended):** Celery with Redis broker + Redis result backend. Mature, widely-known.
* **Option B:** Dramatiq (simpler and modern) with Redis.
* **Option C:** RQ (lightweight) if needs are very simple.

**Recommendation:** Celery for max flexibility (scheduling, retries, priorities). Use it for heavy tasks: ingest CSVs, long-running factor recalculations, export generation (PDF), and optionally for auto-ingestion jobs.

---

### 3.5 Session & auth flow

* **Primary:** OIDC login via MS Entra ID (EPFL). Use OIDC provider to receive id_token + access_token. Validate tokens server-side (signature, audience, expiry) using `python-jose` or `authlib`. Map Entra claims / groups to app roles (Gestionnaire IT, Gestionnaire Métier, etc.).
* **Statelessness:** Use JWTs for session tokens to stay stateless and scale horizontally. Keep token lifetime short and use refresh tokens if necessary.
* **Revocation / logout:** Implement token revocation via Redis blacklist (recommended). Without Redis, revocation is hard.
* **Pluggable module:** Build auth adapter interface so the auth layer can be swapped for other IDM (SAML2) for non-Entra institutions.

---

### 3.6 Database & data model notes

* **Postgres** (primary). Use schemas for separation (e.g., `public`, `audit`, `analytics`) if desired.
* **Connection pooling:** Use `asyncpg` with built-in pool, configure pool size according to pod/worker counts; use PgBouncer if high concurrency is expected.
* **Migrations:** Alembic. Keep migration scripts in repo; enforce code review on migrations.
* **Backups:** Conform to EPFL backup policy — automated backups, retention (align with cahier: results stored 10 years, some travel data 5 years). Store backups in EPFL-approved storage.
* **Audit logs:** All writes and important changes logged (who, when, what), and logs forwarded to SIEM.

---

### 3.7 Containerization & orchestration

* **Images:** OCI-compliant, small base images (python:3.13-slim or distroless) with multi-stage builds. EPFL requirement: support OS patching and updates.
* **docker-compose (dev / Ansible flows):**

  * Use Traefik as reverse proxy in compose for routing, TLS (Let’s Encrypt or cert manager for local certs), and for ease of Ansible-driven deployments.
  * Example services: web (backend), frontend (vite build served by CDN or static nginx), postgres, redis, minio (if object storage required), traefik, pgadmin (optional).
* **Kubernetes (prod):**

  * Use k8s manifests or Helm charts.
  * Use **nginx-ingress** controller (as requested) for production ingress. TLS managed with cert-manager.
  * Use Horizontal Pod Autoscaler (HPA) and resource requests/limits for autoscaling.
  * Readiness/liveness probes configured.
  * Use ephemeral storage for pods; persistent volumes only for Postgres (or use managed Postgres). For Redis prefer managed service or k8s operator.
  * Use PodDisruptionBudgets and anti-affinity rules across nodes.
  * Use liveness/readiness for worker pods (Celery) too.

---

### 3.8 Networking, proxies & TLS

* **k8s ingress:** nginx-ingress controller (EPFL standard) with cert-manager.
* **compose/ansible proxy:** Traefik — matches your Ansible/local flow request. Traefik provides automatic dynamic routing and supports Let's Encrypt, etc.
* **HTTP headers:** Set HSTS, CSP, X-Frame-Options, X-XSS-Protection, Referrer-Policy; enforced at ingress/proxy.
* **CORS:** Backend must implement strict CORS rules allowing only EPFL UIs / origins.

---

### 3.9 Observability & logging

* **Metrics:** Instrument FastAPI endpoints with Prometheus client; export `/metrics`. Frontend usage metrics via custom metrics pipeline (if allowed).
* **Tracing:** OpenTelemetry SDK to capture traces; send to collector, then to tracing backend (Jaeger/Tempo).
* **Logs:** Structured JSON logs from backend, forwarded to EPFL SIEM (ELK or SIEM HTTP ingest). Include correlation ID propagation across frontend/backend.
* **Dashboards:** Grafana dashboards for app & infra metrics; set alerts on errors, latency, job queue sizes, DB connection exhaustion.
* **Error reporting:** Sentry (or EPFL-approved alternative) for uncaught exceptions in backend and front-end.

---

### 3.10 Security & compliance

* **OWASP best practices:** Input validation, output escaping, CSRF protection where needed, secure cookies.
* **Dependency scanning:** GitHub/GitLab Dependabot + Snyk/Trivy.
* **Static analysis:** Bandit/semgrep in CI.
* **Secrets:** Use Vault or sealed-secrets; never store secrets in repo.
* **Penetration tests / audits:** EPFL may request an external security audit. Provide budget in options.
* **Data retention policy:** Implement app logic to purge/retain according to cahier (10 years, 5 years for travel). Ensure backups mirror retention rules.

---

## 4 — Developer ergonomics & repo structure (recommended)

Monorepo or two repos (frontend / backend). Suggested backend layout:

```
/backend
  /app
    main.py
    api/
    services/
    models/
    db/
    auth/
    core/  # config, logging, metrics
    workers/
    migrations/  # alembic
  pyproject.toml  # poetry
  Dockerfile
  tests/
```

Frontend layout: standard Vite + Quasar app with `src/components`, `src/pages`, `stores/` (pinia), `i18n/`, `charts/`.

---

## 5 — CI / CD pipeline (recommended)

* **Stages:** lint (ESLint + style), unit tests (pytest for backend, vitest/jest for frontend), security scans, build (docker images), push to registry, deploy to staging, run integration tests, promote to prod via manual approval.
* **Image signing:** optional but recommended for production compliance.
* **Canary / Blue/Green:** K8s deployments should allow safe rollouts (rolling update, canary via ingress weights).

---

## 6 — Example dev & prod Compose / k8s artifacts (short)

* **Docker Compose:** `docker-compose.yml` with services: backend, frontend(for dev), postgres, redis, traefik, minio (if needed). Traefik configured to route `api.local` -> backend, `app.local` -> frontend.
* **K8s:**

  * Deployment + Service for backend + HPA + ConfigMap for envs + Secret for keys.
  * Deployment for celery workers.
  * StatefulSet/Managed for Postgres (or external managed service).
  * Redis via operator or managed service.
  * Ingress resource using nginx-ingress controller.

*(I can produce concrete example `docker-compose.yml` and k8s manifests or Helm chart if you want — tell me which and I’ll generate.)*

---

## 7 — Performance, scaling & capacity planning

* **Stateless design**: backend pods can scale horizontally; no sticky sessions required.
* **Session strategy:** use JWTs (stateless) + Redis for revocation and short-lived state if needed.
* **DB scaling:** read replicas and connection pooling (PgBouncer) for heavy analytic queries. Use caches (Redis) for repeated factor lookups/aggregates.
* **Peak load (February):** pre-warm caches, increase replicas temporarily via HPA or manual scale; ensure Celery workers and DB sizing can support bulk CSV ingestion and report generation.

---

## 8 — Versioning & dependency pinning

* **Frontend deps**: use the versions you provided:

  * marked: ^9.0.3
  * pinia: ^3.0.1
  * quasar: ^2.18.1
  * vue: ^3.5.13
  * vue-i18n: ^11.1.7
  * vue-router: ^4.3.2
* **Backend deps**: pin the listed ones and exact git rev references you provided for enacit4r-* packages, alembic ^1.14.0, asyncpg ^0.30.0, psycopg2 ^2.9.10, dynaconf ^3.2.6, python-dotenv ^1.0.1. Use Poetry lock for reproducible builds.

---

## 9 — Final recommendations / next steps

1. **Accept runtime Python 3.13** (we used this in the spec). If EPFL infra forbids 3.13, revert to 3.10/3.11.
2. **Include Redis** in staging/prod (strongly recommended). Mark as optional in MVP but prepare code paths for it.
3. **Auth adapter**: create a dedicated module that handles OIDC/MS Entra and a fallback for other providers (SAML). Keep it pluggable.
4. **CI/CD + k8s manifests**: implement a GitOps pipeline or CI pipeline with staging/prod deployments. I can create sample GitHub Actions + Helm charts.
5. **Observability**: wire Prometheus + Grafana + OpenTelemetry early (debugging and capacity planning later).
6. **Security hygiene**: configure SAST & dependency scanning in CI before code freeze.

---

## 10 — Appendix: quick decision table

| Topic                     |                                                                 Decision |
| ------------------------- | -----------------------------------------------------------------------: |
| Python runtime            | **3.13** (target) — compatible with specified deps (they declare 3.10+). |
| Package manager (backend) |                **Poetry** (recommended for locks & reproducible builds). |
| Web framework             |                                                              **FastAPI** |
| ASGI server               |                            **Uvicorn** (with Gunicorn in prod if needed) |
| DB                        |                                                             **Postgres** |
| Cache / Broker            |                                                  **Redis** (recommended) |
| Background tasks          |                                                **Celery (Redis broker)** |
| Auth                      |                                  **OIDC / MS Entra** + pluggable adapter |
| Containers                |               OCI images, docker-compose (Traefik) & k8s (nginx-ingress) |
| Observability             |                             Prometheus, Grafana, OpenTelemetry, ELK/SIEM |

