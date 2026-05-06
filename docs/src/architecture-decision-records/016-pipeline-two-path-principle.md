---
status: partially-delivered
last_updated: 2026-05-05
summary: Path 1 (interactive UI) writes inline; Path 2 (bulk operator) chains async jobs. Single-writer-per-path is the target; today emissions/stats writers are split between the dispatch chain and legacy inline calls.
---

# ADR-016: Two-Path Pipeline Principle (Interactive vs Bulk)

**Status**: Accepted (principle); ownership split partially implemented — see "Current state" below
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

| Path               | Trigger                       | Write strategy      |
| ------------------ | ----------------------------- | ------------------- |
| 1 — Interactive UI | UI module edit endpoints      | Inline, synchronous |
| 2 — Bulk operator  | `/sync/dispatch`, `/sync/...` | Async chained jobs  |

Each table should have **exactly one writer per path**. The target
ownership map:

| Table                  | Path 2 writer (target)           | Path 1 writer (unchanged)    |
| ---------------------- | -------------------------------- | ---------------------------- |
| `data_entries`         | `csv_ingest` / `api_ingest` jobs | `CarbonReportModuleWorkflow` |
| `data_entry_emissions` | `emission_recalc` job            | `CarbonReportModuleWorkflow` |
| `carbon_reports.stats` | `aggregation` job                | `CarbonReportModuleWorkflow` |

Path 2 chain (per module), once fully delivered:

```
csv_ingest  →  emission_recalc  →  aggregation
```

Aggregation jobs dedupe per `(module_type_id, year)` so N parallel
recalcs collapse to one stats refresh.

Path 1 keeps inline writes. Single-row request scope serializes its
writes naturally; this is a deliberate UX choice, not a violation.

See `docs/src/implementation-plans/310-d-pipeline-responsibility-split.md`.

### Current state

The single-writer split is **partially delivered**. The dispatch path
chains `csv_ingest → emission_recalc`, but stats recomputation is not
yet a dedicated `aggregation` job — it is still called inline:

- `backend/app/workflows/emission_recalculation.py:150` —
  `module_svc.recompute_stats(module_id)` runs at the end of the
  recalc workflow.
- `backend/app/services/data_ingestion/base_csv_provider.py:1082` —
  bulk CSV ingest invokes `_recompute_module_stats()` inline before
  the recalc chain takes over.

`TargetType` does not yet expose an `AGGREGATION` value, and no
aggregation worker exists. Until plan 310-d lands the dedicated
aggregation job and removes the inline `recompute_stats` calls, the
`carbon_reports.stats` row of the table above describes intent, not
the live writer set. Treat the table as the architectural goal; the
in-tree behavior for stats is **mixed: extracted in the dispatch path
where applicable, still inline in the legacy ingest and recalc
paths**.

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
