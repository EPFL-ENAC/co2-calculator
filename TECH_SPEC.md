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
* **Package manager / dependency tool:** **UV** (recommended) — explanation below
* **Container runtime:** OCI-compliant images (Docker / buildx)

### Infrastructure & ops

* **Local dev / small deployment:** docker-compose with Traefik for reverse proxy / routing (to support Ansible-driven flows)
* **Production:** Kubernetes manifests (Helm optional), **nginx-ingress** in k8s as ingress controller (as requested)
* **Reverse proxy / TLS:** nginx-ingress (k8s); Traefik for compose/dev.
* **Cache / ephemeral store / broker:** **Redis** (recommended) — details & tradeoffs below
* **Background jobs:** Celery + Redis
* **Observability:** Prometheus (metrics), Grafana (dashboards), OpenTelemetry traces, ELK or fluentd/Vector for logs (forwarded to EPFL SIEM)
* **Secrets management:** Kubernetes Secrets in k8s + sealed-secrets / HashiCorp Vault for production; env vars locally with Dynaconf/.env
* **CI/CD:** GitHub Actions or GitLab CI (pipeline: lint, test, build images, scan, push registry, deploy to staging/prod)
* **Container registry:** public or EPFL-approved registry (OCI-compliant).
