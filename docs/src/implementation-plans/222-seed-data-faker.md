---
status: delivered
issue: 222
last_updated: 2026-05-28
title: "Faker seed-data: ~800 data_entry rows, ERD-aligned"
summary: "Right-size the random generator to ~800 rows, fix payload drift against current Pydantic schemas, wire it into the Makefile."
---

# Plan: Faker seed-data — ~800 rows, aligned to current ERD

## TL;DR

The random Faker seeder under `backend/app/seed/random_generator/` was sized for
a multi-million-row stress test and had drifted from the current Pydantic
schemas (e.g. `active_usage_hours` vs `active_usage_hours_per_week`,
`function`/`sciper` vs `position_title`/`position_category`/`user_institutional_id`).
It also wasn't reachable from `make seed-data` (commented-out call with a typo in
the module path), and `seed_all.py` had broken imports.

This change:

1. Targets ~800 `data_entry` rows total (was unbounded, max ≈ 8M) so local
   dev / smoke testing stays fast.
2. Realigns every builder payload to the current create-DTO field names.
3. Splits the plane/train builder so each writes the IATA / station-name fields
   its schema requires.
4. Makes `DATA_ENTRY_TYPE_TO_DTO` exhaustive over `MODULE_TYPE_TO_DATA_ENTRY_TYPES`,
   so the generator's random pick can never `KeyError` mid-batch.
5. Enables the per-row Pydantic validation (was commented out) — drift now
   surfaces in the seeder, not on first read by the API.
6. Adds `make seed-data-random` and a regression smoke test.

## Row-count math

`seed_carbon_reports` creates `(unit × year × module_type)` modules; the data
entries seeder loops modules and appends `randint(MIN, MAX)` entries each:

```text
total_rows ≈ NUM_UNITS × len(YEARS) × len(ALL_MODULE_TYPE_IDS) × avg(entries/module)
           = 5         × 3          × 8                       × 7                  = 840
```

- `NUM_UNITS` reduced from 300 → 5 in
  `app/seed/random_generator/populate_units_and_users.py`.
- `NUM_USERS` reduced from 1000 → 40 (must satisfy
  `3 × NUM_UNITS ≤ NUM_USERS ≤ 15 × NUM_UNITS` so `distribute_users` converges).
- `YEARS = [2023, 2024, 2025]` (unchanged in `seed_carbon_reports.py`).
- `entries_per_module` window changed from `randint(10, 220)` (avg 115) →
  `randint(4, 10)` (avg 7) in `seed_data_entries.py`. The bounds are pulled out
  as `ENTRIES_PER_MODULE_MIN/MAX` module constants and asserted by the smoke
  test (`test_entries_per_module_window_targets_800_rows`).

Target: **800 ±100**. Actual expected mean: **840**.

## Drift fixes (per builder)

| Builder | Before | After |
| --- | --- | --- |
| `build_professional_travel` (single) | `traveler_name`, `origin_location_id`, `destination_location_id`, `transport_mode` | Split into `build_plane_travel` (writes `user_institutional_id`, `origin_iata`, `destination_iata`, `cabin_class` ∈ {eco,business,first}) and `build_train_travel` (writes `user_institutional_id`, `origin_name`, `destination_name`, `cabin_class` ∈ {first,second}) |
| `build_equipment` | `equipment_class` Optional, `active_usage_hours`, `passive_usage_hours`, sum unbounded | `equipment_class` required, renamed to `active_usage_hours_per_week`/`standby_usage_hours_per_week`, sum capped at 168 to satisfy `_EquipmentUsageHoursValidationMixin` |
| `build_headcount` | `function`, `sciper`, missing `user_institutional_id` | `position_title`, `position_category` (from `POSITION_CATEGORY_VALUES`), required `user_institutional_id` |
| `build_external_cloud` | `provider` wrapped in `maybe()` | `provider` always present, adds `currency` ∈ {chf,eur,usd} |
| `build_external_ai` | `requests_per_user_per_day` was an int | Drawn from `REQUESTS_FREQUENCY_OPTIONS` string enum; `fte_count` ≥ 0.1 per validator |
| `build_purchase` | `total_spent_amount` wrapped in `maybe()` | Required; `currency` added |
| (new) `build_purchase_additional` | — | `name`, `unit`, `annual_consumption`, `coef_to_kg` |
| (new) `build_building_room` | — | Required `building_name`, `room_name`; `room_type` from `VALID_ROOM_TYPES`; ratio ∈ [0,1] |
| (new) `build_energy_combustion` | — | Required `name`, `quantity` ≥ 0 |
| (new) `build_building_embodied_energy` | — | Required `building_name` |
| (new) `build_process_emissions` | — | Required `category`, `quantity` ≥ 0 |
| (new) `build_research_facility_common` | — | All-optional payload matching `ResearchFacilitiesCommonHandlerCreate` |
| (new) `build_research_facility_animal` | — | Common payload + `researchfacility_type` |

