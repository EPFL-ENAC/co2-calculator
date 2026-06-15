---
status: partially-delivered
last_updated: 2026-06-12
summary: Path 1 (interactive UI) writes inline; Path 2 (bulk operator) chains async jobs (csv_ingest → emission_recalc → aggregation). Single-writer-per-path is delivered for the recalc chain; one legacy inline stats writer remains in CSV ingest.
---

# ADR-016: Two-Path Pipeline Principle (Interactive vs Bulk)

**Status**: Accepted (principle); ownership split delivered except one legacy inline stats writer — see "Current state" below
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

The single-writer split is **delivered for the recalc chain, with one
legacy inline writer left in CSV ingest**:

- The dedicated `aggregation` job exists
  (`backend/app/tasks/aggregation_tasks.py:87`,
  `@register("aggregation")`) and is the bulk-path writer of
  `carbon_reports.stats`. Both recalc handlers chain it
  (coalesced to one trailing job per pipeline — see the code-flow
  diagram below); `EmissionRecalculationWorkflow` no longer calls
  `recompute_stats` itself.
- `backend/app/services/data_ingestion/base_csv_provider.py:1279` —
  bulk CSV ingest still invokes `_recompute_module_stats()` inline
  before the recalc chain takes over. This is the remaining
  second writer on `carbon_reports.stats` in Path 2; harmless
  (the trailing aggregation overwrites it) but redundant work.

Aggregation jobs are identified by `job_type="aggregation"` (runner
registry), not a `TargetType` value — `TargetType` has no
`AGGREGATION` member and doesn't need one.

## Code flow

### Path 2 — CSV upload, file by file

```mermaid
flowchart TD
    A["POST /v1/sync/dispatch<br/><code>api/v1/data_sync.py:716</code><br/>sync_module_data_entries"] -->|"creates DataIngestionJob (csv_ingest)<br/>+ Pipeline row, then<br/>fire_and_forget(run_job) :924"| B

    B["<b>run_job</b><br/><code>tasks/runner.py:49</code><br/>claim → heartbeat → handler →<br/>preemption check → FINISHED write"] --> C

    C["csv_ingest_handler<br/><code>tasks/ingestion_tasks.py:42</code>"] -->|"_run_ingest :227"| D["CSV providers<br/><code>services/data_ingestion/base_csv_provider.py</code><br/>writes <b>data_entries</b><br/>(+ legacy inline stats :1082)"]

    C -->|"_chain_emission_recalc_for_data_ingest :423<br/>one child per stale (det, year)"| E["chain_job<br/><code>tasks/_chain.py:153</code><br/>creates child row, dedup-guarded;<br/>dispatch deferred until parent's<br/>FINISHED commit (drain in runner :283)"]

    E -->|"fire_and_forget(run_job)"| F

    F["emission_recalc_handler<br/><code>tasks/emission_recalculation_tasks.py:284</code><br/>factor-recalc advisory lock"] --> G["EmissionRecalculationWorkflow<br/><code>workflows/emission_recalculation.py:30</code><br/>bulk factor rematch + per-entry SAVEPOINT<br/>writes <b>data_entry_emissions</b>"]

    F -->|"_is_last_recalc_sibling :103<br/>only the LAST sibling chains"| H["chain_job → aggregation<br/>(AGGREGATION_DEDUP)"]

    H -->|"fire_and_forget(run_job)"| I["aggregation_handler<br/><code>tasks/aggregation_tasks.py:87</code><br/>CarbonReportModuleService.recompute_stats<br/>writes <b>carbon_reports.stats</b>"]

    B -.->|"after FINISHED write :338<br/>(every job, incl. C, F, I)"| J["recompute_pipeline_status<br/><code>repositories/data_ingestion.py:595</code><br/>resolves the Pipeline row"]

    K["reconcile_pipeline_statuses_loop<br/><code>tasks/_pipeline_reconciler.py:103</code><br/>+ _recover_orphan_aggregations :37"] -.->|"periodic backstop"| J
    L["poll_pending_jobs<br/><code>tasks/_poller.py:89</code>"] -.->|"re-dispatches orphaned<br/>QUEUED jobs (pod crash)"| B
```

Every job — ingest, recalc, aggregation — runs through the same
`run_job` runner; handlers are looked up via `@register("<job_type>")`
in `tasks/registry.py`. The runner, not the handlers, answers "who
resolves the pipeline": after each FINISHED write it calls
`recompute_pipeline_status`, so the pipeline flips to done when its
last child (normally the trailing aggregation) finishes. The
reconciler loop and the poller are crash/race backstops only.

