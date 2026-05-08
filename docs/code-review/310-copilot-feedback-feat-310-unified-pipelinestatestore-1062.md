# Bot Review TODOs: PR #1075

Source Branch: `feat/310-unified-pipeline-state-store`
PR Title: feat(310): unified pipelineStateStore [#1062]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR unifies “active bulk pipeline” state into a single backend endpoint (`GET /v1/sync/active-pipelines`) and a single frontend Pinia store (`pipelineStateStore`), removing the previously duplicated `current_pipeline_id` enrichment from carbon report modules and year configuration recalculation status.

**Changes:**

- Backend: add `GET /sync/active-pipelines` thin wrapper around `DataIngestionRepository.get_current_pipeline_ids_for_modules`, permission-gated.
- Frontend: introduce `pipelineStateStore` keyed by `(module_type_id, year)` and update `ModuleConfig.vue` to use it for the “Recalculating…” badge lifecycle.
- Remove `current_pipeline_id` from backend/FE schemas and delete the now-obsolete service-layer unit test.

### Reviewed changes

Copilot reviewed 12 out of 12 changed files in this pull request and generated 1 comment.

<details>
<summary>Show a summary per file</summary>

| File                                                                                   | Description                                                                                           |
| -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| frontend/src/stores/yearConfig.ts                                                      | Drops `current_pipeline_id` from the recalculation-status entry type.                                 |
| frontend/src/stores/pipelineState.ts                                                   | Adds unified store + bulk loader for active pipeline ids per `(module_type_id, year)`.                |
| frontend/src/stores/modules.ts                                                         | Removes `current_pipeline_id` from carbon report modules response typing and timeline store state.    |
| frontend/src/components/organisms/data-management/ModuleConfig.vue                     | Switches “Recalculating…” badge to read from `pipelineStateStore` and refresh on year/job completion. |
| backend/app/api/v1/data_sync.py                                                        | Adds `GET /sync/active-pipelines` endpoint (permission-gated).                                        |
| backend/app/api/v1/year_configuration.py                                               | Removes pipeline-id enrichment from recalculation status builder.                                     |
| backend/app/api/v1/carbon_report.py                                                    | Stops passing `year=` for module pipeline enrichment (now removed).                                   |
| backend/app/services/carbon_report_module_service.py                                   | Removes `current_pipeline_id` enrichment path from `list_modules`.                                    |
| backend/app/schemas/year_configuration.py                                              | Drops `current_pipeline_id` field from schema.                                                        |
| backend/app/schemas/carbon_report.py                                                   | Drops `current_pipeline_id` field from schema.                                                        |
| backend/tests/integration/services/data_ingestion/test_active_pipelines_endpoint_pg.py | Adds PG integration coverage for the new endpoint (wire shape + permissions).                         |
| backend/tests/unit/services/test_carbon_report_module_service_pipeline.py              | Removes obsolete unit tests tied to the dropped enrichment.                                           |

</details>

---

### File: `frontend/src/stores/pipelineState.ts` (Line 75) — Copilot

`api` is configured with `prefixUrl: '/api/v1/'`, so calling `.get('v1/sync/active-pipelines?...')` will hit `/api/v1/v1/sync/active-pipelines` (duplicate `v1`) and the request will 404. This should be `sync/active-pipelines?...` (or use `searchParams` without embedding the version prefix).

---
