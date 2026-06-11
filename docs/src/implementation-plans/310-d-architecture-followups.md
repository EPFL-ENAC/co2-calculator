---
status: delivered
issue: 310-d
last_updated: 2026-05-29
title: "310-d Architecture follow-ups (#1062 / #1063 / #1064)"
summary: "Three architectural follow-ups staged from the 310-D landing — passive-monitoring backstop, unified pipeline state store, and DedupConfig generalisation. Each is tracked on a dedicated GitHub issue and lands in the post-merge fix batch."
---

# 310-d Architecture follow-ups

> **Delivered** in post-merge fix batch PR #1079. #1 stale-stats endpoint
> (`f99a03bd`, #1063), #2 `DedupConfig` (#1064), #3 `pipelineState` store +
> active-pipelines endpoint (`e3094ef6`, #1062). Parent tracking issue #1057.

The 310-D pipeline shipped a runner-driven aggregation chain plus a
reactive frontend story. Three architecture-shaped follow-ups were
deferred during that landing — they aren't bug fixes (those live in
`docs/code-review/310-overall-review.md`), they're shape work for the
next iteration.

This document is the umbrella; each follow-up has a dedicated section
below tracking its delivery state.

---

## Follow-up 1 — Pipeline-failure observability backstop endpoint (#1063)

### Status

**Delivered in PR #1077** (post-merge fix batch, Unit 10; integrated via #1079).

### Problem

The runner-driven chain surfaces failures interactively (recalc badge +
pipeline diagnostic tooltip) when an operator is watching. The
passive-monitoring case has no single owner:

- Background failures with no operator watching never trigger an alert.
- Stuck `NOT_STARTED` aggregation rows (claim never happened) are
  invisible to the recalc UI.
- Slow-burn drift — a successful aggregation grows older than its data —
  goes unnoticed.

### Decision

**Operator-triggered, no auto-retry**: a read-only health endpoint
suitable for Datadog / Prometheus scrape. Auto-retry was rejected
because it has retry-storm modes that aren't worth the complexity now.

### Shape

- `GET /v1/sync/health/stale-stats?older_than_minutes=60` (default 60,
  `ge=1`).
- Gated on `backoffice.data_management.view`.
- Returns `list[StaleStatsEntry]` — one row per
  `(module_type_id, year)` that is stale or missing an aggregation,
  classified by `why_stale`:
  - `no_aggregation_ever` — module exists but no aggregation row ever
    inserted.
  - `pending_aggregation_stuck` — latest row in a non-terminal state
    (`NOT_STARTED` / `QUEUED` / `RUNNING`).
  - `last_aggregation_failed` — latest row `FINISHED` with
    `result = ERROR`.
  - `last_aggregation_too_old` — latest row `FINISHED` with non-error
    result but `finished_at` older than the cutoff (or `NULL`).

The seed-of-truth for "what should have an aggregation" is
`carbon_report_modules × carbon_reports.year` — the modules themselves
declare their own scope. The query LEFT JOINs from the modules to the
latest `job_type='aggregation'` row per scope; rows without a match fall
into `no_aggregation_ever`.

### Operator workflow

1. Datadog / Prometheus scrapes the endpoint on a schedule, counts rows
   per `why_stale` bucket, and alerts on non-zero values.
2. Operator opens the back-office, navigates to the affected scope, and
   triggers a recalc manually via the existing pipeline-control UI.

No retry storms, no opaque background sweeps — the operator stays in
control.

---

## Follow-up 2 — Generalise `chain_job(dedup_active)` to `DedupConfig` (#1064)

### Status

**Delivered in PR #1074** (post-merge fix batch, Unit 9; integrated via #1079).
Trigger fired by review finding B-M1 (`_chain_recalc_for_stale` becoming
the second concrete dedupable handler — back-to-back factor reuploads).
`DedupConfig` dataclass replaces the boolean shim; `EMISSION_RECALC_DEDUP`

- partial unique index `uq_emission_recalc_active` ship in the same PR.

---

## Follow-up 3 — Unified frontend `pipelineStateStore` + bulk active-pipelines endpoint (#1062)

### Status

**Delivered in PR #1075** (post-merge fix batch, Unit 11; integrated via #1079).
Frontend `pipelineState.ts` Pinia store keyed by `(module_type_id, year)`
collapses the prior dual-source-of-truth (`useTimelineStore.currentPipelineIds`

- `yearConfigStore.recalculationStatus[].current_pipeline_id`); backend
  `GET /v1/sync/active-pipelines` thin-wraps the existing
  `get_current_pipeline_ids_for_modules` repo helper. Per-module scope filter
  on the endpoint added in the post-merge bot-triage pass.

---

## Cross-references

- Source-of-truth for the post-merge review findings:
  `docs/code-review/310-overall-review.md`.
- Coordinator workstream: `docs/src/implementation-plans/310-post-merge-fix-batch.md`.
