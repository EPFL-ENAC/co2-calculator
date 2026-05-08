# Bot Review TODOs: PR #1052

## Source Branch: `feat/310d-pipeline-sse-endpoint`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds backend support for Plan 310D “stale-stats” UX by exposing (1) the currently-active recalculation pipeline for a module and (2) an SSE stream to observe pipeline job progress in real time.

**Changes:**

- Add `DataIngestionRepository.get_current_pipeline_id_for_module(module_type_id)` to resolve the most recent active pipeline UUID for a module.
- Add `GET /v1/sync/pipelines/{pipeline_id}/stream` SSE endpoint emitting `pipeline-update` events plus `ping` heartbeats and a final `stream_closed` marker.
- Add unit + PG integration tests covering the repo helper and the stream endpoint contract (403/404 behaviors).

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated 2 comments.

| File                                                                                       | Description                                                                        |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| backend/app/repositories/data_ingestion.py                                                 | Adds active-pipeline lookup helper for module-scoped stale-stats UX.               |
| backend/app/api/v1/data_sync.py                                                            | Adds SSE streaming endpoint for pipeline job updates + heartbeat and close marker. |
| backend/tests/unit/repositories/test_data_ingestion_repo.py                                | Adds unit tests for `get_current_pipeline_id_for_module`.                          |
| backend/tests/integration/services/data_ingestion/test_sync_pipeline_stream_endpoint_pg.py | Adds PG integration tests for stream endpoint contract (403/404).                  |

---

### File: `backend/app/api/v1/data_sync.py` (Line 852) — Copilot

## `pipeline_stream_by_id` re-polls via `repo.list_jobs_by_pipeline_id()`, which returns ORM instances without a refresh. In this codebase, job state can change via out-of-band UPDATEs (e.g. `claim_job` / runner lifecycle), and the session identity map can keep previously-loaded instances stale unless they are refreshed. This can cause the SSE stream to miss state/result/message changes and never emit updates. Consider polling with a column-only SELECT (returning plain rows/dicts) or using `populate_existing=True` / explicit `session.refresh()` so each tick reads the latest DB values without relying on cached ORM instances.

### File: `backend/app/api/v1/data_sync.py` (Line 754) — Copilot

Docstring says updates are emitted when the `(state, status_message, result, finished_at)` tuple changes, but the emitted snapshot also includes `started_at` (and `job_type`/`id`). Either update the docstring to match the actual change-detection fields, or adjust the snapshot comparison to only include the documented tuple so client expectations stay aligned.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/repositories/data_ingestion.py` (`list_jobs_by_pipeline_id`) and `backend/app/api/v1/data_sync.py` (`pipeline_stream_by_id`)** — the SSE stream will silently fail to emit updates in production. The poll loop calls `list_jobs_by_pipeline_id(pipeline_id)` inside a single long-lived `db: AsyncSession`. SQLAlchemy's identity map keeps the originally-loaded `DataIngestionJob` instances cached; out-of-band UPDATEs from another session (the runner's `claim_job`, `update_ingestion_job`, heartbeat, FINISHED transition — all on `SessionLocal()` connections separate from the request session) are NOT reflected on subsequent `SELECT`s, so `snapshot != last_snapshot` always evaluates False and the wire stays silent until the connection finally drops. The agent's PR report admits the streaming-body assertion was deferred due to an asyncpg+httpx interaction — that's exactly why this bug slipped through. **Fix**: add `.execution_options(populate_existing=True)` to the `select(...)` inside `list_jobs_by_pipeline_id` (one-line change in the repo method). This forces SQLAlchemy to overwrite the identity-map entry with the freshly-loaded row each poll. Alternatively, `await db.expire_all()` at the top of each poll tick — simpler but more heavy-handed. **Add a streaming regression test** that mutates a job state mid-stream via a separate session and asserts the next `pipeline-update` event reflects the new state — even if the asyncpg+httpx limitation means the test runs against a stub session, the contract needs proof. Copilot's diagnosis is correct; do not skip.

### Maintainability / refactoring

- [ ] **`backend/app/api/v1/data_sync.py:749`** — docstring says updates fire when `(state, status_message, result, finished_at)` changes, but the actual snapshot equality check covers 7 fields (`id`, `job_type`, `state`, `result`, `status_message`, `started_at`, `finished_at`). `id` and `job_type` are immutable post-create so they never trigger an emit, but `started_at` is mutable (stamped on first RUNNING transition via #1026's `func.coalesce`). **Fix**: update the docstring to add `started_at` to the listed change-detection tuple. Don't shrink the snapshot — the wider payload is what the frontend consumes, and `started_at` IS a meaningful change to surface (transition NOT_STARTED → RUNNING).
