# Bot Review TODOs: PR #1249

## Source Branch: `fix/pipeline-debug`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR hardens the ingestion → recalc → aggregation pipeline end-to-end by introducing a first-class `pipelines` aggregate (authoritative status + reconciliation), tightening FK correctness, adding concurrency controls to prevent deadlocks/races, and aligning the back-office UX/observability (pipeline ops console + accurate/consistent status messaging).

**Changes:**

- Adds `pipelines` table + `data_ingestion_jobs.pipeline_id` FK enforcement, plus runner-driven status writes and a periodic reconciliation loop.
- Introduces concurrency safety via Postgres advisory locks (aggregation per-year lock; factor↔recalc scoped lock; unit_sync global + per-year locks) and deferred child dispatch until after `data_session.commit()`.
- Improves operator UX/observability: pipeline ops console/store/i18n, PARTIAL vs FAILED tiering, “honest” status messages, and year provisioning gating via `configuration_completed`.

### Reviewed changes

Copilot reviewed 63 out of 63 changed files in this pull request and generated 3 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                 | Description                                                                                                                   |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| frontend/src/stores/yearConfig.ts                                                    | Adds `configuration_completed` field to year configuration types for provisioning UX.                                         |
| frontend/src/stores/pipelineStream.ts                                                | Extends pipeline progress shape with `status` (PARTIAL) and `kind` for UI scoping.                                            |
| frontend/src/stores/pipelineState.ts                                                 | Adds `setPipelineId()` to seed pipeline IDs from dispatch responses (reduce discovery gap).                                   |
| frontend/src/stores/pipelineOperationsConsole.ts                                     | New Pinia store for the pipeline operations console list + filters + counters.                                                |
| frontend/src/stores/backofficeDataManagement.ts                                      | Seeds `pipeline_id` from dispatch/recalc responses to subscribe to SSE immediately.                                           |
| frontend/src/router/routes.ts                                                        | Registers back-office pipeline operations route with permission guard.                                                        |
| frontend/src/pages/back-office/DataManagementPage.vue                                | Makes year provisioning “in-flight” state durable across refresh via `configuration_completed`.                               |
| frontend/src/i18n/pipeline_operations_console.ts                                     | New i18n strings for pipeline operations console (en/fr).                                                                     |
| frontend/src/i18n/backoffice_data_management.ts                                      | Adds tooltip text for “pipeline still running” indicator.                                                                     |
| frontend/src/constant/navigation.ts                                                  | Adds BACKOFFICE nav entry for Pipeline operations.                                                                            |
| frontend/src/components/molecules/data-management/UploadCard.vue                     | Scopes pipeline phase display by pipeline `kind`; consolidates spinners; shows amber “in progress” marker while chain runs.   |
| frontend/src/components/molecules/data-management/SubmoduleItem.vue                  | Injects and forwards module-scoped `pipelineProgress` to submodule upload cards.                                              |
| frontend/src/components/layout/Co2Sidebar.vue                                        | Ensures super-admin always sees menu items (bypasses limited-access disable).                                                 |
| docs/src/implementation-plans/1236-pipelines-table-aggregate-root.md                 | New/updated plan doc for #1236 phases (missing frontmatter).                                                                  |
| docs/src/implementation-plans/1234-pipeline-operations-console.md                    | New/updated plan doc for #1234 (missing frontmatter).                                                                         |
| docs/src/database/erd.md                                                             | Updates ERD for `pipelines`, year configuration completion stamp, and pipeline FK.                                            |
| backend/app/models/data_ingestion.py                                                 | Adds Pipeline model + PipelineStatus; declares FK+index on `data_ingestion_jobs.pipeline_id`.                                 |
| backend/alembic/versions/2026_05_19_2000-b1f7a2c9d4e0_add_pipelines_table.py         | Creates `pipelines` table and indexes.                                                                                        |
| backend/alembic/versions/2026_05_20_0900-a3b8c9d0e1f2_year_config_completed.py       | Adds `year_configuration.configuration_completed` column.                                                                     |
| backend/alembic/versions/2026_05_20_1000-c4d5e6f7a8b9_enforce_pipeline_id_fk.py      | Adds pipeline FK constraint and index on `data_ingestion_jobs.pipeline_id`.                                                   |
| backend/app/schemas/year_configuration.py                                            | Exposes `configuration_completed` in year configuration responses.                                                            |
| backend/app/models/year_configuration.py                                             | Adds `configuration_completed` column definition.                                                                             |
| backend/app/api/v1/year_configuration.py                                             | Ensures pipeline row exists before unit_sync job insert; returns `configuration_completed`.                                   |
| backend/app/tasks/unit_sync_tasks.py                                                 | Adds advisory locks; records phases; stamps `configuration_completed` on success.                                             |
| backend/app/repositories/unit_repo.py                                                | Adds Postgres ON CONFLICT bulk upsert path (race-safe) with SQLite fallback.                                                  |
| backend/app/tasks/\_locks.py                                                         | New helper for factor↔recalc advisory lock with deterministic key encoding.                                                   |
| backend/app/tasks/ingestion_tasks.py                                                 | Uses factor↔recalc lock; centralizes “honest” status message construction via `finalize_ingest_meta`.                         |
| backend/app/tasks/reference_ingest_tasks.py                                          | Reuses `finalize_ingest_meta` to avoid status-message drift/duplication.                                                      |
| backend/app/workflows/emission_recalculation.py                                      | Adds per-entry SAVEPOINT + fail-fast on session/connection-fatal errors.                                                      |
| backend/app/tasks/emission_recalculation_tasks.py                                    | Adds in-pipeline aggregation coalescing + affected-module scoping + factor/recalc lock.                                       |
| backend/app/tasks/aggregation_tasks.py                                               | Adds per-year advisory lock; scopes aggregation to affected modules when available.                                           |
| backend/app/services/pipeline_progress.py                                            | Read-flip support (pipeline status authoritative); root detection via lowest-id; exposes status/kind for UI.                  |
| backend/app/tasks/\_chain.py                                                         | Adds deferred child dispatch queue (ContextVar) + FK-safe pipeline mint ordering; removes `parent_job_id` meta threading.     |
| backend/app/tasks/runner.py                                                          | Defers chained dispatch until after `data_session.commit()`; recomputes pipeline status post-finish; adds new inline imports. |
| backend/app/tasks/\_pipeline_reconciler.py                                           | New cron-like reconciliation loop for pipeline status self-healing.                                                           |
| backend/app/main.py                                                                  | Starts/stops pipeline reconciler task in lifespan.                                                                            |
| backend/app/core/config.py                                                           | Adds settings toggles and interval for pipeline reconciler.                                                                   |
| backend/tests/unit/workflows/test_emission_recalculation.py                          | Adds regression tests for abort-on-fatal DB/session errors.                                                                   |
| backend/tests/unit/tasks/test_ingestion_handlers.py                                  | Pins “not Success when ERROR” + last_error enrichment + retired meta threading.                                               |
| backend/tests/unit/tasks/test_chain.py                                               | Pins deferred-dispatch semantics and retired `parent_job_id` meta.                                                            |
| backend/tests/unit/tasks/test_handler_registrations.py                               | Updates unit_sync tests for configuration stamp + phases; pins advisory lock behavior.                                        |
| backend/tests/unit/services/test_pipeline_progress.py                                | Adds tests for pipeline.status authoritativeness and kind propagation.                                                        |
| backend/tests/unit/services/test_pipeline_meta_allowlist.py                          | Pins meta allow-list and enum-name filter semantics; pins state/result serialization as enum names.                           |
| backend/tests/unit/tasks/test_pipeline_reconciler.py                                 | Tests reconciliation loop hygiene (sleep, exception survival, cancellation, log spam avoidance).                              |
| backend/tests/unit/tasks/test_factor_recalc_lock.py                                  | Tests factor↔recalc advisory lock helper behavior + key encoding uniqueness.                                                  |
| backend/tests/unit/tasks/test_emission_recalc_coalesce.py                            | Tests “single trailing aggregation” gate + affected-module scoping config builder.                                            |
| backend/tests/unit/tasks/test_aggregation_scope.py                                   | Tests unioning affected-module IDs across finished recalc siblings.                                                           |
| backend/tests/unit/tasks/test_aggregation_handler.py                                 | Tests aggregation per-year advisory lock and affected-module scoping behavior.                                                |
| backend/tests/unit/v1/test_active_pipelines_endpoint.py                              | Pins removal of over-eager per-module OPA pre-filter regression.                                                              |
| backend/tests/unit/repositories/test_unit_repo.py                                    | Pins Postgres ON CONFLICT path vs SQLite legacy path; empty input short-circuit.                                              |
| backend/tests/unit/repositories/test_pipeline_fk_ordering_regression.py              | Enforces correct `ensure_pipeline_exists` ordering under FK + autoflush scenarios.                                            |
| backend/tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py | Updates tests to account for new “empty factors” guards.                                                                      |
| backend/tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py      | Adds fail-fast tests for factor-inferred modules on empty factors.                                                            |
| backend/tests/unit/services/data_ingestion/test_guard_factors_required.py            | New tests for `_guard_factors_required` and factor-inferred module set.                                                       |
| backend/tests/integration/data_ingestion/test_csv_upload_e2e.py                      | Seeds `configuration_completed` to satisfy new dispatch precondition in integration test.                                     |
| backend/app/services/data_ingestion/base_csv_provider.py                             | Adds `_guard_factors_required` helper for fail-fast on missing factors.                                                       |
| backend/app/services/data_ingestion/csv_providers/module_per_year.py                 | Adds factor-inferred module fail-fast guard + `_guard_factors_required` usage.                                                |
| backend/app/services/data_ingestion/csv_providers/module_unit_specific.py            | Adds `_guard_factors_required` usage for unit-specific ingests.                                                               |

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 66 out of 66 changed files in this pull request and generated 6 comments.

