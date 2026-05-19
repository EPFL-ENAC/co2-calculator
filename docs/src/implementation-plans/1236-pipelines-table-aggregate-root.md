# 1236 — First-class `pipelines` table

Status: design · Issue #1236 · Not bundled with #1234 or #1225

## Why

A "pipeline" is currently emergent: rows in `data_ingestion_jobs` that
share a `pipeline_id` UUID, with the DAG reconstructed from
`meta.parent_job_id` / `meta.recalc_jobs_chained` /
`meta.aggregation_job_id`, and status recomputed on every read by
`compute_pipeline_progress`. That missing aggregate root is the root
cause of a recurring bug class:

- `pipeline_id` is NULL until the first fan-out → orphans, and the
  eager-id workaround (#1225 / Option A) exists only to paper over it.
- Premature "success" (#1219) — there is no authoritative pipeline
  status to trust.
- The ops console (#1234) must `GROUP BY pipeline_id` with two-step
  pagination because there is no pipeline row to index or page on.
- Counters threaded through `meta` JSON are fragile.

See `emission-pipeline-flow.md` for the current DAG.

## Proposed model

A first-class `pipelines` table (the aggregate root).
`data_ingestion_jobs.pipeline_id` becomes a real FK.

```
pipelines
  id              uuid pk
  kind            text   -- parent job_type: csv_ingest | api_ingest |
                         --   factor_ingest | unit_sync |
                         --   module_emission_recalc | reference_ingest
  status          text   -- NOT_STARTED | RUNNING | SUCCESS | PARTIAL |
                         --   FAILED  (the authoritative state machine)
  entity_type     enum   -- kept, NOT folded into kind
  ingestion_method enum   -- kept, NOT folded into kind
  module_type_id  int  null
  year            int  null
  expected_recalc int  null   -- replaces meta.recalc_jobs_chained
  job_count       int
  error_count     int
  started_at      timestamptz null
  finished_at     timestamptz null
  last_error      text null
```

`kind` mirrors the **parent job's `job_type`**. It is deliberately
**not** a flattened `CSV_MODULE_PER_YEAR / API_MODULE_UNIT_SPECIFIC …`
enum — see Rejected alternatives.

## Central design constraint (the actual hard part)

`pipelines.status` must be advanced **transactionally by the runner on
every job terminal** (`finish_job`). That path is precisely where we
have seen `DeadlockDetected` and `InFailedSqlTransaction` poisoning
(#1225). A naïve added `UPDATE pipelines SET status…` in that path
reintroduces the poisoning surface and lets `status` drift from job
reality — which _is_ the #1219 bug, now denormalised and harder to
spot.

Therefore the status write **must** sit inside the same
`begin_nested()` SAVEPOINT discipline established in #1225, and a
failed status write must never poison the job's own terminal write.
Treat this as the design's primary risk, not an afterthought.

Open question: is `status` advanced incrementally per child terminal,
or recomputed by reusing the existing pure `compute_pipeline_progress`
over the pipeline's jobs at each terminal? Recompute-and-store is
safer (one tested function, no drift) at the cost of a per-terminal
read of sibling jobs — decide in Phase 1.

## Phased plan (each phase shippable + reversible)

1. **Add table + write-through (no reads change).** Create
   `pipelines`; chain/dispatch/recalc paths upsert a row and the
   runner advances `status` (recompute-and-store via
   `compute_pipeline_progress`, inside the #1225 SAVEPOINT).
   `pipeline_id` still works exactly as today.
   _Verify:_ new pipelines get a row whose stored `status` always
   equals `compute_pipeline_progress` over its jobs (assertion test +
   a reconciliation query that must return zero drift rows).
2. **Backfill.** One migration: synthesise a `pipelines` row per
   distinct historical `pipeline_id`; NULL-pipeline parents become
   single-step pipelines.
   _Verify:_ row counts reconcile; spot-check the #1219 / poisoned
   samples land as `FAILED`/`PARTIAL`.
3. **Flip reads.** Point the console (#1234), `GET /pipelines/{id}`,
   and progress at the table. `compute_pipeline_progress` becomes the
   writer-side reducer only.
   _Verify:_ console + read endpoint return identical results before
   and after the flip on the same DB (golden-output diff).
4. **Retire meta threading.** Drop the
   `recalc_jobs_chained`/`aggregation_job_id`/`parent_job_id` read
   paths once nothing consumes them.
   _Verify:_ grep shows no readers; tests green.

Each phase merges independently to `dev`; phases 1–2 are pure
additions (revert = drop table), phase 3 is the only behavioural flip.

## Non-goals / scope

- Not part of #1234 (console ships on the current read-model) and not
  part of #1225 (the recalc-resilience fix stands alone).
- No change to job semantics, fan-out, or the runner's claim/finish
  CAS — only an added, SAVEPOINT-isolated status projection.

## Rejected alternatives

- **Flat `kind` enum** (`CSV_MODULE_PER_YEAR`, `API_MODULE_UNIT_SPECIFIC`,
  …): cartesian-products two axes that are already columns
  (`ingestion_method` × `entity_type`); every new method×scope is a new
  member; already incomplete for the `factor_ingest` / `unit_sync`
  pipelines present in real data. Use `kind` = parent `job_type` plus
  the existing orthogonal columns.
- **`pipelines` as a SQL VIEW**: removes the orphan/pagination pain but
  not the per-read recompute, and cannot carry an authoritative
  `status` — defeats the main reason to do this.
- **Keep emergent, add more meta**: status-in-JSON is the #1219 bug
  class; doubling down deepens it.

## Open questions

- Status state machine: exact `PARTIAL` definition (some children
  errored but chain completed) vs `FAILED` (chain broken).
- Incremental vs recompute-and-store status advance (Phase 1).
- Orphans: their own `kind`, or the parent's `kind` with
  `job_count=1`? (Leaning: parent's `kind`, no special-casing.)
- Backfill of legacy rows whose `meta` lacks the counters — best-effort
  `compute_pipeline_progress` fallback, same as today's read path.

## Convention notes

PRs target `dev`. Commit messages: no `Co-Authored-By` trailer.
