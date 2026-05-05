---
status: delivered
last_updated: 2026-05-05
summary: Code Requirements Document — single source of truth for project scope and decisions.
---

# CRD — co2-calculator (Code Requirements Document)

This document fixes the project's intent, scope, and decision trail. Treat it as authoritative when other docs disagree.

## 1. WHY — the business problem

EPFL labs must report annual CO2 emissions across travel, infrastructure, equipment, purchases, and shared services. Spreadsheets do not scale, hide assumptions, and cannot be audited.

The co2-calculator gives each lab a single, secure, multilingual web app to enter activity data, apply curated emission factors, and produce auditable footprints. Other academic institutions must be able to reuse the codebase.

## 2. WHAT — scope

**In-scope deliverables.**

- Custom web application matching EPFL IT standards and branding.
- Modules: laboratory profile, professional travel, infrastructure, equipment energy, purchases, internal services, results visualisation.
- Manual CSV import with validation; optional automated ingestion (lab energy, staff directory).
- Backoffice tooling: emission-factor management, job history, sync progress, audit logs, role and permission administration.
- REST API documented with OpenAPI; PDF and CSV exports.
- Docker-based deployment to the EPFL XaaS Kubernetes platform.

**Out-of-scope.**

- Real-time IoT ingestion of building meters.
- Public-facing emission dashboards beyond authenticated EPFL users.
- Financial accounting or scope-3 supply-chain analytics outside listed modules.
- AI-driven assumption inference (tracked as an optional future extension).

**Constraints.**

- EPFL IT and security standards (Annexe 8). HERMES project methodology.
- Production target: Q2 2026. Open-source under GPL-3.0.

## 3. HOW — high-level architecture

See [System Overview](02-system-overview.md) for the canonical diagrams (ingress, frontend pods, FastAPI backend, Celery workers, PostgreSQL, S3, Entra ID).

The stack is Vue 3 + Quasar on the frontend, FastAPI on the backend, Celery + Redis for async jobs, PostgreSQL behind PgBouncer for persistence, and EPFL S3 for object storage. Authentication runs through Microsoft Entra ID via OIDC.

## 4. Decisions trail

Each architecturally meaningful decision is captured as an ADR. Add a new ADR before changing any of these.

- [ADR-001 — Python package manager](../architecture-decision-records/001-python-package-manager.md)
- [ADR-002 — Frontend framework](../architecture-decision-records/002-frontend-framework.md)
- [ADR-003 — Backend framework](../architecture-decision-records/003-backend-framework.md)
- [ADR-004 — Database selection](../architecture-decision-records/004-database-selection.md)
- [ADR-005 — Authorization strategy](../architecture-decision-records/005-authorization-strategy.md)
- [ADR-010 — Background job processing](../architecture-decision-records/010-background-job-processing.md)
- [ADR-012 — JWT authentication strategy](../architecture-decision-records/012-jwt-authentication-strategy.md)
- [ADR-013 — Object storage strategy](../architecture-decision-records/013-object-storage-strategy.md)
- [ADR-014 — Security checklist](../architecture-decision-records/014-security-checklist.md)

ADRs 011 and 015 are reserved for in-flight decisions; link them here once their files land in `architecture-decision-records/`.

## 5. Roles

The system recognises four actor classes, mapped to Entra ID groups and faculty scopes.

- **Data-entry user** — lab member who records activity (travel, equipment, purchases) for their unit.
- **Validator** — lab manager (`Utilisateur·rice principal·e`) who reviews, corrects, and signs off annual data.
- **Backoffice operator** — `Gestionnaire Métier` who curates emission factors, runs imports, and audits cross-unit data; permissions scope to a sub-perimeter (see issue #459).
- **Admin** — `Gestionnaire IT` with full operational access: user roles, system jobs, retention, and platform configuration.

Role assignment and faculty filtering are enforced server-side; see [ADR-005](../architecture-decision-records/005-authorization-strategy.md).

## 6. Data integration

**Inputs.**

- User-entered forms per module.
- CSV uploads validated against schemas; rejected rows surface as actionable errors.
- Curated emission-factor datasets (ADEME, DEFRA, custom) ingested via background jobs.
- EPFL Accred for user–unit linkage; staff directory for headcount.

**Outputs.**

- REST/JSON API for the SPA and external consumers (OpenAPI documented).
- PDF and CSV exports of footprints and breakdowns.
- Externalised application logs with 1–10 year retention.

## 7. Source of truth

When in doubt, this CRD wins. For deeper detail follow these links.

- Implementation plans index: <https://github.com/epfl-enac/co2-calculator/tree/main/docs/implementation-plans>
- Glossary: <https://github.com/epfl-enac/co2-calculator/blob/main/docs/src/glossary.md>
- LLM agent guide: <https://github.com/epfl-enac/co2-calculator/blob/main/docs/src/llm-agent.md>
- Architecture entry points: [Purpose & Scope](01-purpose-scope.md), [System Overview](02-system-overview.md), [ADR index](../architecture-decision-records/index.md).
