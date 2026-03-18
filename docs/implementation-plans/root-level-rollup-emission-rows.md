# Root Rollup Emission Rows for Sortable kg_co2eq

## TL;DR

Add a **parent-level rollup `DataEntryEmission` row** per data entry that sums all its leaf emissions. This enables direct `ORDER BY` on `kg_co2eq` via a simple JOIN (no subquery aggregation). The rollup emission_type_id is the parent node in the EmissionType tree (e.g., `buildings__rooms = 60100` for building entries). Identification: rollup rows are the ones whose `emission_type_id` matches the new `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` mapping.

## Design Decisions

- **No schema migration needed**: rollup rows are regular `DataEntryEmission` rows; identified by their non-leaf `emission_type_id` matching the mapping.
- **Headcount excluded**: member/student don't show kg_co2eq in table. Their 4 root types (food, waste, commuting, grey_energy) have no shared parent. No rollup created.
- **Single-leaf entries still get a rollup**: For consistency, entries with only 1 leaf emission (equipment, purchases, etc.) get a rollup row at their parent node. This keeps `get_submodule_data` uniform — always JOIN on the rollup emission_type_id, no conditional paths.
- **Scope on rollup**: set to `None` — scope only meaningful on leaves for scope aggregation. Rollup rows must be excluded from scope sums.
- **`primary_factor_id` on rollup**: set to `None` — it's an aggregate, not tied to one factor.
- **`recompute_stats` unchanged**: it already queries by leaf `emission_type_id` and sums up the tree. Rollup rows won't interfere because `get_subtree_leaves()` only returns actual leaves.

## Steps

### Phase 1: Mapping (no dependencies)

1. In `data_entry_emission_type_map.py`, add a new dict `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION: dict[DataEntryTypeEnum, EmissionType | None]` mapping each `DataEntryTypeEnum` to its parent rollup EmissionType:
   - `building` → `EmissionType.buildings__rooms` (60100)
   - `energy_combustion` → `EmissionType.buildings` (60000) — parent of combustion
   - `plane` → `EmissionType.professional_travel__plane` (50200)
   - `train` → `EmissionType.professional_travel__train` (50100)
   - `scientific` → `EmissionType.equipment` (80000)
   - `it` → `EmissionType.equipment` (80000)
   - `other` → `EmissionType.equipment` (80000)
   - `process_emissions` → `EmissionType.process_emissions` (70000)
   - `external_clouds` → `EmissionType.external__clouds` (110100)
   - `external_ai` → `EmissionType.external__ai` (110200)
   - All purchase types → `EmissionType.purchases` (90000)
   - `research_facilities` → `EmissionType.research_facilities` (100000)
   - `mice_and_fish_animal_facilities` → `EmissionType.research_facilities` (100000)
   - `member` → `None` (no rollup)
   - `student` → `None` (no rollup)

### Phase 2: Emission Compute (_depends on Phase 1_)

2. In `DataEntryEmissionService.prepare_create()` (`data_entry_emission_service.py`):
   - After computing all leaf emissions, look up `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[data_entry_type]`
   - If not `None`, create one additional `DataEntryEmission` row:
     - `emission_type_id` = rollup EmissionType value
     - `kg_co2eq` = sum of all leaf emissions' kg_co2eq
     - `scope` = `None`
     - `primary_factor_id` = `None`
     - `meta` = `{"is_rollup": True, "leaf_emission_type_ids": [...]}`
   - Append to the returned list (gets persisted by existing `bulk_create`)

### Phase 3: Query Simplification (_depends on Phase 2_)

