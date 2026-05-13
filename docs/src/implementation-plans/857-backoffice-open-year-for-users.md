---
status: delivered
issue: 857
last_updated: 2026-05-12
title: "Issue 857 — Back-office: Open year for users (functional, end-to-end)"
summary: "Consolidate the back-office data-management page year-lifecycle: single-click create+sync, real pipeline observability, hide unstarted years from end-users, and wire the 'Open year for users' button."
prs:
  - "#1111 — U1: collapse year-create + unit-sync into one observable pipeline"
  - "#1107 — U2: hide unstarted years from workspace selector for non-admins"
  - "#1109 — U3: silence 404 toast on missing year-configuration / explore report"
  - "#1110 — U4: year-level active-pipelines endpoint + page-mount rehydrate"
  - "#1108 — U5: wire 'Open year for users' button + reflect is_started in UI"
---

# Issue 857 — Back-office: Open year for users (functional)

> **Naming note.** Issue [#857](https://github.com/EPFL-ENAC/co2-calculator/issues/857) is the GitHub-tracked feature ("[FEAT](BackOffice Configuration): Open year for user functional (backend)"). During development the epic was internally referred to as "#867" and the five delivery PRs adopted that identifier (`feat(867): … U1/5 … U5/5`). GitHub issue #867 is unrelated (a closed travel-module PR by @BenBotros). All references to "867" in the merged PR titles/bodies should be read as the U1–U5 grouping for this epic; the authoritative tracking issue is **#857**.

## Context

The back-office **Data Management** page (`frontend/src/pages/DataManagementPage.vue`) is the operator surface for preparing a reporting year: creating the `year_configuration` row, syncing units from Accred, uploading module CSVs, and finally **opening the year for end-users** so it appears in their workspace year selector.

Before this epic, the page had two structural problems:

1. **Two clicks pretending to be one.** "Create year" and "Sync units from accred" were separate buttons. The unit-sync button faked success with a 5-second `setTimeout` — no observability, no error surface.
2. **No closed loop between back-office state and user-facing visibility.** The `is_started` flag existed on `year_configuration` but the workspace selector did not filter by it, and the "Open year for users" button rendered without a click handler.

Side effects: a spurious "404 Not Found" toast on first landing (the page legitimately probes for a not-yet-created year), and no rehydrate path for year-level pipelines on hard-reload (only per-module pipelines rehydrated).

This epic ships the full back-office → end-user functional loop in five independent units, each behind its own PR.

---

## Delivered units

### U1 — `POST /year-configuration/{year}` enqueues one observable pipeline · PR [#1111](https://github.com/EPFL-ENAC/co2-calculator/pull/1111)

**Backend** (`backend/app/api/v1/year_configuration.py`, `backend/app/schemas/year_configuration.py`, repo + service)

- `POST /year-configuration/{year}` now:
  - keeps `is_started=False` on create (default; override-able via payload) — the year stays invisible to end-users until backoffice has uploaded every CSV and validated every mandatory module setting, then flips it via the U5 "Open year for users" button. **Correction (2026-05-12):** as shipped in #1111 the endpoint forced `is_started=True` on create, which short-circuited U5 and pushed half-configured years to users. Reverted in-place: the override now resolves to `False` when payload omits the field.
  - mints a fresh `pipeline_id` UUID
  - enqueues a tracked `DataIngestionJob` (`job_type=unit_sync`, `meta.config.target_year=<year>`)
  - dispatches via `fire_and_forget(run_job(job_id))` — same path the registered `unit_sync_handler` expects
- `YearConfigurationResponse` grows a `pipeline_id: UUID | None` field — populated on POST, `None` on GET.

**Frontend** (`DataManagementPage.vue`, `stores/yearConfig.ts`, `api/backofficeDataManagement.ts`)

- Drops the standalone "Sync units from accred" button and the fake-success `handleUnitSync` with its `setTimeout`.
- After `handleCreateYear` succeeds, the page subscribes to the returned `pipeline_id` via `usePipelineStream` and surfaces real progress / success / error notifications driven by the SSE stream.
- Module config + CSV uploads are gated (`inert` + inner-loading) while the pipeline is in flight.
- Drops the unused `syncUnitsFromAccred` helper and legacy `data_management_unit_sync_*` i18n keys.

---

### U2 — Lightweight year-configuration list endpoint, scoped by role · PR [#1107](https://github.com/EPFL-ENAC/co2-calculator/pull/1107)

**Backend** (`backend/app/api/v1/year_configuration.py`, `backend/app/schemas/year_configuration.py`)

- New `GET /api/v1/year-configuration/` returning `list[YearConfigurationListItem]`:
  ```
  { year: int, is_started: bool, updated_at: datetime }
  ```
  Sorted by `year DESC`. (`is_reports_synced` was originally part of this shape; dropped in the 2026-05-12 cleanup — see follow-ups.)
- **Auth filter**: non-backoffice callers (no `backoffice.data_management:view`) only see `is_started=true` rows. Backoffice data managers see every row.
- `YearConfigurationListItem` deliberately skips the heavy `config` JSON / job enrichment that `GET /{year}` carries — designed for the workspace year selector.
- Existing endpoints untouched: `GET /backoffice/years` (different concern, different data source) and `GET /year-configuration/{year}` (unchanged).

Frontend wiring of the workspace selector against this endpoint is out of scope for U2 — covered separately by frontend follow-ups when the selector switches off its client-side year computation.

---

### U3 — Silence 404 toast on legitimate empty-state probes · PR [#1109](https://github.com/EPFL-ENAC/co2-calculator/pull/1109)

**Frontend** (`stores/yearConfig.ts`, `stores/workspace.ts`)

- The global axios `afterResponse` handler (added in 4f0940b6) fires a default error toast for any non-2xx unless the caller passes `skipErrorCodes`.
- The data-management page already handles "no year yet" by setting `notFound = true` and rendering a "Create year" card — the 404 is meaningful, not an error.
- Applied the existing `skipErrorCodes` pattern (see `frontend/src/api/factors.ts:34`) to two stores where the catch treats 404 as "no resource yet":
  - `stores/yearConfig.ts::fetchConfig` (the reported bug)
  - `stores/workspace.ts::selectSimulatorExploreCarbonReport` (same shape — catch on 404 to seed a fresh explore report)
- Non-404 errors still surface through the global handler; `throw err;` on the non-404 branch is preserved.

---

### U4 — Year-level active-pipelines endpoint + reload rehydrate · PR [#1110](https://github.com/EPFL-ENAC/co2-calculator/pull/1110)

**Backend** — new endpoint:

- `GET /v1/sync/active-pipelines/year/{year}` → `list[str]` of `pipeline_id` UUIDs for every active `entity_type=GLOBAL_PER_YEAR` job (`NOT_STARTED` / `QUEUED` / `RUNNING`) for the year.
- Single SELECT, Python-side dedupe, `pipeline_id IS NOT NULL` guard so the result stays empty until U1 stamps `pipeline_id` on unit_sync.
- Sibling repo helper `get_active_year_level_pipeline_ids` mirrors `get_current_pipeline_ids_for_modules`'s shape.

**Frontend** (`pipelineStateStore`, `DataManagementPage.vue`)

- `pipelineStateStore.loadYearLevelFor(year)` / `getYearLevelPipelineIds(year)` mirror the per-module shape.
- `DataManagementPage.vue` watcher (`{ immediate: true }`) diff-subscribes / -unsubscribes on mount + year change; the composable's `onUnmounted` handles page-leave.
- Complements `ModuleConfig.vue`'s existing per-module rehydrate path (which is scoped by `module_type_id` and cannot see GLOBAL_PER_YEAR chains).

**Concurrency note (carried from the PR).** On rapid year switches (`2024 → 2025 → 2024`), `lastYearLevelSubscriptions = next` runs before `Promise.all(subscribePromises)`. Worst case is a redundant snapshot fetch, not a leak — the composable's `ownedSubscriptions` guards `subscribe` against double-counting. Flagged for awareness.

---

### U5 — Wire 'Open year for users' button + visibility chip · PR [#1108](https://github.com/EPFL-ENAC/co2-calculator/pull/1108)

**Frontend** (`stores/yearConfig.ts`, `DataManagementPage.vue`, i18n en/fr)

- `stores/yearConfig.ts`: new `openForUsers(year)` action — thin wrapper over `updateConfig` that PATCHes `{ is_started: true }`.
- `DataManagementPage.vue`:
  - Button now has `@click="handleOpenForUsers"` showing a positive toast on success / negative toast on error (mirrors `handleCreateYear`).
  - Button is `:disable`d when `anyModuleIncomplete` (existing) **or** the year is already open (new). Tooltip text differs per reason.
  - New `q-chip` near the year selector at-a-glance shows whether the year is open: green `lock_open` + "Open to users" / neutral `lock` + "Not yet open".
- i18n keys (en/fr): `data_management_year_already_open`, `data_management_year_opened_success`, `data_management_year_is_open`, `data_management_year_is_not_open`.

**Independence from U1.** If U1 ships first, new years are already `is_started=true` and this button is auto-disabled with the "already open" tooltip — desired. If U1 ships later, this still works for legacy years that have `is_started=false` (e.g. 2025).

---

## End-to-end flow after this epic

1. Operator hits **Create year** → single click → `POST /year-configuration/{year}` returns a `pipeline_id` → SSE stream drives real progress → modules section overlay clears on `FINISHED`.
2. New year defaults to `is_started=true`; users see it in the workspace selector immediately (U2 filter passes them through). Backoffice operators always see all years.
3. For legacy years (`is_started=false`), the **Open year for users** button is enabled once all modules are complete; clicking it PATCHes `is_started=true` and flips the chip live.
4. Hard-reload during a unit-sync rehydrates the year-level pipeline (U4) — badge / progress reattach.
5. Empty-state probes (landing on an uncreated year, simulator explore on a fresh year) no longer surface a "404 Not Found" toast (U3).

---

## Verification (executed across the 5 PRs)

| Surface                         | Tooling                                                                                                                                                                         | Result                                                                                                                                                |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend year-configuration POST | `uv run pytest tests/unit/v1/test_year_configuration.py tests/unit/schemas/test_year_configuration.py tests/integration/services/data_ingestion/test_sync_units_endpoint_pg.py` | 62 passed (U1)                                                                                                                                        |
| Backend year-list endpoint      | `uv run pytest backend/tests/integration/v1/test_year_configuration_list.py`                                                                                                    | passing — admin/non-admin filter + response shape (U2)                                                                                                |
| Backend active-pipelines/year   | `uv run pytest backend/tests/integration/services/data_ingestion/test_active_pipelines_year_endpoint_pg.py`                                                                     | 8/8 passed (U4)                                                                                                                                       |
| Full backend unit suite         | `uv run pytest tests/unit`                                                                                                                                                      | 1307 passed (U1, U4)                                                                                                                                  |
| Full backend suite (U2)         | `uv run pytest`                                                                                                                                                                 | 1515 passed                                                                                                                                           |
| Frontend type-check             | `vue-tsc --noEmit`                                                                                                                                                              | clean across all units                                                                                                                                |
| Frontend lint/format            | `eslint .` + `prettier --check`                                                                                                                                                 | clean (U5)                                                                                                                                            |
| Frontend build                  | `npm run build`                                                                                                                                                                 | passes (U1)                                                                                                                                           |
| Playwright                      | `npm run test:e2e -- data-management`                                                                                                                                           | 15 passed, 2 pre-existing `test.fixme` (U1); test 8 (year-level reload-rehydrate) added (U4); spec covers button-enabled + button-disabled cases (U5) |

**Manual smokes still recommended on a live env** (carried from PR bodies):

- U1 — create a fresh year, verify single-click creation, the inner-loading overlay, and the success toast on SSE `FINISHED`.
- U3 — land on a year with no `year_configuration` row, verify the "Create year" card renders without a "404 Not Found" toast.
- U4 — trigger a unit-sync, hard-reload while RUNNING, verify the badge / progress reattaches.
- U5 — click "Open year for users" on a legacy `is_started=false` year, verify the chip flips and the button disables.

---

## Files touched (per-PR breakdown lives on each PR)

Backend:

- `backend/app/api/v1/year_configuration.py` (U1, U2)
- `backend/app/schemas/year_configuration.py` (U1, U2)
- `backend/app/api/v1/sync.py` (U4 — new year-level endpoint)
- `backend/app/repositories/data_ingestion/*` (U4 — `get_active_year_level_pipeline_ids`)
- Service / repo glue for U1 unit-sync job dispatch

Frontend:

- `frontend/src/pages/DataManagementPage.vue` (U1, U4, U5)
- `frontend/src/stores/yearConfig.ts` (U1, U3, U5)
- `frontend/src/stores/workspace.ts` (U3)
- `frontend/src/stores/pipelineStateStore.ts` (U4)
- `frontend/src/composables/usePipelineStream.ts` (U4 — referenced)
- `frontend/src/api/backofficeDataManagement.ts` (U1 — `syncUnitsFromAccred` removal)
- `frontend/src/i18n/{en,fr}.json` (U1, U5)

Tests:

- `backend/tests/integration/v1/test_year_configuration_list.py` (U2 — new)
- `backend/tests/integration/services/data_ingestion/test_active_pipelines_year_endpoint_pg.py` (U4 — new)
- `frontend/tests/integration/data-management.spec.ts` (U1, U4, U5 — augmented)

---

## Follow-ups / known limitations

- **Cleanup: drop `year_configuration.is_reports_synced` (2026-05-12).** The bool flag was declared in the model + schema + frontend types but never written by the `unit_sync_handler` (which is the code that actually initializes `carbon_reports` for the year) and never read for any UI/business decision. The authoritative "reports initialized for year N" signal lives in `data_ingestion_jobs` (the `unit_sync` job with `state=FINISHED && result=SUCCESS && meta.config.target_year=N`). Removed from `models/year_configuration.py`, `schemas/year_configuration.py` (`YearConfigurationBase`, `YearConfigurationUpdate`, `YearConfigurationResponse`, `YearConfigurationListItem`), `api/v1/year_configuration.py` (response constructors, POST defaults, PATCH apply path, audit snapshot dicts in POST/PATCH/upload), the integration test `tests/integration/v1/test_year_configuration_list.py`, `frontend/src/stores/yearConfig.ts` (3 type declarations), and 3 frontend mock fixtures. Migration `2026_05_12_1300-a7b2f8c1d3e6` drops the column; downgrade re-adds it with `server_default='false'` for backfill.
- **Post-merge fix: 'Open year for users' button visibility (U5 follow-up, 2026-05-12).** As shipped in #1108 the button rendered unconditionally — outside the `v-if="yearConfigStore.config"` block — so it was visible (a) on the empty-state before any year_configuration row existed, and (b) during the in-flight unit_sync pipeline. Per the spec it must only exist once the year-configuration pipeline is fully completed. Fixed in-place in `DataManagementPage.vue` by adding `v-if="yearConfigStore.config && !yearSyncInFlight"` to the `<q-btn>` (the existing `anyModuleIncomplete` / `is_started` checks stay as `:disable` reasons once the button is visible). Regression coverage added in `frontend/tests/integration/data-management.spec.ts` under `Data management — open year for users`: two new cases assert `[data-testid="open-year-for-users-btn"]` has `toHaveCount(0)` on the empty-state (404 GET) and while the modules wrapper carries the `inert` attribute (pipeline mid-flight, pre-FINISHED).
- **Workspace year selector wiring (U2 consumer).** U2 ships the endpoint and back-end role filter, but the workspace year selector still computes the visible-years list client-side from `CarbonReport.year`. Switching it over to `GET /api/v1/year-configuration/` is the natural follow-up.
- **Vitest gap.** This repo has no vitest config; the U5 PR called for vitest store-action tests but the project is Playwright-only. Coverage lives in `frontend/tests/integration/data-management.spec.ts`.
- **Concurrent year-switch races (U4).** Documented above — currently bounded to redundant snapshot fetches. Revisit if real-world reports show duplicate subscriptions.
- **Issue #857 itself remains OPEN on GitHub.** Closing it requires either editing one of the merged PRs to add a `Closes #857` trailer, or closing manually. Worth doing as part of grooming.
