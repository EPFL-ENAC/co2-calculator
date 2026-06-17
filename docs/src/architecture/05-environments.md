---
status: delivered
last_updated: 2026-06-16
summary: Environments, URLs and per-environment secrets and database configuration.
---

# Environments

The system runs on EPFL OpenShift, delivered by ArgoCD from the
`openshift-app-config` GitOps repo.

## Dev / Stage / Prod Topology

| Environment | URL                                   | Purpose                | Secrets Management       |
| ----------- | ------------------------------------- | ---------------------- | ------------------------ |
| Local       | http://localhost:3000                 | Individual development | `.env` files             |
| Development | https://co2-calculator-dev.epfl.ch/   | Team collaboration     | Infisical Operator       |
| Staging     | https://co2-calculator-stage.epfl.ch/ | Pre-release testing    | Manual OpenShift secrets |
| Production  | https://co2-calculator.epfl.ch/       | Live user traffic      | Manual OpenShift secrets |

Production (`co2-calculator.epfl.ch`) goes live with **v1.0.0
(2026-06-17)**; until then it serves as the pre-release/validation
instance. For local setup, see the [Development Guide](../frontend/01-overview.md).

## Secrets Management

- **Local** — `.env` files from `.env.example` templates (never committed); separate `backend/.env` and `frontend/.env`.
- **Dev** — the **Infisical Operator** generates the Kubernetes Secrets, injected as pod environment variables.
- **Stage / Prod** — currently **manually-managed OpenShift secrets**, because OpenShift is not yet wired to Infisical. **Azure Key Vault** is planned for production secrets (v1.0.0+).

## Database

A single **managed PostgreSQL** (EPFL DBaaS) per environment, reached over
`DB_URL`. Connection pooling is **in-process** (SQLAlchemy async) — there
is **no PgBouncer and no read replica**. A `db-dump` CronJob backs each
database up to the `db-dumps` PVC. Local development uses Postgres 18 in
Docker Compose.

## Background Jobs

Background jobs run in-process within the backend pods and scale with the
web replicas; there is no separate Redis/Celery tier (see
[ADR-010](../architecture-decision-records/010-background-job-processing.md)).

## Key Environment Variables

| Variable                                  | Purpose                                        | Required |
| ----------------------------------------- | ---------------------------------------------- | -------- |
| `DB_URL`                                  | PostgreSQL connection string                   | Yes      |
| `SECRET_KEY`                              | JWT signing key                                | Yes      |
| `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` | Entra ID / OIDC client credentials             | Yes      |
| `OAUTH_ISSUER_URL`                        | OIDC issuer (well-known config appended)       | Yes      |
| `S3_ENDPOINT_HOSTNAME` / `S3_BUCKET` / `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | EPFL S3 file storage (else local disk) | No |
| `APP_SENTRY_DSN`                          | GlitchTip/Sentry DSN (frontend errors)         | No       |
| `ENVIRONMENT`                             | Environment name                               | Yes      |

Complete lists live in the `.env.example` files.

For detailed infrastructure information, see [Infrastructure Documentation](../infra/01-overview.md).
