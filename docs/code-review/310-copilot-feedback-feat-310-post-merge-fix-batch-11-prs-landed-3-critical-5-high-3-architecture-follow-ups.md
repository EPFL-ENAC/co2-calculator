# Bot Review TODOs: PR #1079

## Source Branch: `feat/310/dev`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Integration batch for Plan 310 post-merge fixes plus architecture follow-ups, spanning backend ingestion safety/deduping/observability and frontend pipeline-state unification + accessibility improvements.

**Changes:**

- Backend: harden ingestion runner/pipeline mechanics (FINISHED CAS, heartbeat-driven abort, generalized `chain_job` dedup + new `emission_recalc` partial unique index, SSE per-iteration DB sessions + disconnect detection + pipeline/job scope checks, stale-stats health probe).
- Backend ingestion correctness: persist `kg_co2eq` overrides across async recomputation; seed provider bypasses `BULK_PATH_PURE_ASYNC` gate.
- Frontend: introduce `pipelineState` Pinia store backed by `GET /v1/sync/active-pipelines`, remove `current_pipeline_id` from older response shapes, and make pipeline diagnostic tooltip usable on keyboard focus.

### Reviewed changes

Copilot reviewed 43 out of 43 changed files in this pull request and generated 4 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                       | Description                                                                                                            |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| frontend/src/stores/yearConfig.ts                                                          | Removes `current_pipeline_id` from year-config recalculation status typing.                                            |
| frontend/src/stores/pipelineState.ts                                                       | New Pinia store to bulk-load active pipeline IDs per `(module_type_id, year)`.                                         |
| frontend/src/stores/modules.ts                                                             | Drops `current_pipeline_id` from carbon-report module response and timeline store state.                               |
| frontend/src/components/organisms/data-management/ModuleConfig.vue                         | Wires badge state to `pipelineStateStore`, refreshes on completion, and adds focus/blur-driven tooltip a11y.           |
| frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue            | Exposes Quasar tooltip `show()`/`hide()` so parent can open it on focus.                                               |
| docs/src/implementation-plans/310-post-merge-fix-batch.md                                  | New orchestration plan document for the 310 post-merge fix batch.                                                      |
| docs/src/implementation-plans/310-d-frontend-stale-stats.md                                | Updates stale-stats plan with keyboard-accessible tooltip mechanism details.                                           |
| docs/src/implementation-plans/310-d-architecture-followups.md                              | Adds umbrella plan doc for 310-D follow-ups (observability, dedup, unified store).                                     |
| backend/tests/unit/tasks/test_runner.py                                                    | Updates runner unit tests for `finish_job` + heartbeat abort signature changes.                                        |
| backend/tests/unit/tasks/test_runner_heartbeat_abort.py                                    | New unit tests for heartbeat-failure abort behavior.                                                                   |
| backend/tests/unit/tasks/test_handler_registrations.py                                     | Updates handler registration tests for dedup-config and WARNING chaining behavior.                                     |
| backend/tests/unit/services/test_carbon_report_module_service_pipeline.py                  | Removes service-layer tests for now-deleted `current_pipeline_id` enrichment.                                          |
| backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py        | Pins travel API override carrier persistence behavior.                                                                 |
| backend/tests/unit/services/data_ingestion/test_base_csv_provider.py                       | Pins CSV override carrier persistence behavior.                                                                        |
| backend/tests/unit/services/data_ingestion/csv_providers/test_local_seed_async_gate.py     | New unit tests ensuring seed runs bypass the pure-async gate.                                                          |
| backend/tests/integration/services/data_ingestion/test_sync_pipeline_stream_endpoint_pg.py | Adds/updates SSE PG integration tests for disconnect + per-pipeline scope checks.                                      |
| backend/tests/integration/services/data_ingestion/test_sync_pipeline_endpoint_pg.py        | Adjusts pipeline endpoint tests for the new module-scope checks.                                                       |
| backend/tests/integration/services/data_ingestion/test_stale_stats_endpoint_pg.py          | New PG integration tests for stale-stats health endpoint bucketing.                                                    |
| backend/tests/integration/services/data_ingestion/test_pod_safety_310a.py                  | Updates integration tests to bypass new module-scope checks where needed.                                              |
| backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py               | Adds PG coverage for claim IntegrityError logging + `finish_job` CAS preemption behavior.                              |
| backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py  | New PG integration tests for async-path kg-co2eq override preservation.                                                |
| backend/tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py             | Adds PG integration regression test that aggregation chains on WARNING.                                                |
| backend/tests/integration/services/data_ingestion/test_emission_recalc_dedup_pg.py         | New PG integration tests for `emission_recalc` dedup behavior.                                                         |
| backend/tests/integration/services/data_ingestion/test_active_pipelines_endpoint_pg.py     | New PG integration tests for `/v1/sync/active-pipelines`.                                                              |
| backend/app/tasks/runner.py                                                                | Implements heartbeat abort, switches terminal writes to `finish_job` CAS, updates comments.                            |
| backend/app/tasks/ingestion_tasks.py                                                       | Uses `EMISSION_RECALC_DEDUP` when chaining stale-factor-triggered recalcs.                                             |
| backend/app/tasks/emission_recalculation_tasks.py                                          | Chains aggregation on WARNING and uses `AGGREGATION_DEDUP` via `dedup_config`.                                         |
| backend/app/tasks/\_chain.py                                                               | Introduces `DedupConfig`, adds `EMISSION_RECALC_DEDUP`, and keeps `dedup_active` shim.                                 |
| backend/app/services/data_ingestion/csv_providers/local_seed.py                            | Marks seed provider as `is_seed_run=True` to bypass async gate.                                                        |
| backend/app/services/data_ingestion/base_csv_provider.py                                   | Persists override carrier and bypasses async gate when `is_seed_run=True`.                                             |
| backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py      | Persists travel override carrier; fixes `0`/`0.0` override handling.                                                   |
| backend/app/services/data_entry_emission_service.py                                        | Adds `KG_CO2EQ_OVERRIDE_KEY` and uses it as fallback override in `prepare_create`.                                     |
| backend/app/services/carbon_report_module_service.py                                       | Removes `current_pipeline_id` enrichment from `list_modules`.                                                          |
| backend/app/schemas/year_configuration.py                                                  | Drops `current_pipeline_id` from API schema.                                                                           |
| backend/app/schemas/carbon_report.py                                                       | Drops `current_pipeline_id` from API schema.                                                                           |
| backend/app/repositories/data_ingestion.py                                                 | Adds `finish_job` CAS, adds claim-job logging, and adds stale-aggregation query helper/types.                          |
| backend/app/models/data_ingestion.py                                                       | Documents `is_current` partial-unique-index job_type discrimination rationale.                                         |
| backend/app/api/v1/year_configuration.py                                                   | Removes recalculation-status `current_pipeline_id` enrichment.                                                         |
| backend/app/api/v1/data_sync.py                                                            | Adds `/active-pipelines` + `/health/stale-stats`; refactors SSE to per-iteration sessions + disconnect + scope checks. |
| backend/app/api/v1/carbon_report.py                                                        | Stops returning `current_pipeline_id` in carbon-report modules endpoint.                                               |
| backend/alembic/versions/2026_05_07_1432-f8a9b1c2d3e4_emission_recalc_dedup_index.py       | Adds `uq_emission_recalc_active` partial unique index concurrently.                                                    |
| backend/alembic/versions/2026_03_24_1703-253e62d79609_update_data_ingestion_index.py       | Updates migration docstring with job_type-discrimination rationale.                                                    |

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 43 out of 43 changed files in this pull request and generated 3 comments.