---

### File: `backend/app/api/v1/data_sync.py` (Line null) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).
This for-loop may attempt to iterate over a [non-iterable instance](3) of class [type](2).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/667)

### File: `backend/app/tasks/_chain.py` (Line 103) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.tasks.runner](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/668)

### File: `backend/app/tasks/reference_ingest_tasks.py` (Line 15) — github-advanced-security[bot]

## CodeQL / Cyclic import

Import of module [app.tasks.ingestion_tasks](1) begins an import cycle.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/669)

### File: `docs/src/implementation-plans/1236-pipelines-table-aggregate-root.md` (Line 7) — Copilot

## This implementation plan is missing the required YAML frontmatter (--- ... --- with status/issue/last_updated/summary). Without it, docs/gen_indexes.py will categorize it as "Uncategorized" and it won't be grouped correctly in the generated implementation-plans index. Add the frontmatter block at the top of the file.

### File: `docs/src/implementation-plans/1234-pipeline-operations-console.md` (Line 6) — Copilot

## This implementation plan is missing the YAML frontmatter block (--- ... ---). docs/gen_indexes.py relies on frontmatter (status/issue/last_updated/summary) to generate the Implementation Plans index; without it this page will be grouped under "Uncategorized". Add frontmatter at the top of the file.

### File: `backend/app/tasks/runner.py` (Line 172) — Copilot

