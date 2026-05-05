---
status: delivered
last_updated: 2026-05-05
summary: Alphabetical glossary of project-specific terms used across the co2-calculator codebase and docs.
---

# Glossary

Project-specific terms. For industry-wide acronyms (REST, JWT, OIDC), see
the relevant ADR or external reference.

**Activity** — A unit of measured work that emits CO2 (a flight, a kWh of
lab power, a kg of purchased material). Multiplied by an emission factor.

**ADR (Architecture Decision Record)** — A dated record of one accepted
architectural decision. See
[`architecture-decision-records/`](./architecture-decision-records/index.md).

**Affiliation** — A user's link to one or more EPFL units, sourced from
Accred. Scopes what backoffice users may view or edit (issue #459).

**Backoffice** — The administrative surface: user management, factor
management, audit, ingestion. Permissions live under `backoffice.*`. See
[`backend/07-DEVELOPER-GUIDE-PERMISSIONS.md`](./backend/07-DEVELOPER-GUIDE-PERMISSIONS.md).

**`claim_job`** — Atomic SQL operation that flips a job from
`NOT_STARTED` to `RUNNING` and sets `is_current=TRUE` in one transaction.
Pod-collision losers lose the UPDATE, not the data. See ADR-010, ADR-015.

**CRD (Customer Requirements Document)** — The mandate spec at
[`architecture/spec.md`](./architecture/spec.md). Top of the
source-of-truth hierarchy.

**Data-entry user** — Role that submits activity data for a unit. Distinct
from validators and backoffice operators. See ADR-005.

**Emission factor** — Coefficient mapping an activity quantity to
kg CO2-eq. Versioned by year and scope; ingested via the factor pipeline.

**Factor pipeline** — Bulk import and normalization workflow that ingests
CSV factor sources into canonical factor tables and triggers
recalculation. See
[`310-b-factor-pipeline.md`](https://github.com/epfl-enac/co2-calculator/blob/main/docs/src/implementation-plans/310-b-factor-pipeline.md).

**GHG Protocol** — The Greenhouse Gas Protocol, the international
emissions accounting standard. Defines Scope 1, 2, and 3.

**`/me`** — `GET /api/v1/auth/me`. Returns the cached user profile, roles,
and computed permissions in ~8 ms. Does not trigger role sync. See
[`role-sync-architecture.md`](https://github.com/epfl-enac/co2-calculator/blob/main/docs/role-sync-architecture.md).

**Path 1 vs Path 2** — Operational paths in the bulk-job model. Path 1 is
per-request work for a single user. Path 2 is bulk operator workflows
(CSV ingest, factor sync, recalc). See ADR-010.

**Recalc** — Re-running emission computations after a factor change or
classification fix. Triggered automatically when factor pipelines deliver
new versions. See plan 310b.

**`/refresh`** — Endpoint that triggers a background role sync from
Entra/Accred and returns immediately. Pair with `/me` to read the result.
See [`role-sync-architecture.md`](https://github.com/epfl-enac/co2-calculator/blob/main/docs/role-sync-architecture.md).

**Role sync** — Background process that reconciles a user's roles and
affiliations from the upstream identity provider into the local DB.
Tracked via `last_roles_sync_at`. See ADR-012.

**Scope 1 / 2 / 3** — GHG Protocol categories. Scope 1: direct emissions
(on-site combustion). Scope 2: purchased energy. Scope 3: all other
indirect emissions (travel, purchases, services).

**Validator** — Role that approves submitted data before it counts toward
published totals. Sits between data-entry users and backoffice operators
in the permission hierarchy. See ADR-005.
