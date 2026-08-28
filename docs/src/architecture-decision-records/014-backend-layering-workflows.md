---
status: delivered
last_updated: 2026-08-28
summary: One-aggregate services and operation workflows that own their transactions; binds new code, existing service webs migrate opportunistically
---

# ADR-014: Backend Layering — One-Aggregate Services, Operation Workflows

**Status**: Accepted
**Date**: 2026-08-28
**Deciders**: Maintainer
**Related**: [it4r-agent-kit PR #2](https://github.com/EPFL-ENAC/it4r-agent-kit/pull/2)
(canonical rule text, vendored into
[`it4r-rules.md`](../contributing/it4r-rules.md)); incidents #2445, #2483;
plans `2445-plan-create-name-race.md`, `2449-plan-cascade-jobs.md`; issue
#2487.

## Context

The #2445/#2483 investigations exposed two structural gaps the old layering
rule did not cover:

1. **Hidden side-effect writes.** `CarbonReportService.create` lazily
   created the unit's Calculator project as a side effect of creating a
   report; explore's sandbox likewise. Nobody owned those rows' lifecycle,
   the frontend orchestrated existence via GET → 404 → POST, and the race
   loser surfaced as a 500 (#2483).
2. **A false commit rule.** "The commit happens in the route, never in a
   service" was contradicted by shipped code: `DataEntryWorkflow`
   deliberately commits inside the workflow, and the simulator PATCH
   commits twice (route + job enqueue).

Five options were scored (status-quo codified 6.5, one-aggregate services +
workflows **8.5**, workflow-only writes 7, unit-of-work + domain events 5,
job-first writes 6 — fit, effort, enforceability, over-engineering risk,
payoff against the observed failure modes).

## Decision

Adopt **one-aggregate services + operation workflows** (option 2). The
rule text is canonical in `it4r-agent-kit` and reaches this repo through
`make sync-agent-rules`; this ADR records the decision and its
co2-calculator application. In short:

- **Transaction ownership follows delegation.** A route calling services
  directly owns the commit; a service or repo never commits. A workflow
  owns its own commits — multi-step work, possibly several short
  transactions, possibly handing the heavy part to a background job. Never
  both in one request path.
- **A service serves one aggregate.** Crossing aggregates —
  create-then-fan-out, cascade deletes, cross-entity sync, provisioning —
  is a workflow named after the operation. Existence is an explicit
  workflow step, never a branch discovered mid-request.
- **Binds new code.** Existing service webs (`SimulatorPlanService` →
  `CarbonReportService` → module service) migrate opportunistically, when
  a change touches them anyway. No big-bang refactor.

## Consequences

- #2487 (PUT singletons for explore/calculator) is implemented as a
  provisioning workflow — the first new code bound by this ADR.
- The deferred `simulator_plan_purge` (plan 2449 Track A) is specified as
  a workflow + job when its triggers fire.
- The #2484 SAVEPOINT guards remain the data-layer belt under whatever
  orchestration sits above.
- Enforcement starts as review discipline; an import-linter contract
  (services must not import services in new modules) can mechanize it
  later if drift appears.
