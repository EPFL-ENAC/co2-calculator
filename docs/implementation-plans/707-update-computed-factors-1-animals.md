# Plan: 707 — Implement sync_module_factors (Backend only)

Using example of Research facilities module, this feature aims at allowing a backoffice manager to update factors that are already stored in the database. The update logic is module data entry type dependent.

**TL;DR**: Implement the sync_module_factors stub in app/api/v1/data_sync.py. For (module_type, data_entry_type, year), the endpoint walks all factors stored for those parameters and recomputes their values fields by pulling actual DataEntryEmission totals — using classification.researchfacility_id to locate the correct Unit → CarbonReport → CarbonReportModule → emissions. Reuses the existing DataIngestionJob + background-task infrastructure, so callers poll via SSE identically to sync_module_data_entries.

## Phase 1 — New ingestion method

### Step 1 – Add IngestionMethod.computed = 3 to DataIngestionMethod enum

- File: `data_ingestion.py`
- Distinguishes "compute from existing emissions" from csv/api imports.
- Requires an Alembic migration: `ALTER TYPE ingestion_method_enum ADD VALUE 'computed'` (native PostgreSQL enum — no transaction wrapper).

## Phase 2 — Factor-update provider

### Step 2 – Abstract BaseFactorUpdateProvider (new file)

- `backend/app/services/data_ingestion/factor_update_provider.py`
- Extends DataIngestionProvider; defines abstract compute_factor_values(factor, year, session) → dict | None.
- Concrete ingest() loop: fetch all factors for (data_entry_type_id, year) via FactorRepository.list_by_data_entry_type, call compute_factor_values, apply FactorRepository.update, track stats.

### Step 3 – Concrete ResearchFacilitiesAnimalFactorUpdateProvider (new file)

- `backend/app/services/data_ingestion/computed_providers/research_facilities_animal.py`
- For each factor:
  1. Read researchfacility_id from factor.classification.
  2. `UnitRepository.get_by_institutional_id(researchfacility_id)` → Unit.
  3. `CarbonReportRepository.get_by_unit_and_year(unit_id, year)` → CarbonReport.
  4. `CarbonReportModuleRepository` → find module for (carbon_report_id, module_type_id=research_facilities).
  5. `DataEntryEmissionRepository.get_stats(carbon_report_module_id, aggregate_by="emission_type_id")` → sums per emission_type.
  6. Map EmissionType leaf → source name (e.g. process_emissions → processemissions, buildings\_\_rooms → building_rooms, etc.).
  7. Return updated values dict: only overwrite kg*co2eq_sum*{source} keys; leave shares / use_unit / total_use untouched.
  8. Surface missing unit/carbon-report with a clear error — no silent skip.

### Step 4 – Register in ProviderFactory

- File: `provider_factory.py`
- Add entry: (ModuleTypeEnum.research_facilities, IngestionMethod.computed, TargetType.FACTORS, EntityType.MODULE_PER_YEAR) → ResearchFacilitiesAnimalFactorUpdateProvider.

## Phase 3 — API endpoint

### Step 5 – Implement sync_module_factors stub (depends on Steps 1–4)

- File: `data_sync.py`
- Fix route path typo: {module_id} → {module_type_id}.
- Remove duplicate permission check body (decorator already handles it).
- Validate syncRequest.year is mandatory.
- Set entity_type = EntityType.MODULE_PER_YEAR, call ProviderFactory.create_provider(..., ingestion_method=IngestionMethod.computed), create job, schedule background task, return SyncStatusResponse — mirrors sync_module_data_entries exactly.

## Phase 4 — Tests

### Step 6 – Unit tests for ResearchFacilitiesAnimalFactorUpdateProvider

- New file: `backend/tests/unit/services/data_ingestion/test_research_facilities_animal_factor_update.py`
- Cases: happy path (all sources), unit not found, carbon report not found, partial sources present.

### Step 7 – Extend test_provider_factory.py (parallel with step 6)

- Assert new (research_facilities, computed, FACTORS, MODULE_PER_YEAR) key resolves to the new provider.

## Relevant files

- `data_sync.py` — fill in stub
- `data_ingestion.py` — add computed = 3
- `backend/app/services/data_ingestion/factor_update_provider.py` — new abstract base
- `backend/app/services/data_ingestion/computed_providers/research_facilities_animal.py` — new concrete provider
- `provider_factory.py` — register
- `factor_repo.py` — reuse list_by_data_entry_type
- `data_entry_emission_repo.py` — reuse get_stats
- `versions` — new migration for native enum value
- `backend/tests/unit/services/data_ingestion/test_research_facilities_animal_factor_update.py` — new
- `test_provider_factory.py` — extend

## Verification

1. make lint + make typecheck (ruff + mypy strict) pass on all changed files.
2. New test file: all 4 cases pass.
3. Provider factory test: new registration asserted.
4. Manual: POST /data-sync/factors/research_facilities/mice_and_fish_animal_facilities body {"ingestion_method": 3, "target_type": 1, "year": 2025} → returns job_id; SSE polling → FINISHED/SUCCESS; Factor.values.kg_co2eq_sum_processemissions updated per facility.
5. ModulePerYearFactorCSVProvider tests still pass (no regression on CSV factor ingestion).

## Decisions

- IngestionMethod.computed = 3 avoids conflating this with api in job history.
- year is mandatory for this endpoint (unlike data-entry sync).
- Route typo {module_id} → {module_type_id} fixed as part of this PR.
- ResearchFacilitiesCommonFactorUpdateProvider (single kg_co2eq_sum) is out of scope.

## Further considerations

1. CarbonReportModuleRepository gap — confirm whether a method get_by_carbon_report_id_and_module_type already exists; if not, add it before Step 3 is executable.
2. Emission aggregation scope — get_stats aggregates all DataEntryEmission rows for a carbon_report_module_id; confirm that the research_facilities module stores all lab-emission sub-types (process, buildings, rooms, equipment, purchases) under a single CarbonReportModule, or whether separate modules need to be joined.
3. Alembic native-enum migration — ALTER TYPE … ADD VALUE cannot run inside a transaction; verify alembic.ini settings (transaction_per_migration) or add op.execute with explicit connect_args={"isolation_level": "AUTOCOMMIT"}.
