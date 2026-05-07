---
status: in-progress
issue: 310
last_updated: 2026-05-07
title: "310 — Post-merge fix batch (review findings + #1062/#1063/#1064)"
summary: "Parallel worker batch landing the 8 High/Critical findings from docs/code-review/310-overall-review.md plus completing the three architecture follow-ups, all targeting feat/310/dev integration branch."
---

# 310 — Post-Merge Fix Batch

## Context

After Plans 310-A/B/C/D merged to `dev`, a thorough end-to-end review
(`docs/code-review/310-overall-review.md`) surfaced 8 High/Critical
correctness/safety findings in shipped code. Independently, three
architecture follow-ups were staged via PR #1058 (issues #1062, #1063,
#1064) to address structural concerns the individual PRs each patched
around. The review's reconciliation section confirmed:

- #1064's trigger condition is **met** (B-M1 names a concrete second
  dedupable handler — `_chain_recalc_for_stale`).
- #1063 would _detect_ but not _fix_ B-C2 and B-H1 — valuable as a
  passive backstop.
- #1062 stays orthogonal; F-C1 (a11y) is its own bug, fixed standalone.

This batch lands all of it in parallel on a dedicated integration
branch `feat/310/dev`, NOT on `dev`. The user wants a stable platform
to test the bundle before promoting to `dev`. Each PR targets
`feat/310/dev`. After PR creation, the coordinator manually triggers
Copilot review and runs `/review-copilot-comments` per PR.

## Design decisions

### B-C1 — Atomic CAS on FINISHED job-write

New `finish_job(job_id, pod_id, result, status_message, metadata) → bool`
on `DataIngestionRepository` issues an atomic
`UPDATE … WHERE id=:id AND locked_by=:pod_id AND state=RUNNING RETURNING id`.
Returns `True` on rowcount==1, `False` on rowcount==0 (preempted). Runner
uses it for terminal transitions; existing `update_ingestion_job` keeps
non-terminal status updates simple. Avoids cascading a `pod_id` arg into
every existing call site.

### B-H1 — Persist Travel `kg_co2eq` override into `DataEntry.data`

