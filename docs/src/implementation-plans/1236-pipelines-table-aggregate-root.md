# 1236 — First-class `pipelines` table

Status: design · Issue #1236 · Integrates into `fix/pipeline-debug`
(supersedes the standalone PR #1237). Not bundled with #1234 / #1225.

## Why

A "pipeline" is currently emergent: rows in `data_ingestion_jobs`
sharing a `pipeline_id` UUID, DAG reconstructed from
`meta.parent_job_id` / `recalc_jobs_chained` / `aggregation_job_id`,
status recomputed on every read by `compute_pipeline_progress`. That
missing aggregate root is the root cause of a recurring bug class:
NULL-until-fan-out (orphans + the #1225 eager-id workaround), premature
"success" (#1219), and the console (#1234) having to `GROUP BY
pipeline_id` with two-step pagination. See `emission-pipeline-flow.md`
for the current DAG.

## Background — why this is hard (poisoning & deadlocks)

Keep this; it is the whole reason the design is shaped this way.

- A SQLAlchemy async `Session` is **one Postgres transaction**. Any
  statement error aborts the **entire** transaction; every later
  statement then fails with `InFailedSqlTransaction: current
transaction is aborted …` until a `ROLLBACK`
  (`PendingRollbackError`). The logged error is usually the
  **cascade, not the cause** — e.g. jobs 47/74/104 log a harmless
  `SELECT carbon_report_modules` because it was merely the first
  statement to touch an already-poisoned session; the real failure
  was an earlier write.
- A **deadlock** = two transactions each holding a lock the other
  needs in opposite order; Postgres kills one (`DeadlockDetected`).
  Here it is structural: one upload → `recalc_jobs_chained: 3` → 3
  `emission_recalc` children run **concurrently** over overlapping
  rows, each `DELETE`/re-insert `data_entry_emissions`, each
  `aggregation` then rewrites ~2231 `carbon_reports`. 3× concurrent
  full-table rewrites = the deadlocks in the data (job 90 on `UPDATE
carbon_reports`).
- Chain: **amplification → concurrent overlapping writes → deadlock
  (trigger) → no rollback → poisoning (cascade) → job sinks**
  (#1219/#1225).
- Two sessions (`job_session` vs `data_session`) correctly isolate
  _job-state_ integrity from _data_ poisoning — necessary, but only
  that axis. It does not prevent cross-worker deadlocks, nor stop a
  poisoned `data_session` sinking the rest of a job's data work; that
  is what #1225's per-entry `begin_nested()` SAVEPOINT covers. Both
  halves are required.

## Proposed model

First-class `pipelines` table; `data_ingestion_jobs.pipeline_id`
becomes an FK.

```
pipelines
  id              uuid pk
  kind            text   -- = parent job_type: csv_ingest | api_ingest |
                         --   factor_ingest | unit_sync |
                         --   module_emission_recalc | reference_ingest
  status          text   -- NOT_STARTED|RUNNING|SUCCESS|PARTIAL|FAILED
  entity_type     enum   -- kept; NOT folded into kind
  ingestion_method enum   -- kept; NOT folded into kind
  module_type_id  int  null
  year            int  null
  expected_recalc int  null   -- owned recalc count (was meta.recalc_jobs_chained)
  job_count       int
  error_count     int
  started_at      timestamptz null
  finished_at     timestamptz null
  last_error      text null
```

`kind` mirrors the parent job's `job_type` — deliberately **not** a
flattened `CSV_MODULE_PER_YEAR / API_MODULE_UNIT_SPECIFIC` enum (see
Rejected alternatives).

## DECIDED — Phase-1 status maintenance

- **Recompute-and-store** (not incremental). On a job terminal, read
  the pipeline's sibling jobs, run the existing pure
  `compute_pipeline_progress`, write the single resulting `status`.
  Rationale: drift is the exact bug we are killing; recompute-from-
  truth cannot drift and self-heals a lost write, whereas an
  incremental accumulator under concurrency + retries + out-of-order
  terminals is precisely how drift returns. The per-terminal sibling
  SELECT is bounded and indexed by `pipeline_id` — cheap insurance.
- **Option (a) — only the last expected child writes status.** Use
  `expected_recalc` (+ aggregation count) so just the terminating
  child performs the status write. Cuts the all-children-write-the-
  same-`pipelines`-row contention to ~one write per pipeline.
- The status write **must** sit inside a `begin_nested()` SAVEPOINT
  (the #1225 discipline): if it deadlocks/errors, roll back **only the
  savepoint** so the job's own `finish_job` survives; log-and-skip the
  status update; reconcile later. A reconciliation sweep (recompute
  status for any pipeline whose stored status ≠
  `compute_pipeline_progress`) is the safety net for skipped writes.

## Concurrency & contention model (informs Phase 3+)

The contention map has two **distinct** problems — do not conflate:

| Phase                    | Writes                                                              | Cross-pipeline conflict     |
| ------------------------ | ------------------------------------------------------------------- | --------------------------- |
| ingest + emission_recalc | `data_entries`/`data_entry_emissions`, **det-partitioned**          | none between different dets |
| aggregation              | `carbon_report_modules` + the **shared `carbon_reports` synthesis** | always                      |

- **Problem A — aggregation is the universal collision + amplified.**
  Fix the _step_, not whole pipelines (whole-pipeline priority over-
  serializes the independent det-partitioned phases and still does the
  full rewrite). Two levers: **coalesce** concurrent aggregation for a
  report/year scope into one trailing run (extend the existing
  `AGGREGATION_DEDUP`); **scope** the rewrite to the recalc's already-
  computed `affected_module_ids` instead of all reports.
  - **VERIFY (not asserted):** confirm the aggregation handler
    actually full-rewrites (`modules_refreshed: 2231` constant in the
    dumps strongly suggests it) and is not already scoped some other
    way, before designing the scoping change.
- **Problem B — same-`(module_type_id, data_entry_type_id, year)`
  factor-vs-data ordering is a correctness bug**, not just contention:
  a data recalc concurrent with a factor reload for the same scope
  computes emissions against half-loaded factors → silently wrong
  numbers. Needs a **scoped** factor-before-data mutex (reuse the
  `uq_emission_recalc_active` per-scope primitive; the gap is ordering
  the _parent ingests_ for that scope), not whole-pipeline priority.

Net direction: keep ingest/recalc concurrent (that is the wanted
parallelism); make aggregation a coalesced, affected-scope, serialized-
per-report-domain step (A); add a scoped factor→data ordering (B).
Most of this extends primitives already built.

## Phased plan (each shippable + reversible)

1. **Add table + write-through.** Create `pipelines`;
   chain/dispatch/recalc upsert a row; runner advances `status` via
   recompute-and-store, option (a), inside the #1225 SAVEPOINT.
   _Verify:_ a reconciliation query returns **zero** rows where stored
   `status` ≠ `compute_pipeline_progress` over the pipeline's jobs.
2. **Backfill.** One migration: a `pipelines` row per historical
   `pipeline_id`; NULL-pipeline parents → single-step pipelines.
   _Verify:_ counts reconcile; #1219/poisoned samples land
   `FAILED`/`PARTIAL`.
3. **Flip reads.** Console (#1234), `GET /pipelines/{id}`, progress
   read the table; `compute_pipeline_progress` becomes writer-side
   only. _Verify:_ golden-output diff before/after on the same DB.
4. **Aggregation coalesce + scope (Problem A)** and **scoped
   factor→data ordering (Problem B)** — separate sub-PRs, gated on the
   VERIFY above.
5. **Retire meta threading** once nothing reads the counters.

Phases 1–2 are pure additions (revert = drop table); phase 3 is the
only behavioural flip.

## Rejected alternatives

- **Flat `kind` enum**: cartesian of `ingestion_method` ×
  `entity_type` (already columns); incomplete for `factor_ingest` /
  `unit_sync` present in real data.
- **`pipelines` as a VIEW**: keeps per-read recompute, cannot carry an
  authoritative `status`.
- **Global whole-pipeline priority/mutex** (the first instinct for
  side-note-2): over-serializes the independent det-partitioned
  phases and still leaves the full-table aggregation rewrite. Replaced
  by the A/B decomposition above.
- **Incremental status**: drift under concurrency/retries/reorder =
  the #1219 class.

## Open questions

- `PARTIAL` (some children errored, chain completed) vs `FAILED`
  (chain broken) exact definition.
- Aggregation coalescing key: `(carbon_report scope, year)`? Interaction
  with `unit_sync` (year-level, also rewrites `carbon_reports`).
- Shared-synthesis edge: det-disjoint pipelines still collide on a
  `carbon_reports` row when their modules share a report — serialize by
  report-domain, not by det.
- Retry-safety of the factor→data ordering (`max_attempts=3`,
  mid-pipeline re-claim) and interaction with dedup-skip.
- Backfill of legacy rows lacking meta counters — best-effort
  `compute_pipeline_progress`, same as today's read path.

## Convention notes

Pipeline work integrates into `fix/pipeline-debug` (not `dev`) until
told otherwise. Commit messages: no `Co-Authored-By` trailer.
