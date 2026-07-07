---
status: proposed
issue: 1556
last_updated: 2026-07-07
title: "Simulation module — backend scope"
summary: "Placeholder for the backend half of the Simulator module; blocked on open questions in the #1555/#404 plan."
---

# Simulation module — backend scope

## Problem

Issue body is empty; this is the backend-scope placeholder for the Simulator module spec'd in issue #1555/#404 (lets authenticated users estimate a project's carbon footprint by reusing reference-year data with per-module % overrides).

## Design

No backend design exists yet for this module — there is no `simulation`/`simulator` code in `backend/` today. The frontend spec's front/backend split isn't even decided. Backend scope should be derived once `docs/src/implementation-plans/404-simulation-module-plan.md` (from #1555) resolves its open questions on front/backend split and per-module breakout. Do not speculate about tables or endpoints here.

## Steps

- [ ] Wait on #1555/#404 plan to resolve its open questions (front/backend split, per-module override breakout)
- [ ] Once resolved, scope backend data model + endpoints in this document
