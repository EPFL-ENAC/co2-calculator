---
status: delivered
last_updated: 2026-05-05
summary: Landing page for co2-calculator developer documentation.
---

# co2-calculator developer docs

co2-calculator is an EPFL open-source web app that lets labs measure, visualise, and simulate their CO2 emissions; this site exists to keep maintenance cheap, onboard new contributors fast, and give LLM agents stable anchors for code navigation.

The docs cover product scope (the CRD/spec), system architecture and decision records, and per-stack guides for backend, frontend, database, and infrastructure.

## Start here — humans

- [Architecture overview](./architecture/index.md)
- [Frontend overview](./frontend/01-overview.md)
- [Backend overview](./backend/01-overview.md)

## Start here — LLM agents

- [CRD / spec](./architecture/spec.md)
- [ADR index](./architecture-decision-records/index.md)
- [Implementation plans](./implementation-plans/INDEX.md)

## How decisions are made

Architectural decisions live in `architecture-decision-records/`; each ADR captures context, options, and consequences.
The CRD is `architecture/spec.md` — the authoritative product requirement.
Issue-scoped delivery detail lives in `docs/src/implementation-plans/` (one file per GitHub issue), browsable in the [Implementation Plans](./implementation-plans/INDEX.md) nav section.