`DATA_ENTRY_TYPE_TO_DTO` was also wrong on three rows — `building` →
`EquipmentHandlerCreate`, `process_emissions` → `EquipmentHandlerCreate`,
`scientific_equipment` → `EquipmentHandlerCreate` (should all be the
module-native DTO). The rewritten map now covers every reachable
`DataEntryTypeEnum` value, asserted by
`test_dto_map_covers_every_reachable_data_entry_type`.

## `data_entry_emissions` schema drift

Past the per-row payload drift, the emissions writer was also writing two
columns that no longer exist on the table:

| Column | Old seeder | Current `DataEntryEmissionBase` |
| --- | --- | --- |
| `subcategory` (TEXT) | written | removed (emission_type.path is the source of truth) |
| `formula_version` (TEXT) | written as top-level column | folded into `meta.formula_version` |
| `additional_value` (FLOAT) | not written | new nullable polymorphic quantity |
| `scope` (INT) | not written | scope id (1/2/3 or NULL on rollups) |

`copy_insert_emissions` now creates a tmp table whose columns match the live
schema in order, and `generate_emissions_for_entry` emits an 8-tuple in the
same order (entry_id, emission_type, primary_factor_id, kg_co2eq,
additional_value, scope, meta, computed_at). `formula_version` is preserved
inside `meta` so the seeded trace stays auditable.

This drift was the second crash uncovered while running the generator against
a real DB; without the fix `seed-data-random` would `UndefinedColumnError`
on the very first emissions batch.

## Enabled per-row validation

`seed_data_entries.py:generate_data_entries_for_module` previously commented
out the Pydantic-DTO instantiation. With the drift fixes in place, the seeder
now does:

```python
dto_instance = dto_class(
    data_entry_type_id=data_entry_type.value,
    carbon_report_module_id=module_id,
    **payload_dict,
)
rows.append((..., json.dumps(dto_instance.data, default=str), ...))
```

`DataEntryPayloadMixin.unflatten_payload` wraps the flat builder dict into
`{"data": {...}}`; we persist `dto_instance.data` so the JSONB column matches
the API-write shape. Any future builder/schema drift now blows up at seed
time with a Pydantic `ValidationError`, not silently as a stale JSON column.

## Makefile change

Existing `seed-data` target left untouched (it still runs the small CSV /
locations / building-rooms / factors seeders).

Added a dedicated target so contributors can opt in to the heavier random
data without changing existing flows:

```make
.PHONY: seed-data-random
seed-data-random: ## Seed ~800 random data_entry rows via Faker (issue #222)
	$(UV) run -m app.seed.random_generator.seed_all
```

`seed_all.py` itself was rewired:

- Imports now point at `app.seed.random_generator.*` (were `app.seed.*`,
  which didn't resolve).
- The previously-commented `populate_units_and_users` call is now active —
  the random orchestrator no longer depends on a hand-seeded users table.

## User & lab seeding (existing, no net-new)

The pre-existing `populate_units_and_users.py` already handles labs (`units`)
and users via `asyncpg` `COPY`, including admin-role grants. That code path
covers the success criterion *"Seed data are generated for user and labs"* in
issue #222; this change only resizes its constants.

## Regression smoke test

New: `backend/tests/unit/seed/test_random_generator_builders.py`. Runs without
a DB and would catch every drift fix above. 18 parametrized cases, all green:

- For each `(dto_class, builder)` pair: 50 generated payloads must validate.
- Every reachable `DataEntryTypeEnum` is in `DATA_ENTRY_TYPE_TO_DTO`.
- Every DTO in the map has a registered builder.
- The configured `ENTRIES_PER_MODULE_MIN/MAX` window stays in the 800 ±100 band.

## Files touched

- `backend/app/seed/random_generator/seed_data_entries.py` — builders + DTO
  map rewritten, validation enabled, row count tuned.
- `backend/app/seed/random_generator/populate_units_and_users.py` —
  `NUM_UNITS=5`, `NUM_USERS=40`.
- `backend/app/seed/random_generator/seed_all.py` — fixed imports, wired in
  `populate_units_and_users`, dropped unused clean-data hook.
- `backend/Makefile` — added `seed-data-random` target, removed stale typo'd
  comment from `seed-data`.
- `backend/tests/unit/seed/test_random_generator_builders.py` — new
  regression net.

## Out of scope

- The Faker generator still skips `data_entry_emissions` factor lookups
  (random `EmissionType` + null `primary_factor_id`); aligning emissions to
  real factor rows is a follow-up if/when benchmarks need it.
- `data_entries.data` rows reference `user_institutional_id` values that do
  not match the seeded `users.institutional_id` set — the seed flow has no
  FK between the JSON payload and the users table, so this is cosmetic.
  Closing the loop is a follow-up (would require sampling from
  `unit_user_rows` rather than `randint`).
