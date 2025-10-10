## **we target Python 3.13 at runtime**

# Tech Stack Specification — Calculateur CO2@EPFL

**Audience:** Lead dev / Architects / Dev team
**Date:** 2025-10-06
**Last Update:** 2015-10-7
**Status:** Proposal / RFC

---

## 1 — High-level constraints & goals

- Must comply with EPFL IT standards (OIDC / OAuth2 support, logging, monitoring, container images, security, backups, SIEM, etc.).
- Open-source; EPFL owns the code.
- Web application (responsive).
- Containerised, deployable via **docker-compose** (local/Ansible flow) and **Kubernetes** (production).
- Stateless app design; horizontally scalable.
- Primary DB: **Postgres**. **TBD**
- Authentication via EPFL Identity (MS Entra / OIDC), pluggable for other institutions (oidc/openid)

---

## 2 — Summary of selected stack (short)

### Frontend

- **Package manager:** npm
- **Bundler / dev server:** Vite
- **Framework / UI:** Vue 3 + Quasar
- **State management:** Pinia
- **Router / i18n:** vue-router, vue-i18n
- **Charts:** eCharts
- **Markdown rendering:** marked

### Backend

- **Language / runtime:** Python **3.13** (target runtime)
- **Web framework:** FastAPI
- **ASGI server:** Uvicorn
- **DB driver & ORM:** asyncpg (async driver) + SQLAlchemy (async) + Alembic for migrations;
- **Config / env:** Dynaconf + python-dotenv (cli extras)
- **EPFL helpers:** enacit4r-files, enacit4r-auth, enacit4r-sql
- **Package manager / dependency tool:** **UV**
- **Container runtime:** OCI-compliant images (Docker / buildx)

### Infrastructure & ops

- **Makefile**: Use Makefile for entrypoint
- **Local dev / small deployment:** docker-compose with Traefik for reverse proxy / routing (to support Ansible-driven flows)
- **Production:** Kubernetes manifests (Helm optional), **nginx-ingress** in k8s as ingress controller (as requested)
- **Reverse proxy / TLS:** nginx-ingress (k8s); Traefik for compose/dev.
- **Background jobs:** Celery + Redis
- **Observability:** Prometheus (metrics), Grafana (dashboards), OpenTelemetry traces, (forwarded to EPFL SIEM)
- **Secrets management:** Kubernetes Secrets in k8s / for production; env vars locally with Dynaconf/.env
- **CI/CD:** GitHub Actions or GitLab CI (pipeline: lint, test, build images, scan, push public registry, deploy to staging/prod)
- **Container registry:** public: ghcr.io
