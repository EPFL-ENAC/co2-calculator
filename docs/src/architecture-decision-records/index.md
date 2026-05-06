# Architecture Decision Records (ADRs)

This is the **complete index** of all architectural decisions made
during CO2 Calculator development. Each ADR documents the context,
alternatives considered, and consequences of significant technical
choices.

## What Are ADRs?

Architecture Decision Records capture important architectural decisions
along with their context, alternatives considered, and consequences.
They serve as historical documentation and help future developers
understand why certain choices were made.

## Status Legend

- ✅ **Accepted** - Decision made, implemented, and in use
- 📋 **Planned** - Under consideration or approved for implementation
- ⚠️ **Deprecated** - No longer in effect (kept for historical context)
- 🔄 **Superseded** - Replaced by newer decision (links to successor)

## Active Decisions

### Technology Stack

| ADR                                        | Decision                     | Status      | Key Rationale                             |
| ------------------------------------------ | ---------------------------- | ----------- | ----------------------------------------- |
| [ADR-001](./001-python-package-manager.md) | Use uv for Python packages   | ✅ Accepted | 10-100x faster than pip, lock files       |
| [ADR-002](./002-frontend-framework.md)     | Use Vue 3 + Quasar           | ✅ Accepted | Team expertise, rapid development         |
| [ADR-003](./003-backend-framework.md)      | Use FastAPI                  | ✅ Accepted | Async-native, automatic docs, type safety |
| [ADR-004](./004-database-selection.md)     | PostgreSQL + SQLite fallback | ✅ Accepted | ACID compliance, zero-config dev          |

### Security & Authorization

| ADR                                             | Decision                 | Status      | Key Rationale                  |
| ----------------------------------------------- | ------------------------ | ----------- | ------------------------------ |
| [ADR-005](./005-authorization-strategy.md)      | In-code RBAC, reject OPA | ✅ Accepted | Simpler, sufficient for needs  |
| [ADR-012](./012-jwt-authentication-strategy.md) | JWT-based authentication | ✅ Accepted | Stateless, microservices-ready |
| [ADR-014](./014-security-checklist.md)          | Security checklist       | ✅ Accepted | Security maintenance plan      |

### Infrastructure & Operations

| ADR                                                   | Decision                                   | Status                                                       | Key Rationale                                                                  |
| ----------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| [ADR-010](./010-background-job-processing.md)         | In-process asyncio + 10s safety-net poller | ✅ Accepted                                                  | No new infra; Celery deferred                                                  |
| [ADR-013](./013-object-storage-strategy.md)           | Local filesystem, S3 optional              | 📋 Planned                                                   | Zero-config dev, scalable prod                                                 |
| [ADR-015](./015-claim-job-atomic-state-is-current.md) | Atomic claim_job on (state, is_current)    | ✅ Accepted                                                  | Closes pod-collision race                                                      |
| [ADR-016](./016-pipeline-two-path-principle.md)       | Two-path principle (interactive vs bulk)   | ✅ Accepted (principle); ownership split partially delivered | Single-writer-per-path is the target; stats today still inline in legacy paths |

### Data Pipeline

| ADR                                                 | Decision                                                               | Status      | Key Rationale                                                             |
| --------------------------------------------------- | ---------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------- |
| [ADR-011](./011-factor-classification-jsonb.md)     | factors.classification → JSONB                                         | ✅ Accepted | Deterministic key order, real uniqueness                                  |
| [ADR-018](./018-factor-csv-delete-before-insert.md) | Factor CSV idempotency (upsert in prod, delete-before-insert in seeds) | ✅ Accepted | Production: upsert + last_seen_job_id; seeds: scoped delete-before-insert |

### Auth & Identity

| ADR                                             | Decision                              | Status      | Key Rationale                         |
| ----------------------------------------------- | ------------------------------------- | ----------- | ------------------------------------- |
| [ADR-017](./017-me-endpoint-async-role-sync.md) | /me pure DB read; /refresh async sync | ✅ Accepted | ~8ms /me; eventual 15-min consistency |

## Planned Decisions

| ADR | Topic               | Status     | Notes                                      |
| --- | ------------------- | ---------- | ------------------------------------------ |
| 008 | Observability Stack | 📋 Planned | Prometheus + Grafana + OpenTelemetry       |
| 009 | Caching Strategy    | 📋 Planned | Redis for emissions factors, rate limiting |
| 019 | OIDC Integration    | 📋 Planned | MS Entra ID for EPFL SSO                   |

## Rejected Alternatives

| Alternative       | Rejected Because                     | See ADR                                    |
| ----------------- | ------------------------------------ | ------------------------------------------ |
| Open Policy Agent | Too complex, operational overhead    | [ADR-005](./005-authorization-strategy.md) |
| Django + DRF      | Slower, sync-first, more boilerplate | [ADR-003](./003-backend-framework.md)      |
| React             | Team less familiar, larger bundles   | [ADR-002](./002-frontend-framework.md)     |
| Poetry            | Slower than uv, non-standard format  | [ADR-001](./001-python-package-manager.md) |

## ADR Format

Each ADR follows this structure:

1. **Title** - Short descriptive phrase
2. **Status** - Proposed, Accepted, Deprecated, Superseded
3. **Context** - The issue motivating this decision
4. **Decision** - The change we're proposing or agreed to
5. **Consequences** - The resulting context after applying

## Creating New ADRs

When making a significant architectural decision:

1. **Create new ADR** in this directory using next sequential number (e.g., ADR-014)
2. **Follow the 5-part structure** above
3. **Keep concise** - aim for 40-60 lines (under 80 lines max)
4. **Update this index** - add entry to appropriate table above
5. **Submit with related code** changes in same PR

**What qualifies as an ADR?** Technology choices, architectural
patterns, security models, infrastructure decisions, or any
choice that impacts multiple systems or is hard to reverse.

**Not an ADR**: Routine implementation details, bug fixes, or
small refactorings.

## Additional Resources

- [Architectural Decisions Overview](../architecture/14-architectural-decisions.md) - Why we use ADRs
- [Tech Stack Documentation](../architecture/08-tech-stack.md) - Current technology stack
- [ADR Methodology](https://adr.github.io/) - Best practices and examples

---

**Last Updated**: 2026-05-05
