---
status: delivered
issue: 2371
last_updated: 2026-08-26
title: "Job runner: one OTel span per job execution"
summary: "Wrap each claimed job execution and each pipeline-reconciler sweep in an OTel span so background-job SQL nests under a parent trace instead of flooding Tempo as parentless root spans."
---

# Job runner: one OTel span per job execution

## Problem

Background-job SQL statements export as parentless root spans: every
`UPDATE pipelines SET ...` / `SELECT` emitted from the job runner is its
own single-span trace in Tempo. During the 2026-08-25 stage
investigation (#2360) this flooded trace search — HTTP requests nest
their SQL correctly (the request span is the parent), background jobs
don't, so job activity is impossible to read as a unit and filtering
endpoint traces from SQL noise needs `{kind=server}` gymnastics.

Two emitters, both outside any span:

1. **Job handlers** — everything dispatched through
   `app/tasks/runner.py::run_job` (handler SQL, `finish_job`, the
   post-commit `recompute_pipeline_status`, heartbeat ticks).
2. **The pipeline reconciler sweep**
   (`app/tasks/_pipeline_reconciler.py`) — the
   `UPDATE pipelines SET expected_recalc/status/job_count` bookkeeping
   seen as root traces at 2026-08-25 15:47:12 comes from
   `recompute_pipeline_status` on the sweep cadence.

## Solution

Telemetry-only — zero changes to pipeline/job logic, ordering, sessions,
or transactions. `opentelemetry-distro` is already a direct dependency;
without the OTLP env vars (local/tests) the API is a no-op, so no config
plumbing.

1. **`run_job`** opens one span per claimed job execution, named
   `job <type>` (reads well in Tempo search), with attributes `job.id`,
   `job.type`, and `pipeline.id` when the job carries one. The span is
   started manually (`tracer.start_span` + `context.attach`) right after
   the post-claim re-fetch — before the heartbeat task is created, so
   the heartbeat's `UPDATE`s inherit the context too — and detached +
   ended in the existing `finally`. Manual start/attach instead of a
   `with` block keeps the runner's heartbeat/preemption try/finally
   structure untouched. Async SQLAlchemy instrumentation picks the span
   up from the OTel context, so all SQL emitted during the job nests
   under it.
2. **The reconciler loop** wraps each sweep iteration in a
   `pipeline reconcile sweep` span (one span per orchestration step,
   not per statement), covering `reconcile_pipeline_statuses` and the
   orphan-aggregation backfill.

Pre-claim SQL (the initial `get_job_by_id` + `claim_job`) stays outside
the span by design: the span represents a _claimed_ execution, and a
no-op `run_job` probe (already claimed / finished) should not mint a
trace.

## What changed

- `backend/app/tasks/runner.py` — module-level
  `tracer = trace.get_tracer(__name__)`; span start + attribute stamping
  after the post-claim re-fetch; `context.detach` + `span.end()` in the
  existing `finally`.
- `backend/app/tasks/_pipeline_reconciler.py` — sweep body wrapped in
  `tracer.start_as_current_span("pipeline reconcile sweep")`.
- `backend/tests/unit/tasks/test_runner.py` —
  `test_run_job_handler_runs_inside_job_span`: a local SDK
  `TracerProvider` + `InMemorySpanExporter` patched onto the runner's
  tracer; a stub handler captures the current span mid-run and the test
  asserts it is the recording `job test_job` span (matching span id,
  `job.id`/`job.type` attributes) and that exactly one span is exported
  after `run_job` returns.

## Verification

- `uv run pytest backend/tests/unit/tasks/test_runner.py -x` — new span
  test plus the existing runner matrix pass.
- `make lint` / `make type-check` pass on the backend.
- On stage (OTLP configured): job SQL appears as children of
  `job <type>` traces; reconciler bookkeeping appears under
  `pipeline reconcile sweep` — no more parentless SQL root spans from
  background work.