## New inline imports were introduced inside run_job() for \_chain helpers. These don’t appear to be required for avoiding a circular dependency (runner already imports from app.tasks.\_chain elsewhere), and they make dependencies harder to audit and can hide import-time errors until runtime. Prefer moving these imports to the module top (or at least the top of run_job alongside the existing bootstrap_handlers import) so they’re explicit and consistent.

### File: `frontend/src/components/molecules/data-management/UploadCard.vue` (Line 107) — Copilot

## `TARGET_TO_KINDS[TargetType.DATA_ENTRIES]` only allows `csv_ingest`/`api_ingest`, but backend also creates pipelines with kind `emission_recalc` and `module_emission_recalc` for the “Recalculate” actions (see `POST /sync/recalculate-emissions/...`). With the current mapping, those pipelines won’t show phase progress / the amber in-progress indicator on the data cards, which contradicts the intent of seeding `pipeline_id` from the recalc responses. Add the recalc kinds to the DATA_ENTRIES allowed list (or switch to a broader rule for DATA_ENTRIES pipelines).

### File: `docs/src/implementation-plans/1236-pipelines-table-aggregate-root.md` (Line 5) — Copilot

## This new implementation plan is missing the required YAML frontmatter (`---` block with at least `status`, `issue`, `last_updated`, `summary`). `docs/gen_indexes.py` groups implementation plans using that frontmatter; without it this page will fall under “Uncategorized” in the generated Implementation Plans index.

### File: `docs/src/implementation-plans/1234-pipeline-operations-console.md` (Line 4) — Copilot

## This new implementation plan is missing the required YAML frontmatter (`---` block with at least `status`, `issue`, `last_updated`, `summary`). `docs/gen_indexes.py` groups implementation plans using that frontmatter; without it this page will fall under “Uncategorized” in the generated Implementation Plans index.

### File: `backend/app/tasks/runner.py` (Line 173) — Copilot

## Inline imports were introduced for `_chain` helpers inside `run_job()`. This makes dependencies harder to audit and conflicts with the project’s “no inline imports” guideline; here it also isn’t necessary to break a cycle (runner already depends on `_chain` at runtime). Prefer moving these imports to module top (or refactor to remove the need for importing `_chain` from within the function).

### File: `backend/app/tasks/runner.py` (Line 298) — Copilot