---

### File: `backend/app/tasks/runner.py` (Line 182) — github-advanced-security[bot]

## CodeQL / Empty except

'except' clause does nothing but pass and there is no explanatory comment.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/649)

### File: `backend/tests/unit/tasks/test_handler_registrations.py` (Line 220) — Copilot

## The WARNING-path assertion is still checking `dedup_active`, but `emission_recalc_handler` now chains aggregation with `dedup_config=AGGREGATION_DEDUP`. This will fail because `dedup_active` is no longer passed. Update the assertion to check `dedup_config` (consistent with the success-path test above).

### File: `frontend/src/components/organisms/data-management/ModuleConfig.vue` (Line 54) — Copilot

## `getModuleTypeIdFromName()` returns `0` when the module name is unknown. `refreshPipelineState()` will still call `loadFor(..., [0])`, creating a `modules=0` request and caching a `0:<year>` entry. Consider guarding on a falsy `moduleTypeId` (as other `useModuleConfig` helpers do) to avoid unnecessary calls and confusing cache keys.

### File: `backend/app/api/v1/data_sync.py` (Line 891) — Copilot

`get_pipeline_jobs` fetches `jobs` via `list_jobs_by_pipeline_id`, then `_check_pipeline_scope` immediately fetches the same job list again. Consider passing the already-fetched `jobs` into the scope-check helper (or adding a helper that checks scope from an existing job list) to avoid the redundant DB round-trip on a hot endpoint.

---

### File: `backend/app/api/v1/data_sync.py` (Line 776) — Copilot

## `GET /sync/active-pipelines` is only gated by the global `backoffice.data_management.view` permission. Since it returns pipeline UUIDs that can then be used to probe other pipeline endpoints, it should likely apply the same per-module/pipeline scope checks introduced elsewhere in this file (e.g. `_check_pipeline_scope`/`_check_job_scope` or `check_module_permission`) to avoid cross-scope leakage of active pipeline IDs.

