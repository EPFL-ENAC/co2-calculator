---
status: in-progress
issue: 310
last_updated: 2026-05-06
title: "310 — Background Pipeline Architecture: Overview"
summary: "Umbrella plan: redesign FastAPI background workflows for multi-pod safety, retry, and observability."
---

# 310 — Background Pipeline Architecture: Overview

## Why we are doing this

The CO2 calculator runs background workflows (CSV uploads, factor ingestion, emission
recalculation, unit sync) via FastAPI `BackgroundTasks`. Multi-pod deployment exposes several
classes of bugs:

### Current pain points

**1. Pod collision**
Sync background tasks run in a thread-pool executor. Two concurrent HTTP requests (or two pods
handling the same trigger) can spawn two tasks that write the same DB rows simultaneously. No
claiming mechanism prevents this. The result is duplicate writes, race conditions on
`carbon_reports`, and misleading job state.

**2. `is_current` race**
Today's flow creates a job with `state=NOT_STARTED, is_current=False`, then the background task
sets `is_current=True` only after starting. The partial unique index does not trip during the
race window, so two simultaneous operator actions create two jobs that both run.

**3. No retry / recovery**
Pods that crash mid-job leave `state=RUNNING` rows stuck forever. No `attempts` counter, no
`run_after` delay, no recovery mechanism.

**4. Incomplete pipeline coverage**
Unit sync returns `job_id=0` — untracked, unobservable, unrecoverable. Factor ingest requires a
manual recalculation step that operators forget.

**5. Ad-hoc pipeline wiring**
Each pipeline is wired differently: providers, tasks, inline workflows. No unified dispatch.
Adding a new pipeline requires re-inventing the pattern.

**6. One writer per table is violated on the bulk path**
CSV ingestion currently computes `data_entry_emissions` inside the ingest transaction. Factor
recalculation ALSO writes `data_entry_emissions`. Both call `recompute_stats` which writes
`carbon_reports`. Two concurrent bulk pipelines for different modules race on the same tables.

---

## The two-path principle (foundational framing)

The system has two distinct user paths with fundamentally different latency expectations:

### Path 1 — Interactive (UI)

**Users**: standard users + principal users updating their own modules in the UI.
**Triggers**: `POST/PATCH/DELETE /v1/carbon_reports/.../data-entry`.
**Flow** (synchronous, instant feedback):

```
DataEntry  →  data_entry_emissions  →  carbon_report_modules.stats  →  carbon_reports.stats
```

All inline. Single row. Fast (< 200ms typical). User sees impact immediately.

**Path 1 is out of scope for these plans.** It works today and stays exactly as-is. No jobs.
No DAG. No async.

### Path 2 — Bulk (operator)

**Users**: principal users + backoffice métier uploading CSVs, syncing factors, syncing units.
**Triggers**: `POST /sync/dispatch` (CSV), `POST /sync/factors/...`, `POST /sync/units`,
`POST /sync/recalculate-emissions/...`.
**Flow** (async, no instant feedback expected):

```
csv_ingest job  →  emission_recalc job (one per data_entry_type)  →  aggregation job
```

Operators expect minutes, not milliseconds. SSE shows pipeline progress. Stats become correct
when the chain finishes.

**Plans A–D apply only to Path 2.**

---

## Architectural decisions

### Chaining mechanism: in-process `asyncio.create_task` + safety poller

**Decided.** Web pods both serve HTTP and run jobs (current model). Chaining works two ways:

1. **Fast path**: a handler that completes successfully calls
   `asyncio.create_task(run_job(next_job_id))` to fire the next step in milliseconds.
2. **Safety net**: each pod runs an in-process loop that polls every 10s for orphan jobs
   (`state=NOT_STARTED AND run_after<=now() AND locked_by IS NULL`) using
   `FOR UPDATE SKIP LOCKED`. This recovers chains broken by pod crashes.

#### Why not Option 3 (`asyncio.create_task` only, no poller)

A pod crash between `data_session.commit()` and `asyncio.create_task(...)` leaves the next job
sitting at `state=NOT_STARTED` forever. With no poller, the only recovery is the manual
`POST /sync/jobs/{job_id}/recover` endpoint (Plan A). Operators have to notice the stuck chain
and act. The 10-second poller closes that hole at trivially small DB cost (~1 SELECT per pod
per 10s with SKIP LOCKED, well under 1 RPS even at 10 pods).

#### Why not Option 2 (dedicated worker pod)

A separate worker fleet is the standard pattern (Celery, RQ, Sidekiq) but adds deployment
complexity (new k8s Deployment, separate scaling, separate monitoring) for a workload that
fires intermittently. The handler registry from Plan C makes `run_job(job_id)` deployable
anywhere — if production data ever justifies a dedicated worker, it is a feature flag and a
new Deployment, not a refactor. **You don't lose the option by starting in-process.**

#### When to switch to Option 2 (concrete triggers)

Revisit if any of:

