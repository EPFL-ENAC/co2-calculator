# Bot Review TODOs: PR #1023

## Source Branch: `feat/310c-pipeline-list-endpoint`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds a new backoffice-facing read endpoint to fetch all ingestion/recalculation jobs belonging to a single pipeline run (shared `pipeline_id`), enabling the dashboard to render the full multi-step chain (parent FACTORS job + fan-out children).

**Changes:**

- Added `DataIngestionRepository.list_jobs_by_pipeline_id()` to fetch pipeline jobs ordered by `id ASC`.
- Added `GET /v1/sync/pipelines/{pipeline_id}` (permission-gated) plus `PipelineResponse` / `PipelineJobResponse` response schemas.
- Added Postgres-backed integration tests covering ordering, isolation, 404 for unknown pipeline UUID, and 403 for missing permission.

### Reviewed changes

Copilot reviewed 3 out of 3 changed files in this pull request and generated 2 comments.

| File                                                                                | Description                                                                                         |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| backend/app/repositories/data_ingestion.py                                          | Adds repository query to list jobs by `pipeline_id` in deterministic order.                         |
| backend/app/api/v1/data_sync.py                                                     | Introduces pipeline response schemas and the new `/sync/pipelines/{pipeline_id}` endpoint.          |
| backend/tests/integration/services/data_ingestion/test_sync_pipeline_endpoint_pg.py | Adds end-to-end PG integration coverage for the new endpoint (ordering/filtering/auth/error cases). |

---

### File: `backend/tests/integration/services/data_ingestion/test_sync_pipeline_endpoint_pg.py` (Line 16) — Copilot

The module docstring claims the endpoint exposes the `target_type` enum column, but the new `/v1/sync/pipelines/{pipeline_id}` response schema does not include `target_type`. Update the docstring to match the actual response (or add `target_type` to the response and assert it in the tests).

---

### File: `backend/app/repositories/data_ingestion.py` (Line 144) — Copilot

## `list_jobs_by_pipeline_id` filters by `pipeline_id`, but `data_ingestion_jobs` does not appear to have an index on `pipeline_id`. If this table grows, this endpoint can degrade into a sequential scan; consider adding a (possibly partial) Postgres index on `pipeline_id` via an Alembic migration to keep lookups fast.

## Action Items

### Performance

- [ ] **backend/app/repositories/data_ingestion.py**: `list_jobs_by_pipeline_id` filters `data_ingestion_jobs` by `pipeline_id` with no index on that column. Add a Postgres index (partial if appropriate) via Alembic migration so the endpoint avoids sequential scans as the table grows.

### Maintainability / refactoring

- [ ] **backend/tests/integration/services/data_ingestion/test_sync_pipeline_endpoint_pg.py**: Module docstring claims the endpoint exposes the `target_type` enum column, but the `PipelineJobResponse` schema does not include it. Either update the docstring to match the actual response or add `target_type` to the schema and assert on it in the tests.
