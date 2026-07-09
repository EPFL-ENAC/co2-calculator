---
status: delivered
issue: 740
last_updated: 2026-07-09
title: "Backoffice: Copy factors from previous year"
summary: "Add a backoffice action to duplicate a prior year's factor rows into a newly opened year, bulk or per-submodule, instead of forcing a full CSV re-upload."
---

# Backoffice: Copy factors from previous year

## Problem

Factors (`factors` table) are year-scoped (`Factor.year`, indexed, unique per
`(data_entry_type_id, year, emission_type_id, classification)`). The only way
to populate factors for a newly-opened year today is a CSV/API/computed sync
per `(module_type_id, data_entry_type_id)` via
`POST /v1/sync/factors/{module_type_id}/{data_entry_type_id}`
(`backend/app/api/v1/data_sync.py:998`), routed through
`ProviderFactory.PROVIDERS`/`COMPUTED_FACTOR_PROVIDERS`
(`backend/app/services/data_ingestion/provider_factory.py`) keyed on
`(IngestionMethod, TargetType)` or
`(module, data_entry_type, IngestionMethod, TargetType, EntityType)`.

Most factor tables (emission factor CSVs, unit costs, classifications) do not
change year over year — only a handful of rows get revised. Operators
currently must re-upload the full CSV for every module/data-entry-type
combination for every new year, even when 95%+ of rows are identical to the
prior year. `year_configuration` creation
(`create_year_configuration`, `backend/app/api/v1/year_configuration.py:608`)
already auto-enqueues a `unit_sync` job but does nothing for factors — every
submodule starts "incomplete" (`_enrich_config_with_incomplete_flags`) until
manually synced.

`getPreviousYearSuccessfulJobs` (`frontend/src/stores/backofficeDataManagement.ts:572`)
already reads the prior year's finished jobs for prerequisite checks, so the
frontend already has the previous-year job list in scope where a "copy"
action would be offered — no new lookup needed there.

No copy/duplicate/clone mechanism exists today (`grep` for
`copy|duplicate|clone` across `factor_service.py`, `factor_repo.py`,
`factors.py`, `backoffice.py` — the only "copy" hit is
`FactorRepository._upsert_via_copy`, a Postgres `COPY`-based upsert
implementation detail, unrelated).

## Design

