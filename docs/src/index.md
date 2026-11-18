---
status: delivered
last_updated: 2026-11-18
summary: Landing page for co2-calculator developer documentation.
---

# co2-calculator developer docs

co2-calculator is an open-source web app from EPFL. Labs use it to
measure, show and simulate their CO2 emissions. This site keeps the
maintenance cheap, helps new contributors start fast, and gives LLM
agents stable anchors in the code.

The docs cover the product scope (the CRD, or spec), the system
architecture and the decision records. Each part has a guide: backend,
frontend, database and infrastructure.

## Something is broken?

- [Operations](./infra/04-operations.md): where to look, who to call,
  what to expect
- [Tools and access](./infra/05-tools-and-access.md): each dashboard
  and how to get access

## Install it

- [Install the CO2 Calculator](./infra/install.md): Docker Compose or
  Skaffold on one machine, the Helm chart or Kustomize on Kubernetes

## Start here: humans

- [Architecture overview](./architecture/index.md)
- [Frontend overview](./frontend/01-overview.md)
- [Backend overview](./backend/01-overview.md)

## Start here: LLM agents

- [CRD / spec](./architecture/spec.md)
- [ADR index](./architecture-decision-records/index.md)
- [Implementation plans](./implementation-plans/_index.md)

## How decisions are made

The architectural decisions are in `architecture-decision-records/`.
Each ADR (architecture decision record) gives the context, the options
and the consequences. The CRD in `architecture/spec.md` is the product
requirement that has authority. The delivery detail of each GitHub
issue is in `docs/src/implementation-plans/`, one file for each issue.
The [Implementation Plans](./implementation-plans/_index.md) section of
the menu lists them.