Reserved key `__kg_co2eq_override__` (double-underscore prefix marks it as
internal, won't surface as a kind/subkind value).
`DataEntryEmissionService.prepare_create` reads it, applies via the
existing `kg_co2eq_override` short-circuit. No new column, no migration,
idempotent through async recovery.

### F-C1 — `<q-tooltip>` with manual focus/blur via exposed `show()` / `hide()`

Keep the tooltip (preserves hover behavior on desktop). Re-expose Quasar's
`show()` / `hide()` (verified at `QTooltip.js:268`) via `defineExpose` on
`PipelineDiagnosticTooltip.vue`. Parent badge calls them on `@focus` /
`@blur`. Apply to both badges in `ModuleConfig.vue`.

### #1063 — Operator-triggered, no auto-retry

Read-only health endpoint. Auto-retry has retry-storm modes that aren't
worth the complexity now.

### #1064 — `DedupConfig` dataclass

`(job_type, scope_columns, constraint_name)`. Add `EMISSION_RECALC_DEDUP`
covering `(module_type_id, data_entry_type_id, year)` and a new partial
unique index `uq_emission_recalc_active`. Wire `_chain_recalc_for_stale`
to use it (resolves B-M1).

### #1062 — Unified `pipelineStateStore`, lifecycle stays in the composable

Store holds state, `usePipelineStream` composable wires the SSE
connection. Drop `current_pipeline_id` from
`useTimelineStore.currentPipelineIds` and
`yearConfigStore.recalculationStatus[].current_pipeline_id`. New backend
endpoint `GET /v1/sync/active-pipelines?year=Y&modules=…` thin-wraps the
existing `get_current_pipeline_ids_for_modules` repo helper.

## Coordinator pre-flight

```bash
rtk git fetch origin
rtk git checkout dev && rtk git pull --ff-only origin dev
rtk git checkout -b feat/310/dev
rtk git push -u origin feat/310/dev
```

Then spawn the 11 parallel workers in isolated worktrees. Each worker
bases its branch on `feat/310/dev`. Each PR targets `feat/310/dev`.

## Work units (11 parallel)

### Unit 1 — fix(310): atomic CAS on FINISHED job-write [B-C1]

**Branch**: `fix/310-finished-cas`
**Files**:

- `backend/app/repositories/data_ingestion.py` — add `finish_job(job_id, pod_id, result, status_message=None, metadata=None) → bool` with atomic UPDATE.
- `backend/app/tasks/runner.py` — replace FINISHED-write paths (success at ~`:181-188`, exception at `:152-159`) to call `finish_job(job.id, _POD_ID, ...)`. On `False`: log warning and exit cleanly.
- `backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py` — new test simulating the recovery race.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py -v`

### Unit 2 — fix(310): emission_recalc chains aggregation on WARNING [B-C2]

**Branch**: `fix/310-recalc-aggregation-on-warning`
**Files**:

- `backend/app/tasks/emission_recalculation_tasks.py:110` — change `result == IngestionResult.SUCCESS` to `result != IngestionResult.ERROR`.
- `backend/tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py` — add `test_aggregation_chains_on_warning_with_partial_failure`.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_full_dag_pipeline_pg.py -v`

### Unit 3 — fix(310): a11y — pipeline diagnostic accessible on focus [F-C1]

**Branch**: `fix/310-a11y-tooltip-focus`
**Files**:

- `frontend/src/components/molecules/data-management/PipelineDiagnosticTooltip.vue` — `defineExpose({ show, hide })` re-exposing the inner `<q-tooltip>`'s methods via a template ref `tooltipRef`.
- `frontend/src/components/organisms/data-management/ModuleConfig.vue:232-261` — `ref="recalcTooltip"` / `ref="failureTooltip"`, `@focus` / `@blur` handlers on each `<q-badge>` calling the exposed methods.
- Update `docs/src/implementation-plans/310-d-frontend-stale-stats.md` to reflect the actual mechanism.

**E2E**: `make lint && make type-check-go`. Manual: tab to badge, confirm tooltip opens.

### Unit 4 — fix(310): preserve kg_co2eq override on async path [B-H1]

**Branch**: `fix/310-kg-co2eq-async-path`
**Files**:

- `backend/app/services/data_entry_emission_service.py:122-200` — `prepare_create` / `upsert_by_data_entry` read `__kg_co2eq_override__` from `data_entry_response.data`.
- `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py:419-432` — store override under reserved key instead of popping.
- `backend/app/services/data_ingestion/base_csv_provider.py:818-829` — mirror change for CSV-side overrides.
- `backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py` (new).

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py -v`

### Unit 5 — fix(310): seed provider bypasses BULK_PATH_PURE_ASYNC gate [B-H2]

**Branch**: `fix/310-seed-bypass-async-gate`
**Files**:

- `backend/app/services/data_ingestion/csv_providers/local_seed.py` — `is_seed_run=True` attribute on the provider.
- `backend/app/services/data_ingestion/base_csv_provider.py:1185, 1233` — gate honors the flag: `if get_settings().BULK_PATH_PURE_ASYNC and not getattr(self, "is_seed_run", False):`.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/`

### Unit 6 — fix(310): heartbeat failure aborts handler before preemption window [B-H3]

**Branch**: `fix/310-heartbeat-abort-on-failure`
**Files**:

- `backend/app/tasks/runner.py:231-234` — track consecutive heartbeat failures; after threshold, set `asyncio.Event` that cancels the handler task.
- `backend/tests/unit/tasks/test_runner.py` — unit test simulating failure burst.

**E2E**: `rtk uv run pytest backend/tests/unit/tasks/`

### Unit 7 — fix(310): SSE session lifetime + disconnect detection + tenant scope [A-H1 + A-H2 + A-H3]

**Branch**: `fix/310-sse-pool-and-scope`
**Files**:

- `backend/app/api/v1/data_sync.py:560-632` (job stream), `:732-856` (pipeline stream) — drop `Depends(get_db)`; `async with SessionLocal()` per poll inside loop. `request: Request` + `await request.is_disconnected()` check.
- Same file `:684-690`, `:732-738`, `:1057-1102` (recovery), `:520-556` (cancel) — `_check_pipeline_scope` helper deriving `(module_type_id, institutional_id)` from job; `# TODO(#459)` comments.
- `backend/tests/integration/services/data_ingestion/test_sync_pipeline_stream_endpoint_pg.py` — disconnect simulation + cross-tenant 403.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_sync_pipeline_*`

### Unit 8 — fix(310): is_current index discriminates job_type + claim IntegrityError logging [M-H2 + A-M1]

**Branch**: `fix/310-is-current-index-job-type`
**Files**:

- Walk `(job_type, target_type, ingestion_method)` cartesian. Either document discriminating-tuple rationale OR add `job_type` to partial unique index via new alembic migration with `transaction_per_migration=False` + `CREATE INDEX CONCURRENTLY`.
- `backend/app/repositories/data_ingestion.py:456-459` — `logger.warning` on `IntegrityError` branch, `logger.debug` on `_ClaimUnavailable`.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_pod_safety_310a_pg.py`

### Unit 9 — feat(310): chain_job DedupConfig + emission_recalc dedup [#1064 + B-M1]

**Branch**: `feat/310-dedup-config`
**Files**:

- `backend/app/tasks/_chain.py` — `@dataclass(frozen=True) class DedupConfig`; `AGGREGATION_DEDUP`, `EMISSION_RECALC_DEDUP`. Refactor `_insert_child_with_dedup` to build SQL from `scope_columns` / `constraint_name`. `chain_job(..., dedup_config: DedupConfig | None = None)`. Keep `dedup_active=True` shim.
- New alembic migration: `CREATE UNIQUE INDEX CONCURRENTLY uq_emission_recalc_active ON data_ingestion_jobs (module_type_id, data_entry_type_id, year) WHERE job_type='emission_recalc' AND state IN ('NOT_STARTED','QUEUED','RUNNING')` with `transaction_per_migration=False`.
- `backend/app/tasks/ingestion_tasks.py:302-310` — pass `dedup_config=EMISSION_RECALC_DEDUP`.
- `backend/app/tasks/emission_recalculation_tasks.py:111-118, 244-251` — migrate to `dedup_config`.
- `backend/tests/integration/services/data_ingestion/test_emission_recalc_dedup_pg.py` (new).

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/`

### Unit 10 — feat(310): pipeline-failure observability backstop endpoint [#1063]

**Branch**: `feat/310-stale-stats-health`
**Files**:

- `backend/app/api/v1/data_sync.py` — `GET /v1/sync/health/stale-stats?older_than_minutes=60`, gated on `backoffice.data_management.view`. Read-only, no auto-retry.
- `backend/app/repositories/data_ingestion.py` — `find_stale_aggregations(threshold_minutes) → list[…]`.
- `backend/app/schemas/sync.py` (or `data_sync.py`) — `StaleStatsEntry` schema with `why_stale ∈ {no_aggregation_ever, last_aggregation_failed, last_aggregation_too_old, pending_aggregation_stuck}`.
- `backend/tests/integration/services/data_ingestion/test_stale_stats_endpoint_pg.py` (new).
- Mark `docs/src/implementation-plans/310-d-architecture-followups.md` Follow-up 1 as Delivered.

**E2E**: `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_stale_stats_endpoint_pg.py`

### Unit 11 — feat(310): unified frontend pipelineStateStore + bulk active-pipelines endpoint [#1062]

**Branch**: `feat/310-unified-pipeline-state-store`
**Files** (backend):

- `backend/app/api/v1/data_sync.py` — `GET /v1/sync/active-pipelines?year=Y&modules=1,2,3` thin-wrapping `get_current_pipeline_ids_for_modules`. Permission `backoffice.data_management.view`.
- `backend/app/schemas/year_configuration.py:475-486` — drop `current_pipeline_id`.
- `backend/app/schemas/carbon_report.py:66-78` — drop `current_pipeline_id`.
- `backend/app/api/v1/year_configuration.py:173-229` — drop `_build_recalculation_status` enrichment.
- `backend/app/api/v1/carbon_report_module.py` — drop bulk-fetch enrichment for `current_pipeline_id`.
- `backend/tests/integration/services/data_ingestion/test_active_pipelines_endpoint_pg.py` (new).

**Files** (frontend):

- `frontend/src/stores/pipelineState.ts` (new).
- `frontend/src/components/organisms/data-management/ModuleConfig.vue:42-48` — read from new store.
- `frontend/src/stores/yearConfig.ts:108` — drop field.
- `frontend/src/stores/modules.ts:124` — drop field.
- Mark `docs/src/implementation-plans/310-d-architecture-followups.md` Follow-up 3 as Delivered.

**E2E**: backend `rtk uv run pytest backend/tests/integration/services/data_ingestion/test_active_pipelines_endpoint_pg.py`; frontend `make lint && make type-check-go`.

## Out of scope

- **M-H1 (Plan B migration safety)** — investigative; coordinator handles via runbook check.
- **A-M2/A-M3/A-M4/F-M1/F-M2/F-M3/B-M2** — Mediums; folded into a single follow-up cleanup PR after this batch.
- **A-M1** — folded into Unit 8.

## Worker conventions (every unit)

- `rtk` prefix on every git/test command.
- `rtk uv run pytest`, never bare `pytest`.
- Branch off `feat/310/dev`. PR `--base feat/310/dev`.
- NO `Co-Authored-By: Claude` trailer.
- NO emojis.
- After implementing: invoke `Skill` tool with `skill: "simplify"` for self-review.
- Use `pg_dsn_with_310b` fixture in IT files needing 310-B's partial unique indexes.
- Final report line exactly: `PR: <url>`.

## Post-batch coordinator workflow

For each PR (sequential — Copilot may rate-limit):

1. Trigger Copilot review via `gh` (verify exact mechanism via existing 310 PR's reviewer list).
2. Poll `gh pr view <num> --json reviews` until Copilot review appears.
3. Run `/review-copilot-comments` on the PR — produces `docs/code-review/310-copilot-feedback-<slug>.md`.
4. Surface triage to user, who decides what to land.

## Verification (post-merge of batch)

After all 11 PRs merge to `feat/310/dev`:

1. `rtk git checkout feat/310/dev && rtk git pull && cd backend && rtk uv run pytest` → all green.
2. `cd frontend && make lint && make type-check-go` → clean.
3. `alembic upgrade head` against populated PG → no failure.
4. Browser smoke: focus badge → tooltip opens (F-C1). Trigger CSV upload → "Recalculating…" badge cycles correctly (#1062 store wiring).
5. User opens PR `feat/310/dev → dev` once satisfied; that PR is reviewed standalone.