Reuse the existing ingestion-job pipeline rather than inventing a parallel
synchronous copy path — this keeps SSE progress, `latest_factor_job`
enrichment, and the pipeline-observability UI (issue #857) working unchanged
for the new action.

**Backend**

1. Add `IngestionMethod.copy_previous_year` (int enum,
   `backend/app/models/data_ingestion.py`) alongside `api/csv/manual/computed`.
2. New provider `FactorCopyProvider`
   (`backend/app/services/data_ingestion/factor_copy_provider.py`, mirrors
   `factor_update_provider.py`'s shape): given `module_type_id`,
   `data_entry_type_id`, target `year`, reads `source_year` from
   `syncRequest.filters` (default `year - 1`), selects all `Factor` rows for
   `(data_entry_type_id, source_year)` scoped to the module's emission
   type(s) via `FactorService.list_by_data_entry_type`, clones each row with
   `year=target_year` and `id=None`, and writes them via the existing
   `FactorRepository.upsert_factors` (identity key already excludes `id`, so
   re-running is idempotent and safe to retry).
3. Register `(IngestionMethod.copy_previous_year, TargetType.FACTORS)` in
   `ProviderFactory.PROVIDERS` — no new endpoint needed, the existing
   `POST /v1/sync/factors/{module_type_id}/{data_entry_type_id}` already
   accepts `ingestion_method` + `filters` in `SyncRequest` and dispatches
   through `ProviderFactory.create_provider`.
4. Bulk "copy all" for a year: a thin loop endpoint
   `POST /v1/sync/factors/copy-previous-year/{year}` (or a frontend-side
   loop over configured `(module_type_id, data_entry_type_id)` pairs calling
   the per-module endpoint — prefer the frontend loop, it reuses
   `initiateSync`'s existing per-submodule pipeline tracking instead of
   inventing a second bulk-job abstraction). Skip pairs with zero source-year
   rows (nothing to copy) rather than erroring.
5. No migration needed — `Factor.year` and its indexes already exist.

**Frontend**

6. `backofficeDataManagement.ts`: add `initiateFactorCopyFromPreviousYear(moduleTypeId, dataEntryTypeId, year)`,
   mirrors `initiateComputedFactorSync` (`:602`) but posts
   `ingestion_method: IngestionMethod.COPY_PREVIOUS_YEAR`. Gate visibility
   per-submodule on `getPreviousYearSuccessfulJobs(year - 1, moduleTypeId, TargetType.FACTORS)`
   returning non-empty (nothing to copy from an unsynced prior year).
7. `DataManagementPage.vue`: add a "Copy from {year-1}" action next to each
   submodule's existing CSV-upload control, plus one page-level "Copy all
   factors from {year-1}" bulk button that loops the per-submodule call.
   Existing job-card/pipeline UI (issue #857) covers progress display with
   no changes.

Individual-row copy (copying a single factor entry rather than a whole
module/data-entry-type table) is out of scope for v1 — the issue's primary
ask ("open 2024 ... to have a previous year") is the bulk case; per-row copy
is deferred to a follow-up if operators ask for it after using bulk copy.

## Steps

- [x] Add `IngestionMethod.copy_previous_year` to `backend/app/models/data_ingestion.py`
- [x] Implement `FactorCopyProvider` (source-year lookup, clone-with-new-year, `upsert_factors`)
- [x] Register provider in `ProviderFactory.PROVIDERS` for `(copy_previous_year, TargetType.FACTORS)`
- [x] Unit test: `FactorCopyProvider` copies rows, is idempotent on retry, no-ops when source year is empty
- [x] Unit test: `sync_module_factors` endpoint accepts `ingestion_method=copy_previous_year` with `filters.source_year` override
- [x] Frontend: `initiateFactorCopyFromPreviousYear` in `backofficeDataManagement.ts`
- [x] Frontend: per-submodule "Copy from {year-1}" button (in `UploadCardFactors.vue` / `SubmoduleItem.vue`, consumed from `DataManagementPage.vue`'s module tree), gated on prior-year success via `getPreviousYearSuccessfulJobs`
- [x] Frontend: page-level "Copy all factors from {year-1}" bulk action in `DataManagementPage.vue` looping per-submodule calls, skipping pairs with no source-year factors
- [x] Manual/logical verification: reasoned through the end-to-end flow (see "Verification" note below) — no live app available in this environment to click through.

### Implementation notes (2026-07-09)

- The per-submodule "Copy from {year-1}" button lives on the existing
  `UploadCardFactors` card (next to "Compute Missing Factors"), wired
  through `SubmoduleItem.vue` → `useSubmoduleConfig.ts`, not directly in
  `DataManagementPage.vue` (that file only hosts the page-level bulk
  button) — the per-submodule UI composition already lived one level
  down from the page component before this change (mirrors how
  "Compute Missing Factors" is wired), so the new button follows the
  same layering rather than moving existing structure.
- A confirmation dialog (`CopyFactorsDialog.vue`, modeled on the
  existing `ComputedFactorDialog.vue`) gates both the per-submodule and
  bulk actions, since copying overwrites already-entered current-year
  factor rows for the affected data-entry type(s).
- Pre-existing, unrelated mechanism found during implementation: a
  file-replay "copy from previous year" flow already exists for
  individual data-entry-type dialogs (`useDataEntryDialog.ts` +
  `config.source_job_id` + `_resolve_source_job_to_file_path` in
  `data_sync.py`), which re-uploads the prior year's *processed CSV
  file* through the normal CSV provider. It is orthogonal to this
  plan's DB-level `FactorCopyProvider`: it depends on the source year's
  processed file still existing in file storage and only replays
  CSV-sourced factors, whereas `FactorCopyProvider` clones the `Factor`
  rows directly from the database and also covers factors that were
  never CSV-uploaded (e.g. seeded or computed). Both mechanisms now
  coexist; no changes were made to the file-replay path.