## `discard_pending_dispatches` is imported inline in the error path. This adds another hidden dependency inside `run_job()` and conflicts with the project’s “no inline imports” guideline. Prefer importing `_chain` helpers once at module top (or refactor dispatch-queue helpers into a module that doesn’t require importing from inside control-flow branches).

### File: `backend/app/tasks/_chain.py` (Line 107) — Copilot

## `drain_pending_dispatches()` imports `run_job` from `app.tasks.runner` inside the function. This creates a runtime-level import edge back to the runner and is already flagged by CodeQL as a cyclic-import risk; it also violates the project’s “no inline imports” guideline. Consider breaking the `_chain ↔ runner` dependency by moving dispatch-queue utilities into a neutral module and injecting a dispatcher callback, so `_chain` never imports `runner`.

## Action Items

### Critical: logic, security, correctness

- [ ] **`frontend/src/components/molecules/data-management/UploadCard.vue:107`** — `TARGET_TO_KINDS[TargetType.DATA_ENTRIES]` is missing `emission_recalc` and `module_emission_recalc`. The two `/sync/recalculate-emissions*` endpoints (verified at `app/api/v1/data_sync.py:1610` and `:1710`) call `ensure_pipeline_exists(kind="emission_recalc"|"module_emission_recalc")`, so clicking the data card's "Recalculate" button creates a pipeline whose `kind` doesn't match the card's allowed list → `pipelineAppliesToCard` returns false → no phase indicator, no amber ⋯, even though the operator triggered the recalc _from_ the data card. Fix: change the mapping to `[TargetType.DATA_ENTRIES]: ['csv_ingest', 'api_ingest', 'emission_recalc', 'module_emission_recalc']`. Bot's diagnosis is exactly right; apply the suggested fix.

### Maintainability / refactoring

- [ ] **`backend/app/tasks/_dispatch.py`** _(new module)_ — extract the deferred-dispatch ContextVar + `reset_pending_dispatches` / `drain_pending_dispatches` / `discard_pending_dispatches` out of `_chain.py` into a neutral module that imports nothing from `runner` or `_chain`. Invert the runner dependency: `runner.py` calls `set_dispatcher(_dispatch_child)` at module load (where `_dispatch_child` wraps `fire_and_forget(run_job(...))`), and `_dispatch.drain()` calls the registered callback instead of importing `run_job`. After: `runner.py` imports `_dispatch` at module top (closes Copilot's three inline-import comments on lines 172, 173, 298 — bot's "runner already imports from \_chain elsewhere" diagnosis is wrong, runner currently has NO module-top \_chain import, but the suggestion is sound once `_dispatch` exists). `_chain.py` also imports `_dispatch` at top, no lazy `run_job` import (closes the CodeQL `_chain.py:103/107` cyclic-import note). One refactor closes 5 bot comments.

- [ ] **`backend/app/tasks/_ingest_meta.py`** _(new module — or move `finalize_ingest_meta` into `app/services/data_ingestion/`)_ — break the `reference_ingest_tasks ↔ ingestion_tasks` cycle CodeQL flagged at `reference_ingest_tasks.py:15`. The cycle path is `reference_ingest → ingestion_tasks → _chain → runner → bootstrap_handlers → reference_ingest` (all lazy past `_chain` so harmless at runtime, but CodeQL flags the static graph). Move `finalize_ingest_meta` to a leaf module that depends only on `app.models.data_ingestion`; both handler modules then import from there. Pairs naturally with the `_dispatch.py` extraction.

- [ ] **`docs/src/implementation-plans/1236-pipelines-table-aggregate-root.md`** and **`docs/src/implementation-plans/1234-pipeline-operations-console.md`** — both lack the YAML frontmatter block (Copilot flagged twice each, lines 5/7 and 4/6 — same root cause across re-scans). `docs/gen_indexes.py` reads `status` / `issue` / `last_updated` / `summary` from frontmatter to group entries; without it both end up in "Uncategorized" in the rendered MkDocs index. Match the shape used by `1219-stuck-jobs-and-pipeline-progress.md` and `220-csv-upload-implementation-summary.md`: add the `---\nstatus: delivered\nissue: <id>\nlast_updated: 2026-05-20\nsummary: …\n---` block at the top of each. One-line edit per file.

### Dropped after verification

- **CodeQL "Non-iterable used in for loop" on `data_sync.py`** — already-fixed in commit `18f051d4`. The loop now reads `enum_cls.__members__.values()` (verified at `app/api/v1/data_sync.py:460`). CodeQL hasn't re-scanned or the alert hasn't cleared in the dashboard, but the code is correct.
