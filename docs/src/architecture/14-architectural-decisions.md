# Architectural Decisions

This document indexes major architectural decisions made during
CO2 Calculator development. Each decision is captured in an
Architecture Decision Record (ADR) with context, alternatives,
and consequences.

## What Are ADRs?

ADRs document **why** decisions were made, **what** alternatives
were considered, and **when** they occurred. They help teams
understand trade-offs and avoid revisiting settled questions.

Each ADR follows a consistent structure:

1. **Title** - Short descriptive phrase (e.g., "Use FastAPI")
2. **Status** - Current state (see legend below)
3. **Context** - Problem or need driving the decision
4. **Decision** - What we chose and why
5. **Consequences** - Trade-offs and implications

## Status Legend

- ✅ **Accepted** - Decision made, implemented, and in use
- 📋 **Planned** - Under consideration or approved for implementation
- ⚠️ **Deprecated** - No longer in effect (kept for historical context)
- 🔄 **Superseded** - Replaced by newer decision (links to successor)

## Active Decisions

### Technology Stack

| ADR                                                                   | Decision                     | Status      | Key Rationale                             |
| --------------------------------------------------------------------- | ---------------------------- | ----------- | ----------------------------------------- |
| [001](../architecture-decision-records/001-python-package-manager.md) | Use uv for Python packages   | ✅ Accepted | 10-100x faster than pip, lock files       |
| [002](../architecture-decision-records/002-frontend-framework.md)     | Use Vue 3 + Quasar           | ✅ Accepted | Team expertise, rapid development         |
| [003](../architecture-decision-records/003-backend-framework.md)      | Use FastAPI                  | ✅ Accepted | Async-native, automatic docs, type safety |
| [004](../architecture-decision-records/004-database-selection.md)     | PostgreSQL + SQLite fallback | ✅ Accepted | ACID compliance, zero-config dev          |

### Security & Authorization

| ADR                                                                        | Decision                 | Status      | Key Rationale                  |
| -------------------------------------------------------------------------- | ------------------------ | ----------- | ------------------------------ |
| [005](../architecture-decision-records/005-authorization-strategy.md)      | In-code RBAC, reject OPA | ✅ Accepted | Simpler, sufficient for needs  |
| [012](../architecture-decision-records/012-jwt-authentication-strategy.md) | JWT-based authentication | ✅ Accepted | Stateless, microservices-ready |

### Infrastructure

| ADR                                                                    | Decision                      | Status     | Key Rationale                  |
| ---------------------------------------------------------------------- | ----------------------------- | ---------- | ------------------------------ |
| [013](../architecture-decision-records/013-object-storage-strategy.md) | Local filesystem, S3 optional | 📋 Planned | Zero-config dev, scalable prod |

## Planned Decisions

| ADR                                                                      | Topic               | Status     | Notes                                      |
| ------------------------------------------------------------------------ | ------------------- | ---------- | ------------------------------------------ |
| 008                                                                      | Observability Stack | 📋 Planned | Prometheus + Grafana + OpenTelemetry       |
| 009                                                                      | Caching Strategy    | 📋 Planned | Redis for emissions factors, rate limiting |
| [010](../architecture-decision-records/010-background-job-processing.md) | Background Jobs     | 📋 Planned | Celery + Redis preferred                   |
| 011                                                                      | OIDC Integration    | 📋 Planned | MS Entra ID for EPFL SSO                   |

## Rejected Alternatives

| Alternative       | Rejected Because                     | See ADR                                                               |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------- |
| Open Policy Agent | Too complex, operational overhead    | [005](../architecture-decision-records/005-authorization-strategy.md) |
| Django + DRF      | Slower, sync-first, more boilerplate | [003](../architecture-decision-records/003-backend-framework.md)      |
| React             | Team less familiar, larger bundles   | [002](../architecture-decision-records/002-frontend-framework.md)     |
| Poetry            | Slower than uv, non-standard format  | [001](../architecture-decision-records/001-python-package-manager.md) |

## Contributing New ADRs

When making a significant architectural decision:

1. **Create new ADR** in `architecture-decision-records/` (use next number)
2. **Follow the 5-part structure**: Status, Context, Decision, Alternatives, Consequences
3. **Keep concise** - aim for 40-60 lines (under 80 lines max)
4. **Add to this index** in the appropriate table
5. **Link from Tech Stack** document if relevant
6. **Submit with related code** changes in same PR

**What qualifies as an ADR?** Technology choices, architectural
patterns, security models, infrastructure decisions, or any
choice that impacts multiple systems or is hard to reverse.

## References

- [Tech Stack Specification](./08-tech-stack.md) - Implementation details
- [ADR Methodology](https://adr.github.io/) - Best practices and examples

---

**Last Updated**: 2025-11-11  
**Readable in**: ~5 minutes
