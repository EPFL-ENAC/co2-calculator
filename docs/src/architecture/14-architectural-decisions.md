# Architectural Decisions

This document provides an overview of how we document architectural
decisions in the CO2 Calculator project. For the complete index of
all decisions, see the [Architecture Decision Records](../architecture-decision-records/index.md)
section.

## What Are ADRs?

Architecture Decision Records (ADRs) document **why** decisions were
made, **what** alternatives were considered, and **when** they occurred.
They help teams understand trade-offs and avoid revisiting settled questions.

Each ADR follows a consistent structure:

1. **Title** - Short descriptive phrase (e.g., "Use FastAPI")
2. **Status** - Current state (Accepted, Planned, Deprecated, Superseded)
3. **Context** - Problem or need driving the decision
4. **Decision** - What we chose and why
5. **Consequences** - Trade-offs and implications

## Why Document Decisions?

ADRs serve multiple purposes:

- **Onboarding** - New team members understand why the system is built this way
- **Consistency** - Prevents rehashing settled debates
- **Context preservation** - Captures reasoning that might otherwise be lost
- **Accountability** - Makes trade-offs explicit and reviewable

## Decision Categories

We organize ADRs into several categories:

- **Technology Stack** - Languages, frameworks, libraries
- **Security & Authorization** - Authentication, authorization, data protection
- **Infrastructure** - Deployment, storage, networking
- **Architecture Patterns** - System design, communication patterns

## Quick Reference

For a comprehensive list of all decisions with status indicators,
rationale summaries, and rejected alternatives, see:

**→ [Complete ADR Index](../architecture-decision-records/index.md)**

Key decisions include:

- Python package management (uv vs pip/poetry)
- Frontend framework (Vue 3 + Quasar)
- Backend framework (FastAPI)
- Database selection (PostgreSQL + SQLite)
- Authorization strategy (in-code RBAC vs OPA)
- Authentication approach (JWT-based)

## Contributing New ADRs

When making a significant architectural decision:

1. **Create new ADR** in `architecture-decision-records/` (use next number)
2. **Follow the 5-part structure** listed above
3. **Keep concise** - aim for 40-60 lines (under 80 lines max)
4. **Update the [ADR Index](../architecture-decision-records/index.md)**
5. **Link from Tech Stack** document if relevant
6. **Submit with related code** changes in same PR

**What qualifies as an ADR?** Technology choices, architectural
patterns, security models, infrastructure decisions, or any
choice that impacts multiple systems or is hard to reverse.

**Not an ADR**: Routine implementation details, bug fixes, or
small refactorings.

## References

- **[Complete ADR Index](../architecture-decision-records/index.md)** - Full list with status and rationale
- [Tech Stack Specification](./08-tech-stack.md) - Implementation details
- [ADR Methodology](https://adr.github.io/) - Best practices and examples

---

**Last Updated**: 2025-11-11  
**Readable in**: ~2 minutes
