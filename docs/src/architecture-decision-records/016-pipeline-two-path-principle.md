---
status: delivered
last_updated: 2026-05-05
summary: Path 1 (interactive UI) writes inline; Path 2 (bulk operator) chains async jobs. Each table has one writer per path.
---

# ADR-016: Two-Path Pipeline Principle (Interactive vs Bulk)

**Status**: Accepted
**Date**: 2026-05-05
**Deciders**: Backend Team
**Related**: [ADR-010: Background Job Processing](./010-background-job-processing.md); plan `docs/src/implementation-plans/310-d-pipeline-responsibility-split.md`

## Context

The CO2 calculator serves two user paths with fundamentally
different latency expectations:

- **Path 1 — Interactive UI**: standard and principal users edit
  modules through `POST/PATCH/DELETE /v1/carbon_reports/...`. Users
  expect instant visual feedback (<200ms typical).
- **Path 2 — Bulk operator**: principal users and backoffice métier
  upload CSVs, sync factors, sync units. Operators expect minutes,
  not milliseconds; SSE streams progress.

Earlier code mixed both paths through the same write functions.
Bulk CSV ingest computed emissions inside the ingest transaction;
factor recalculation also wrote `data_entry_emissions`; both called
`recompute_stats` writing `carbon_reports`. Two concurrent bulk
pipelines for different modules raced on the same tables.

## Decision

Codify a **two-path principle** with distinct write strategies per
path:

| Path                  | Trigger                          | Write strategy        |
| --------------------- | -------------------------------- | --------------------- |
| 1 — Interactive UI    | UI module edit endpoints         | Inline, synchronous   |
| 2 — Bulk operator     | `/sync/dispatch`, `/sync/...`    | Async chained jobs    |

Each table has **exactly one writer per path**:

| Table                  | Path 2 writer                    | Path 1 writer (unchanged)    |
| ---------------------- | -------------------------------- | ---------------------------- |
| `data_entries`         | `csv_ingest` / `api_ingest` jobs | `CarbonReportModuleWorkflow` |
| `data_entry_emissions` | `emission_recalc` job            | `CarbonReportModuleWorkflow` |
| `carbon_reports.stats` | `aggregation` job                | `CarbonReportModuleWorkflow` |

Path 2 chain (per module):

```
csv_ingest  →  emission_recalc  →  aggregation
```

Aggregation jobs dedupe per `(module_type_id, year)` so N parallel
recalcs collapse to one stats refresh.

Path 1 keeps inline writes. Single-row request scope serializes its
writes naturally; this is a deliberate UX choice, not a violation.

See `docs/src/implementation-plans/310-d-pipeline-responsibility-split.md`.

## Consequences

**Positive**:

- Bulk-path race conditions on `data_entry_emissions` and
  `carbon_reports.stats` are eliminated by ownership, not locking.
- Long-running emission compute no longer holds ingest transaction
  locks; ingest commits fast and chains the recalc.
- Frontend UX explicit: per-module "Recalculating..." badge while
  Path 2 chains run.

**Negative**:

- Two write paths to maintain. Tests must cover both.
- New contributors must learn which path their change belongs to;
  the rule "is the user staring at a spinner?" decides — yes is
  Path 1, no is Path 2.

**Future work**: batched ingest (1k–5k rows) is deferred until
Path 2's job-split lands and lock duration becomes the bottleneck.

## References

- `docs/src/implementation-plans/310-d-pipeline-responsibility-split.md`
- `docs/src/implementation-plans/310-overview.md`