### File: `backend/app/tasks/_chain.py` (Line 426) — Copilot

In the IntegrityError dedup path, `msg = str(getattr(exc.orig, "diag", None) or exc)` is likely to miss the constraint name when using psycopg, because `exc.orig.diag` is a diagnostics object whose `str(...)` may not contain `constraint_name`. That would cause expected dedup collisions to raise instead of returning `None`, breaking `chain_job` under concurrent fan-out. Prefer checking `getattr(getattr(exc.orig, "diag", None), "constraint_name", None)` (or equivalent driver-specific field) against `dedup_config.constraint_name`, and only fall back to message parsing if that attribute is missing.

---

### File: `docs/src/implementation-plans/310-d-architecture-followups.md` (Line 27) — Copilot

## This plan doc still contains PR-number and status placeholders (e.g. `Delivered in PR #<TBD>`), but the corresponding follow-up has landed in this batch. Please replace the placeholder with the actual PR number and update the status section accordingly so the rendered plan stays accurate.

### File: `docs/src/implementation-plans/310-d-architecture-followups.md` (Line 98) — Copilot

## Follow-up 2 and 3 sections are still marked as `<TBD>` / `Pending`, but this PR description indicates #1062/#1064 work is included in the post-merge batch. If these follow-ups are now delivered, update this document to remove the placeholders and link to the actual PR(s) so future readers don’t treat completed work as outstanding.

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/tasks/_chain.py:423`** — `msg = str(getattr(exc.orig, "diag", None) or exc).lower()` may miss the `constraint_name` on psycopg drivers (the diag object's `__str__` is implementation-defined and often lacks the constraint identifier). When that happens an expected dedup race-loss raises instead of returning `None`, breaking concurrent fan-out. Fix: read the field directly — `constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)`; treat-as-dedup if `constraint == dedup_config.constraint_name`; fall back to the lowercase substring match only when `constraint is None` (covers the asyncpg path that exposes nothing structured). Bot got the fix shape right.
- [ ] **`backend/app/api/v1/data_sync.py:768-799`** (`GET /sync/active-pipelines`) — endpoint returns active `pipeline_id`s for every requested `module_type_id` with only the global `backoffice.data_management.view` gate. The pipeline IDs are usable as input to the per-pipeline `/sync/pipelines/{id}` family, which IS scoped, so the leak is just enumeration of pipeline UUIDs across modules the caller can't read. Fix: filter the response to modules that pass `_check_module_permission_for_unit` (or the equivalent helper) — drop entries the caller has no access to rather than 403-ing the whole endpoint. Add `# TODO(#459)` for the post-scoping tightening.
- [ ] **`frontend/src/components/organisms/data-management/ModuleConfig.vue:51-54`** — `refreshPipelineState` calls `loadFor(year, [getModuleTypeIdFromName(props.module)])` without guarding on the `0` sentinel that `getModuleTypeIdFromName` returns for unknown modules. That fires `GET /v1/sync/active-pipelines?modules=0` and pollutes the store with a `0:<year>` key. Fix: early-return when `moduleTypeId` is falsy, mirroring the existing pattern in `useModuleConfig` helpers.

### Performance

- [ ] **`backend/app/api/v1/data_sync.py:884-891` (and `:954-961`)** — `get_pipeline_jobs` and the SSE stream endpoint both call `list_jobs_by_pipeline_id(pipeline_id)`, then immediately invoke `_check_pipeline_scope` which (`:173`) re-queries the same row set. Doubles the DB round-trips on every pipeline read and every SSE poll iteration. Fix: factor an `_check_pipeline_scope_from_jobs(jobs, current_user, db, action)` overload that takes the already-fetched list and bypasses the re-query; have `_check_pipeline_scope(pipeline_id, ...)` call the new helper after its lookup.

### Maintainability / refactoring

- [ ] **`docs/src/implementation-plans/310-d-architecture-followups.md`** (lines 27 + 98) — Follow-up sections still carry `Delivered in PR #<TBD>` / `Pending` placeholders even though #1062, #1063, and #1064 are all delivered in this PR. Replace TBD with the per-issue closing PR (#1075 / #1077 / #1074) and flip the status lines.
- [ ] **`backend/app/tasks/runner.py:180-183`** — `try: await abort_waiter / except asyncio.CancelledError: pass` is an idiomatic cancellation-drain but has no explanatory comment, so CodeQL flags it. One-line comment ("drain the cancellation we just issued") satisfies the rule without behavior change.

_Already fixed (dropped from triage)_: `test_handler_registrations.py:220` — `dedup_active is True` → `dedup_config is AGGREGATION_DEDUP` was applied in commit 7399d4b0 (the CI-unblock pass).
