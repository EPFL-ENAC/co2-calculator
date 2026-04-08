# Plan: 707-ext — sync_module_factors for research_facilities common (DE type 70)

## TL;DR

Add `ResearchFacilitiesCommonFactorUpdateProvider` that recomputes `kg_co2eq_sum`
(single total) for data_entry_type=70 (research_facilities) factors, by summing ALL
DataEntryEmission totals from the corresponding facility's CarbonReport.
Mirrors the animal provider pattern but with a single-field output. Also updates the
ProviderFactory to use 5-tuple keys for computed providers so both 70 and 71
can coexist.

---

## Phase 1 — Factory key update (enables both providers to coexist)

### Step 1 — Update `provider_factory.py` to use 5-tuple for computed providers

- File: `backend/app/services/data_ingestion/provider_factory.py`
- Remove the existing 4-tuple entry: `(research_facilities, computed, FACTORS, MODULE_PER_YEAR)`
- Add new import: `ResearchFacilitiesCommonFactorUpdateProvider`
- Add two 5-tuple entries to a dedicated `COMPUTED_FACTOR_PROVIDERS` dict (or extend PROVIDERS):
  - `(research_facilities, mice_and_fish_animal_facilities, computed, FACTORS, MODULE_PER_YEAR)` → `ResearchFacilitiesAnimalFactorUpdateProvider`
  - `(research_facilities, research_facilities, computed, FACTORS, MODULE_PER_YEAR)` → `ResearchFacilitiesCommonFactorUpdateProvider`
- Update `get_provider_by_keys`: when `data_entry_type_id` is provided, try 5-tuple `(module_type, data_entry_type, ingestion_method, target_type, entity_type)` first; fall back to 4-tuple if not found (for CSV/API providers that don't have data_entry_type in key).
- Update `PROVIDERS_BY_CLASS_NAME` to include common provider.

## Phase 2 — New concrete provider

### Step 2 — Add `ResearchFacilitiesCommonFactorUpdateProvider` (new file)

- File: `backend/app/services/data_ingestion/computed_providers/research_facilities_common.py`
- Extends `BaseFactorUpdateProvider`
- `compute_factor_values(factor, year, session)`:
  1. Read `researchfacility_id` from `factor.classification.get("researchfacility_id")`
  2. Return `None` + warning log if absent (same pattern as animal provider)
  3. `UnitRepository(session).get_by_institutional_id(researchfacility_id)` → Unit (raise ValueError if None)
  4. `CarbonReportRepository(session).get_by_unit_and_year(unit.id, year)` → CarbonReport (raise ValueError if None)
  5. `DataEntryEmissionRepository(session).get_emission_breakdown(carbon_report.id)` → list of (module_type_id, emission_type_id, kg)
  6. Sum all `kg` values → `total: float`
  7. Return `{"kg_co2eq_sum": total}`
- Only `kg_co2eq_sum` is overwritten; `use_unit` and `total_use` are left untouched (handled by base class merge logic).

## Phase 3 — Tests

### Step 3 — Unit tests for `ResearchFacilitiesCommonFactorUpdateProvider` (new file)

- File: `backend/tests/unit/services/data_ingestion/test_research_facilities_common_factor_update.py`
- Mirror structure of `test_research_facilities_animal_factor_update.py`
- Cases:
  1. Happy path: multiple emission rows from different modules → `kg_co2eq_sum` = sum of all
  2. Unit not found → `ValueError` raised
  3. CarbonReport not found → `ValueError` raised
  4. Zero emissions → returns `{"kg_co2eq_sum": 0.0}`
  5. Missing `researchfacility_id` in classification → returns `None` (skipped)

### Step 4 — Extend `test_provider_factory.py` (parallel with Step 3)

- File: `backend/tests/unit/services/data_ingestion/test_provider_factory.py`
- Add assertion: 5-tuple `(research_facilities, research_facilities, computed, FACTORS, MODULE_PER_YEAR)` → `ResearchFacilitiesCommonFactorUpdateProvider`
- Update existing assertion for animal provider to use the new 5-tuple key

---

## Relevant files

- `backend/app/services/data_ingestion/provider_factory.py` — update registration (5-tuple) + lookup
- `backend/app/services/data_ingestion/computed_providers/research_facilities_common.py` — NEW
- `backend/app/services/data_ingestion/computed_providers/__init__.py` — no change needed (comment-only)
- `backend/app/services/data_ingestion/computed_providers/research_facilities_animal.py` — reference only
- `backend/app/services/data_ingestion/factor_update_provider.py` — reference/no change
- `backend/app/api/v1/data_sync.py` — no change needed (already passes data_entry_type_id in config)
- `backend/app/repositories/data_entry_emission_repo.py` — reuse get_emission_breakdown()
- `backend/app/repositories/unit_repo.py` — reuse get_by_institutional_id()
- `backend/app/repositories/carbon_report_repo.py` — reuse get_by_unit_and_year()
- `backend/tests/unit/services/data_ingestion/test_research_facilities_common_factor_update.py` — NEW
- `backend/tests/unit/services/data_ingestion/test_provider_factory.py` — extend

## Verification

1. `make lint && make typecheck` pass on all changed files.
2. New test file: all 5 cases pass.
3. Updated provider factory test: new and updated registrations asserted.
4. Manual: `POST /data-sync/factors/research_facilities/research_facilities` body `{"ingestion_method": 3, "target_type": 1, "year": 2025}` → returns job_id; SSE polling → FINISHED/SUCCESS; `Factor.values.kg_co2eq_sum` updated per facility.
5. Regression: `POST /data-sync/factors/research_facilities/mice_and_fish_animal_facilities` still resolves to `ResearchFacilitiesAnimalFactorUpdateProvider` (5-tuple lookup).

## Decisions

- 5-tuple factory key for computed providers; CSV/API providers remain 4-tuple (fallback).
- `kg_co2eq_sum` = ALL emission types across entire CarbonReport (via `get_emission_breakdown()`).
- `use_unit` and `total_use` left untouched — billing/usage denominator comes from CSV ingestion.
- No Alembic migration needed (no schema change).
- No changes to `data_sync.py` or `factor_update_provider.py`.
