---
status: delivered
issue: 1219
last_updated: 2026-05-19
title: "1219 Stuck ingestion/recalc jobs + premature pipeline 'success'"
summary: "Stage incident: a zombie emission_recalc row tripped uq_emission_recalc_active, the IntegrityError poisoned the runner's job_session, and the job never reached FINISHED — self-propagating the stall. Fixes runner session resilience, adds dedup to the csv/api fan-out, and makes pipeline completion server-authoritative with a 3-phase UI."
---

# 1219 — Stuck jobs + premature pipeline success

## Context

On **stage** (2026-05-19) a CSV equipment ingest (job 112) wrote its
50 072 rows, then crashed in the post-success fan-out with
`UniqueViolation: uq_emission_recalc_active (4, 10, 2025)`.

The duplicate key was a symptom. Root cause chain:

1. A prior `emission_recalc` for `(4,10,2025)` was stuck in an active
   state (zombie) — its work done but its row never finalized.
2. `uq_emission_recalc_active` is partial over
   `state IN (NOT_STARTED, QUEUED, RUNNING)`; the zombie permanently
   blocks new recalcs for that scope.
3. The failing INSERT raised `IntegrityError` on the runner's
   `job_session`; the runner never rolled it back, so the next query
   (`get_job_by_id`) raised `PendingRollbackError`, escaped the
   handler `except`, and `finish_job` was never called → job 112 also
   stuck. The defect self-propagates.
4. Separately, the UI showed a module green as soon as the parent
   upload finished — before recalc/aggregation children ran.

Root cause #3 is the single defect that both creates zombies and
spreads the stall. Adjacent to [#1057 follow-ups](310-d-architecture-followups.md)
(referenced, not superseded).

## What shipped

### Fix 1 — runner survives a poisoned `job_session` (core)

`backend/app/tasks/runner.py`: the handler-exception block now
`await job_session.rollback()` before the preempt-check / `finish_job`.
Every handler failure now durably writes `FINISHED + ERROR` (visible
in the UI) instead of stranding the job `RUNNING`.

### Fix 2 / 2b — dedup + owned-child count on the csv/api fan-out

`backend/app/tasks/ingestion_tasks.py`:
`_chain_emission_recalc_for_data_ingest` now passes
`dedup_config=EMISSION_RECALC_DEDUP` (mirrors the factor path) — a
pre-existing active recalc is a logged no-op, not an uncaught
`IntegrityError`. Both fan-out helpers now count only children they
actually created (`chain_job` returning non-`None`); a dedup-skipped
target is owned by an earlier pipeline and excluded from
`recalc_jobs_chained`.

### Fix 3 — server-authoritative completion + 3-phase UI

`backend/app/services/pipeline_progress.py` (`compute_pipeline_progress`):
derives phase/done/error from the _expected_ fan-out recorded in job
meta (`recalc_jobs_chained`, `aggregation_job_id`), not from a
possibly-incomplete snapshot. Phases: **data → emissions →
aggregation**. `done` ⇔ phase 3 satisfied **or** any job
`FINISHED+ERROR`.

Wired into `data_sync.py`: the SSE stream closes on `progress.done`
and ships `progress` in every payload; `GET /sync/pipelines/{id}`
gained a `progress` field.

Frontend: `pipelineStream.ts` carries `progress`; `isFinishedFor`
trusts `progress.done` / `closed` (the old "all snapshot jobs
FINISHED" _success_ heuristic is gone — but a `FINISHED+ERROR` job
still counts as terminal, matching the backend's `done ⇔ phase3 OR
any FINISHED+ERROR` rule, so an errored pipeline shows the failure
badge even before an authoritative `progress` payload). `seedFromSnapshot`
forwards the one-shot endpoint's `progress` so the badge/card show the
phase immediately on subscribe, not only after the first ~2s SSE poll. `ModuleConfig.vue` shows
`Step N/3 · …` per phase.

`ModuleConfig.vue` also `provide()`s the module's reactive
`pipelineProgress`; `ModuleUploadsSection.vue` injects it and threads
it through `UploadCardData` / `UploadCardFactors` into the shared
`UploadCard.vue`, which renders the live `Step N/3 · …` phase line per
card while the pipeline runs (hidden once done/errored). The pipeline
is module-scoped, so every card in a module reflects the same phase —
a single SSE subscription, no per-card streams.

> **Intentional edge case:** if every recalc target was dedup-skipped
> (an earlier active pipeline owns them), `recalc_jobs_chained == 0`,
> so the badge advances to "Aggregated" once the parent finishes. The
> recalc work _is_ dispatched — under the owning pipeline's id.

### Remediation (manual, post-deploy on stage)

Use `POST /v1/sync/jobs/{id}/cancel` (immediate `FINISHED+ERROR`, no
stale wait) on the zombie recalc + job 112 and any 30-min-stale
siblings. Inspect first:

```sql
SELECT id, job_type, state, module_type_id, data_entry_type_id, year, locked_at
FROM data_ingestion_jobs
WHERE state IN ('NOT_STARTED','QUEUED','RUNNING')
  AND (locked_at IS NULL OR locked_at < now() - interval '30 minutes')
ORDER BY id;
```

## Verification

- `backend`: `uv run pytest tests/unit/tasks/test_runner.py
tests/unit/tasks/test_ingestion_handlers.py
tests/unit/services/test_pipeline_progress.py tests/unit/tasks/test_chain.py`
  — 52 pass. The Fix-1 regression test simulates the
  `PendingRollbackError` state and is verified to fail when the
  rollback is reverted.
- `frontend`: `tsc` clean; lint clean. Playwright (rebuilt SPA):
  `pipeline-diagnostic-tooltip.spec.ts` 8 passed / 1 skipped (incl.
  the new Issue-#1219 case and the restored FINISHED+ERROR case);
  `data-management.spec.ts` 14 passed / 1 skipped.
- Pre-existing unrelated flake:
  `test_reference_data.py::test_reference_ingest_handler_is_registered`
  fails only under combined-suite ordering on clean `dev` (registry
  snapshot); passes in isolation. Out of scope.
