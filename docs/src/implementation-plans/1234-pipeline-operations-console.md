# 1234 — Pipeline operations console

Status: in progress · Branch: `feat/1234-pipeline-operations-console` · Base: `dev`

## Problem

`/back-office/data-management` shows per-module ingestion status only. There is
no global view of pipelines. Operators cannot see, across all modules/years:
failed parents, transaction-poisoning, deadlocks between sibling recalc jobs, or
anomalous runs.

Live data shows the failure shapes the page must surface:

- `csv_ingest` `status_message="Success"` but `result=ERROR` (100% row errors).
- `InFailedSqlTransaction` on the `carbon_report_modules` SELECT — parent
  ERROR, no `pipeline_id`, no children (carbon-report-stats poisoning).
- `DeadlockDetected` between concurrent `emission_recalc`/`aggregation`
  siblings of the **same** `pipeline_id`.
- One `csv_ingest` → 3 `emission_recalc` → 3 `aggregation`, each
  `modules_refreshed: 2231` (concurrent full-table recompute amplification).

## Outcome

A new back-office page, complementary to data-management. Unit = the pipeline
(one `pipeline_id` = a DAG: ingest parent → per-det `emission_recalc` →
`aggregation`, edges via `meta.parent_job_id`). Pipeline-grouped table, alert
strip, filters, expandable job DAG with decoded meta. Orphan parents
(`pipeline_id IS NULL`) shown inline as pipelines-of-one.

## Scope

- ONE new backend list endpoint. Reuse — do not rebuild — `GET
/v1/sync/pipelines/{id}` and `/stream` for drill-down/live.
- No migration (all derived from `data_ingestion_jobs`).
- No change to `/back-office/data-management`.
- NOT bundling PR #1225 or the eager-pipeline-id work. This endpoint only
  reads existing `pipeline_id` values; orphan rows are surfaced regardless.

## Steps

### Backend

- **B1** `backend/app/repositories/data_ingestion.py` —
  `list_pipelines_paginated(...)`. Pagination unit is `pipeline_id`, not the
  job row. Group/filter in SQL (no `DISTINCT ON` — SQLite test fixture),
  page on `pipeline_id`, then one `IN (:page_ids)` fetch grouped in Python.
  Orphans (`pipeline_id IS NULL`) as synthetic pipelines-of-one. Returns a
  Pydantic-free typed dict.
- **B2** `backend/app/api/v1/data_sync.py` — `GET /sync/pipelines`
  (registered before `/pipelines/{pipeline_id}`). Inline schemas
  `PipelineListItem` / `PipelineListResponse`, reusing
  `PipelineProgressResponse` + `compute_pipeline_progress`. Meta projection
  is an **allow-list** (`parent_job_id`, `recalc_jobs_chained`,
  `aggregation_job_id`, `provider_name`, `filters`) — never ship
  `error_details` / `affected_module_ids` (KB-scale). Permission gate copied
  from `get_active_pipelines` (global `backoffice.data_management.view` +
  per-module decision, drop not 403).
- **B3** tests — extend
  `backend/tests/unit/repositories/test_data_ingestion_repo.py`: grouping,
  pipeline-unit pagination, each filter, orphans, meta allow-list strips the
  big arrays.

### Frontend

- **F1** `frontend/src/i18n/pipeline_operations_console.ts` (auto-globbed;
  en + fr; nav keys included).
- **F2** `frontend/src/constant/navigation.ts` — `BACKOFFICE_NAV` entry.
- **F3** `frontend/src/router/routes.ts` — `back-office/pipeline-operations`
  route, same `beforeEnter`/`meta` as the data-management sibling.
- **F4** `frontend/src/stores/pipelineOperationsConsole.ts` +
  `frontend/src/pages/back-office/PipelineOperationsConsolePage.vue`. Alert
  strip (clickable counters → filters), pipeline-grouped table (newest
  first), expandable job DAG with decoded meta. Drill-down/live reuses
  `usePipelineStream()` verbatim.
- **F5** `cd frontend && make type-check` (vue-tsc — the gate husky runs;
  `rtk tsc` green ≠ this).

## Verify

- Backend: `cd backend && uv run ruff check . && uv run pytest
tests/unit/repositories/test_data_ingestion_repo.py
tests/unit/services/test_pipeline_progress.py -q` and `python -c "from
app.main import app"`.
- Frontend: `cd frontend && make type-check`.

## Convention notes

PRs target `dev`. Commit messages: **no** `Co-Authored-By` trailer.
