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
- **Option (a) — only the last child writes status.** No manual
  counting: `compute_pipeline_progress(siblings).done` _is_ the
  last-child oracle. Under READ COMMITTED a non-last terminal sees
  `done=false` and skips; the actually-last terminal sees every
  earlier commit and writes. If two terminals race and both observe
  the full set, both write — benign, recompute-from-truth makes the
  writes identical (just brief row contention). UPSERT; add no
  coordination machinery for a self-resolving edge.
- **Mechanism: post-commit isolated write, NOT a SAVEPOINT inside the
  finish transaction.** `repo.finish_job` self-commits the
  `job_session`; there is no enclosing transaction to nest in. So the
  status write is its own short transaction _after_ `finish_job`
  returns `True`, fully `try/except`'d (log-and-skip on any DB error).
  This is _stronger_ isolation than the SAVEPOINT ideal: the job's
  terminal is already durably committed, so a failed status write
  cannot poison it at all. Trade-off: a small window where a reader
  sees stale status — irrelevant in Phase 1 (no reads flipped),
  absorbed in Phase 3 by the sweep + next-terminal self-heal.
- **Row creation is a separate concern from status.** Create the
  `pipelines` row at **parent creation**, not in the runner (the
  runner is a terminal actor, not a kickoff actor). One idempotent
  helper `ensure_pipeline_exists(session, pipeline_id, parent_job)`
  (`INSERT … ON CONFLICT DO NOTHING`) called from the 4 post-merge
  mint sites (`_stamp_job_type_and_meta`, the 2 recalc endpoints'
  `DataIngestionJob(...)`, `_chain.py` lazy mint). One logical
  chokepoint, several call sites — keeps Phase-3 in-flight visibility
  without 4-way drift.
- **Reconciliation sweep** (recompute status where stored ≠
  `compute_pipeline_progress`) is the durable backstop for skipped
  writes. Phase 1 ships it as a standalone callable (manually /
  cron-invokable); Phase 3 schedules it before flipping reads.

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

> **v0.x has no backfill — the DB is dropped between deploys; real
> backfill starts at v1.x.** This collapses old Phase 2: there is no
> history to synthesise. On any fresh v0.x DB every `pipeline_id`
> originates from `ensure_pipeline_exists`, so the FK is not
> backfill-gated — it can be enforced once a clean DB is running
> Phase-1 code (i.e. the deploy *after* Phase 1 ships, which in v0.x
> is a DB drop). The mid-DB-life window (Phase 1 deployed onto a DB
> that already has pre-Phase-1 pipeline_id rows) is the only reason
> the FK isn't in the Phase-1 migration itself.

1. **Add table + write-through.** ✅ DONE (`fix/pipeline-debug`).
   Migration creates `pipelines` table-only (column stays plain UUID,
   **no FK yet** — see box above). The 4 mint sites call
   `ensure_pipeline_exists`; the runner advances `status`
   post-`finish_job` as an isolated log-and-skip write (last-child
   oracle). Sweep is a standalone callable.
   _Verify (met):_ the reconciliation test proves **zero** drift
   (stored `status` == `compute_pipeline_progress`).
2. **Enforce FK** (v0.x, post-DB-drop) — add `pipeline_id` FK →
   `pipelines(id)` once a clean DB runs Phase-1 code. No data
   migration. _Verify:_ migration applies on a fresh DB; an orphan
   `pipeline_id` is impossible because `ensure_pipeline_exists` runs
   at every mint. **(v1.x: a real backfill migration replaces this
   step — a `pipelines` row per historical `pipeline_id`,
   NULL-pipeline parents → single-step; #1219/poisoned samples land
   `FAILED`/`PARTIAL`. The `last_error`-skips-"Success" fix already
   makes that backfill safe.)**
3. **Flip reads.** Console (#1234), `GET /pipelines/{id}`, progress
   read the table; `compute_pipeline_progress` becomes writer-side
   only. _Verify:_ golden-output diff before/after on the same DB.
4. **Aggregation coalesce + scope (Problem A)** and **scoped
   factor→data ordering (Problem B)** — separate sub-PRs, gated on the
   VERIFY above.
5. **Retire meta threading** once nothing reads the counters.

Phase 1 is a pure addition (revert = drop table); phase 3 is the only
behavioural flip.

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