- p95 web request latency rises during CSV ingestion (job CPU bleeding into request path)
- Job throughput exceeds ~100 jobs/minute (poller saturating one pod's event loop)
- Need for job-specific resource limits (e.g., 4 GB memory for emission recalc on large datasets)
- Need for sub-second chain latency (current 10s safety-net poll becomes the bottleneck)

### `claim_job` is atomic on `state` + `is_current`

**Decided.** `claim_job` does both in one statement, and a pre-step unsets the previous
`is_current` for the same combo. The unique partial index trips on the second claimer's
UPDATE. See Plan A.

### Factor classification → JSONB

**Decided.** Migrate `factors.classification` from JSON to JSONB. Postgres JSONB normalizes
keys alphabetically; `::text` becomes deterministic regardless of insertion order. Eliminates
the silent-duplicate-row footgun. See Plan B.

### Plan D ships with C, not deferred

**Decided.** Plan D is reframed: it is no longer "purity refactor for one-writer-per-table";
it is the explicit codification of the two-path principle for the bulk path. The "manual UI
keeps inline emission compute" carve-out is not a violation — it is Path 1, which Plan D does
not touch.

---

## The four-plan roadmap

```
310-a  →  310-b  →  310-c  →  310-d
 │         │         │         │
Pod      Factor    DAG +     Bulk path
safety   pipeline  handler   = pure
+ atom.  + unit    registry  async
claim    sync     (poller)   (Path 2)
```

| Plan | Ships in      | Depends on  |
| ---- | ------------- | ----------- |
| A    | PR 1          | —           |
| B    | PR 1          | A migration |
| C    | PR 2          | A, B        |
| D    | PR 2 (with C) | C           |

---

## Plan A — Pod Safety + Atomic Claim (`310-a-pod-safety.md`)

### What

Extend `DataIngestionJob` with claiming/retry/grouping fields. Replace the create-then-mark
pattern with an atomic `claim_job` that sets `state=RUNNING` AND `is_current=TRUE` in one
statement (with a pre-step that unsets the previous current row for the same combo). The
unique partial index `ix_data_ingestion_jobs_is_current_unique` then trips on the second
claimer.

Add a manual stale-job recovery endpoint and the in-process safety poller (lives in this plan
because it is the orphan-recovery mechanism that pairs with `claim_job`).

### What it fixes

- Pod collision on the bulk path → eliminated (atomic claim + unique index)
- Jobs stuck in RUNNING after pod crash → recoverable manually + auto-recovered by poller
- No grouping of related jobs → `pipeline_id` enables dashboard queries per pipeline run
- No retry scaffolding → `attempts` / `max_attempts` / `run_after` columns ready for use by
  the poller and by Plan B's auto-recalc trigger

---

## Plan B — Factor Pipeline + Unit Sync Tracking (`310-b-factor-pipeline.md`)

### What

1. **Factor classification → JSONB** + unique index. Eliminates the JSON-key-order footgun.
2. **Factor upsert-in-place**: `INSERT ... ON CONFLICT DO UPDATE` keyed on the new unique
   index. Preserves `factor.id` FKs from Strategy A `DataEntry` rows.
3. **Stale factor tracking**: add `last_seen_job_id` column. Factors not in the new upload
   keep their FKs but operators can see them as "not in latest CSV".
4. **Auto-recalculation after factor ingest**: at the end of `run_sync_task`, when target is
   FACTORS and result is not ERROR, create one `emission_recalc` job per stale type and fire
   each via `asyncio.create_task`.
5. **Unit sync job tracking**: `EntityType.GLOBAL_PER_YEAR` (with `ALTER TYPE` migration);
   `POST /sync/units` creates a real job and returns a real `job_id`.

### What it fixes

- Dangling FKs after factor CSV upload → eliminated
- Silent duplicate factor rows from inconsistent JSON ordering → eliminated by JSONB
- Manual recalculation step that operators forget → automated
- Unit sync invisible / unrecoverable → tracked + SSE-streamable
- Stale factors silently lost on bulk-delete → preserved + visible

---

## Plan C — DAG + Handler Registry + Observability (`310-c-dag-handler-registry.md`)

### What

1. **Handler registry**: each `job_type` registers a handler function. `csv_ingest`,
   `api_ingest`, `factor_ingest`, `emission_recalc`, `module_emission_recalc`, `unit_sync`,
   `aggregation` (Plan D).
2. **Unified `run_job(job_id)` runner**: single dispatch path. Reads job, claims it
   (Plan A), looks up handler by `job_type`, executes with the dual-session pattern, fires
   `next_job` chains via `asyncio.create_task`.
3. **Observability**: `started_at` / `finished_at` columns. Documented dashboard query for
   throughput / duration / failure rate per `job_type`.

### What it fixes

- Ad-hoc pipeline wiring → one registry, one runner
- No way to see pipeline duration → started_at / finished_at + dashboard SQL
- Plan B's `_enqueue_stale_recalculations` → folded into a generic `chain_job(parent, child)`
  helper used by every handler

---

## Plan D — Bulk Path Pure Async (`310-d-pipeline-responsibility-split.md`)

### What

Make the bulk path (Path 2) fully respect the one-writer-per-table rule:

- **Bulk ingest jobs** (`csv_ingest`, `api_ingest`, `factor_ingest`) write `data_entries`
  only. They no longer compute emissions inline. They chain to `emission_recalc`.
- **`emission_recalc` job** writes `data_entry_emissions` only. It chains to `aggregation`.
- **`aggregation` job** writes `carbon_reports.stats` only. With dedup so N concurrent recalcs
  for the same module produce one aggregation job.

**Path 1 (interactive UI) is unchanged.** This plan makes that an explicit, documented design
choice — not a violation.

### What it fixes

- Bulk-path race conditions on `carbon_reports.stats` → eliminated
- Long-running emission compute holding ingest transaction locks → split into separate jobs
- Frontend stale-stats UX after CSV upload → spec'd ("Recalculating..." badge per module while
  pipeline runs)

---

## Cross-cutting: testing strategy

Plan A's claim race must be tested with **real Postgres**, not mocked. The plan adds an
integration test that fires two concurrent `claim_job` calls against a real DB and asserts
exactly one wins. Without this, we ship pod-safety code without proving it works under
contention.

## Cross-cutting: batching (deferred to a future plan)

The reflexion doc recommends 1k–5k row batches for CSV ingest and 50–200 entry batches for
emissions. None of A–D delivers this. As data volume grows, single-transaction iterations
will hold long locks. Track as a follow-up — implementation depends on Plan D's job split
landing first.