3. In `get_submodule_data()` (`data_entry_repo.py`):
   - Replace the `emission_agg` subquery with a direct JOIN on `DataEntryEmission` filtered to the rollup `emission_type_id` for this `data_entry_type_id`
   - Import and use `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` to get the rollup emission_type_id
   - For headcount (rollup is `None`): keep existing subquery approach or skip kg_co2eq join entirely
   - Update sort_map override: `sort_map["kg_co2eq"] = DataEntryEmission.kg_co2eq` now works directly since there's exactly 1 row per data_entry in the join
   - The `primary_factor` join changes: currently it piggybacks on `emission_agg.c.primary_factor_id`. With rollup, this needs to come from the rollup row or from a separate leaf emission join. Since rollup has `primary_factor_id = None`, keep a separate subquery/join for factor (using `func.min(DataEntryEmission.primary_factor_id)` filtered to leaf rows), OR store the primary_factor_id on the rollup meta.

### Phase 4: Stats Safety (_parallel with Phase 3_)

4. In `compute_module_stats()` (`carbon_report_module_service.py`):
   - Verify rollup rows don't cause double-counting. Current `get_stats()` aggregates by `emission_type_id`. If it sums all emission_type_ids, rollup nodes will be included → double-count.
   - Fix: filter `get_stats()` query to exclude rollup emission_type_ids, OR rely on the existing logic that only uses leaf values from `EMISSION_SCOPE` (which doesn't include rollup types → they'd be ignored in scope sums).
   - Verify `by_emission_type` in the stats JSON: the existing code already computes rollups in-memory via `get_subtree_leaves()`. Having rollup rows in DB shouldn't affect this IF the aggregation query groups by `emission_type_id` — the rollup type IDs would just appear as extra keys. Confirm they're harmless or filter them out.

## Relevant Files

- `backend/app/utils/data_entry_emission_type_map.py` — add `DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION` dict
- `backend/app/services/data_entry_emission_service.py` — modify `prepare_create()` to append rollup row
- `backend/app/repositories/data_entry_repo.py` — simplify `get_submodule_data()` query
- `backend/app/services/carbon_report_module_service.py` — verify `compute_module_stats()` / `get_stats()` doesn't double-count
- `backend/app/repositories/data_entry_emission_repo.py` — verify `get_stats()` query shape
- All handler `sort_map` entries for `kg_co2eq` — now `DataEntryEmission.kg_co2eq` works directly (no change needed if query is rewritten)
- `backend/app/services/data_ingestion/base_csv_provider.py` — bulk import path also calls `prepare_create()`, so rollup rows are automatically included

## Verification

1. Write a unit test for `prepare_create()`: given a building data_entry with 5 leaf emissions, verify 6 rows returned (5 leaves + 1 rollup at `buildings__rooms`), rollup `kg_co2eq` equals sum of leaves.
2. Write a unit test for single-leaf entry (e.g., equipment): verify 2 rows returned (1 leaf + 1 rollup at `equipment`), both with same `kg_co2eq`.
3. Write a unit test for headcount: verify no rollup row created.
4. Verify sorting: hit `GET /submodule_data?sort_by=kg_co2eq&sort_order=asc` for buildings and equipment — confirm correct ordering.
5. Verify `recompute_stats()` doesn't double-count: create entries, recompute, check scope totals match expected.
6. Run existing test suite (`make test` in backend/).

## Further Considerations

1. **Data migration**: Existing `DataEntryEmission` rows in production won't have rollup rows. Options: (A) run a one-time migration script that recomputes all emissions (calls `upsert_by_data_entry` for every existing entry), or (B) add an Alembic data migration. Recommend (A) as a management command.