Progress reaches the UI via SSE: `GET /v1/sync/jobs/{job_id}/stream`
(`api/v1/data_sync.py:1318`) streams job state; per-pipeline progress
is derived read-side by `compute_pipeline_progress`
(`services/pipeline_progress.py:120`) from the job rows.

### Background loops — poller, reconciler, heartbeat

Path 2's primary dispatch is in-process `fire_and_forget(run_job)` —
no loop involved. Three lifespan-managed loops (started in
`main.py`'s lifespan context, each gated by a `RUN_*` setting) cover
the failure modes:

```mermaid
flowchart TD
    M["FastAPI lifespan startup<br/><code>app/main.py:61-95</code>"] --> P & R & H

    P["<b>Safety poller</b><br/><code>tasks/_poller.py:87</code> poll_pending_jobs<br/>every <b>2 s</b> (POLLER_INTERVAL_SECONDS)"]
    P --> P1["Sweep 1: sweep_stuck_running_jobs<br/><code>repositories/data_ingestion.py:1126</code><br/>RUNNING + locked_at older than<br/><b>60 min</b> (STALE_JOB_TIMEOUT_MINUTES)<br/>→ NOT_STARTED, or FINISHED+ERROR<br/>when attempts ≥ max_attempts"]
    P --> P2["Sweep 2: _pending_runner_jobs_query :60<br/>NOT_STARTED, job_type NOT NULL,<br/>run_after due, unlocked, attempts &lt; max<br/>FOR UPDATE SKIP LOCKED,<br/><b>limit 100</b> (POLLER_BATCH_LIMIT)"]
    P2 -->|"schedule_job → fire_and_forget"| RUN["run_job<br/><code>tasks/runner.py:49</code>"]

    R["<b>Pipeline reconciler</b><br/><code>tasks/_pipeline_reconciler.py:103</code><br/>every <b>60 s</b> (PIPELINE_RECONCILER_INTERVAL_SECONDS)"]
    R --> R1["recompute_pipeline_status<br/>for non-terminal pipelines"]
    R --> R2["_recover_orphan_aggregations :37<br/>re-chains a missing trailing aggregation"]

    H["<b>Pod heartbeat</b><br/><code>tasks/_pod_heartbeat.py</code><br/>every <b>30 s</b> (POD_HEARTBEAT_INTERVAL_SECONDS)<br/>refreshes <code>pods.last_heartbeat_at</code><br/>backs GET /v1/sync/workers"]
```

Intervals and limits (defaults from `app/core/config.py`):

| Loop                | Interval                                | Limit / threshold                                                  | Off switch                |
| ------------------- | --------------------------------------- | ------------------------------------------------------------------ | ------------------------- |
| Safety poller       | 2 s (`POLLER_INTERVAL_SECONDS`, `ge=1`) | 100 jobs per sweep (`POLLER_BATCH_LIMIT`); stale-RUNNING at 60 min | `RUN_BACKGROUND_POLLER`   |
| Pipeline reconciler | 60 s (`ge=10`)                          | commits per pipeline                                               | `RUN_PIPELINE_RECONCILER` |
| Pod heartbeat       | 30 s (`ge=5`)                           | pod counts live within 2× interval                                 | `RUN_POD_HEARTBEAT`       |

Why a 2 s cadence is safe: each sweep is one `SELECT … FOR UPDATE
SKIP LOCKED LIMIT 100` — multi-pod deployments don't double-dispatch
(skip-locked) and an idle system costs one cheap indexed query per
pod per interval. The 60-min stale threshold must stay above the
longest plausible job runtime; below it, the sweep would preempt a
still-working pod and duplicate processing.

The poller never drives the happy path. A healthy upload flows
entirely through endpoint → `fire_and_forget` → `run_job` →
`chain_job` deferred dispatches; the poller only catches jobs whose
in-process Task died between the row commit and the runner claim
(pod crash, restart mid-deploy).

### Path 1 — interactive module edit

```mermaid
flowchart LR
    A["POST/PATCH/DELETE<br/>/v1/carbon_reports/...<br/>module edit endpoints"] --> B["CarbonReportModuleWorkflow<br/><code>workflows/carbon_report_module.py</code>"]
    B --> C["writes <b>data_entries</b>"]
    B --> D["DataEntryEmissionService<br/>writes <b>data_entry_emissions</b>"]
    B --> E["recompute_stats (inline)<br/>writes <b>carbon_reports.stats</b><br/>:108 :229 :262"]
```

One request, one transaction, all three tables written synchronously —
no jobs, no pipeline row, no SSE. The user's spinner _is_ the
progress indicator.

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