/!\ SUPER IMPORTANT we need to fix it first 2. **primary_factor on rollup**: The current `get_submodule_data` enriches response with `primary_factor.values` and `primary_factor.classification`. With rollup JOIN, `primary_factor_id` is `None`. Two options: (A) store the "representative" primary_factor_id on the rollup row (e.g., the first leaf's factor), or (B) keep a separate join for factor resolution. Recommend (A) — store `primary_factor_id` from the first leaf on the rollup for display purposes.

## FURTHER Information

Looking at the `DATA_ENTRY_TO_EMISSION_TYPES` mapping, here are the `DataEntryTypeEnum` values that have **exactly one item** in their array (meaning they produce a single emission row per data entry):

## Single Emission Type (No Rollup Logic Needed)

**Energy Combustion:**

- [`energy_combustion`](backend/app/models/data_entry.py) → [`EmissionType.buildings__combustion`](backend/app/models/data_entry_emission.py)

**Equipment:**

- [`scientific`](backend/app/models/data_entry.py) → [`EmissionType.equipment__scientific`](backend/app/models/data_entry_emission.py)
- [`it`](backend/app/models/data_entry.py) → [`EmissionType.equipment__it`](backend/app/models/data_entry_emission.py)
- [`other`](backend/app/models/data_entry.py) → [`EmissionType.equipment__other`](backend/app/models/data_entry_emission.py)

**Purchases:**

- [`scientific_equipment`](backend/app/models/data_entry.py) → [`EmissionType.purchases__scientific_equipment`](backend/app/models/data_entry_emission.py)
- [`it_equipment`](backend/app/models/data_entry.py) → [`EmissionType.purchases__it_equipment`](backend/app/models/data_entry_emission.py)
- [`consumable_accessories`](backend/app/models/data_entry.py) → [`EmissionType.purchases__consumable_accessories`](backend/app/models/data_entry_emission.py)
- [`biological_chemical_gaseous_product`](backend/app/models/data_entry.py) → [`EmissionType.purchases__biological_chemical_gaseous`](backend/app/models/data_entry_emission.py)
- [`services`](backend/app/models/data_entry.py) → [`EmissionType.purchases__services`](backend/app/models/data_entry_emission.py)
- [`vehicles`](backend/app/models/data_entry.py) → [`EmissionType.purchases__vehicles`](backend/app/models/data_entry_emission.py)
- [`other_purchases`](backend/app/models/data_entry.py) → [`EmissionType.purchases__other`](backend/app/models/data_entry_emission.py)
- [`additional_purchases`](backend/app/models/data_entry.py) → [`EmissionType.purchases__additional`](backend/app/models/data_entry_emission.py)

**Research Facilities:**

- [`research_facilities`](backend/app/models/data_entry_emission.py) → [`EmissionType.research_facilities__facilities`](backend/app/models/data_entry_emission.py)
- [`mice_and_fish_animal_facilities`](backend/app/models/data_entry.py) → [`EmissionType.research_facilities__animal`](backend/app/models/data_entry_emission.py)

---

## Multiple Emission Types (Need Rollup)

**Headcount:**

- [`member`](backend/app/models/data_entry.py), [`student`](backend/app/models/data_entry.py) → 4 types each (food, waste, commuting, grey_energy)

**Buildings:**

- [`building`](backend/app/models/data_entry.py) → 5 types (lighting, cooling, ventilation, heating_elec, heating_thermal)

---

## Runtime Resolved (None in Static Mapping)

These are `None` in the static mapping and resolved at runtime:

- [`plane`](backend/app/models/data_entry.py), [`train`](backend/app/models/data_entry.py) → resolved by cabin class
- [`process_emissions`](backend/app/models/data_entry_emission.py) → resolved by gas type
- [`external_clouds`](backend/app/models/data_entry.py) → resolved by service type
- [`external_ai`](backend/app/models/data_entry.py) → resolved by provider (but has static fallback list)

---

**Summary:** 13 data entry types produce exactly **one emission row** per entry, so their rollup is straightforward (the rollup row equals the single leaf row).

## Summary

Identified the 13 `DataEntryTypeEnum` values that produce exactly one emission row per data entry (no rollup logic complexity needed):

**Single emission types:** `energy_combustion`, `scientific`, `it`, `other`, `scientific_equipment`, `it_equipment`, `consumable_accessories`, `biological_chemical_gaseous_product`, `services`, `vehicles`, `other_purchases`, `additional_purchases`, `research_facilities`, `mice_and_fish_animal_facilities`

**Multiple emission types (need rollup):** `member`, `student` (4 types each), `building` (5 types)

**Runtime resolved:** `plane`, `train`, `process_emissions`, `external_clouds`, `external_ai`

Task completed!
