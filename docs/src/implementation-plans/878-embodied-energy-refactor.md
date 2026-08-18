---
status: in-progress
issue: 878
last_updated: 2026-08-18
title: "Embodied energy: room_name-keyed derived entries + reconciliation"
summary: "Refactors building_embodied_energy derived entries to persist only room_name — building_name and surface resolve from BuildingRoom reference data at compute/read time — and rewrites EmbodiedEnergyWorkflow as an idempotent reconcile of the derived-entry multiset against the module's building parents. CSV derivation moves from a job-end read-back to per-batch creation."
---

# Embodied energy: `room_name`-keyed derived entries + reconciliation

## Context

Follow-up refactor on top of
[878-embodied-energy-csv-ingestion](878-embodied-energy-csv-ingestion.md)
(unified derived-entry creation behind `DERIVED_ENTRY_WORKFLOWS`). Two
structural problems remained:

1. **Derived entries persisted `building_name`** — a value copied from the
   parent at creation time. The parent `building` rows themselves persist
   only `room_name` and resolve everything else from the `BuildingRoom`
   reference table, so the derived rows carried a second, denormalized copy
   that could go stale and that clients could overwrite.
2. **The workflow tracked parent↔derived identity per entry**
   (`_get_embodied_energy_entry_id`, separate create/update/delete branches).
   Every CRUD path had to know the mutated entry's previous shape, and any
   missed path (bulk ingest, historically) left orphans or gaps.

## Approach

Make the derived-entry set a **pure function of the parents**: one
`building_embodied_energy` row per parent `building` `room_name`
(multiset — duplicate parent rooms get duplicate derived rows), with
`{"room_name"}` as the entire persisted payload.

- **Reference data resolves at compute/read time.** The handler's
  `pre_compute` looks up `BuildingRoom` by `room_name` for
  `building_name` + `room_surface_square_meter` (shared `_prefetch_rooms` /
  `_resolve_room` helpers with the rooms handler; slice-cached in bulk).
  An unresolvable room yields no context, so the formula produces no
  emission — the module's "skip, don't default" semantic.
- **CRUD sync is a reconcile, not per-entry bookkeeping.**
  `EmbodiedEnergyWorkflow.post_create/post_update/post_delete` all call one
  `_reconcile`: read the module's entries post-commit, count wanted
  `room_name`s from the parents, delete surplus derived rows (falsy or
  over-represented names, highest ids first), create missing ones via
  `CarbonReportModuleWorkflow`. Idempotent; needs no knowledge of what
  changed. `post_delete` now takes `data_entry_type_id` instead of the
  deleted item's id.
- **Bulk ingest derives per batch.** `_create_derived_entries(batch)` runs
  inside `_process_batch` on the just-inserted rows instead of a job-end
  read-back by `created_by_id` (`list_by_creator_and_type` deleted). The
  registry protocol now receives the whole batch and each workflow selects
  its own source rows. Bulk ingest's delete-then-recreate already clears
  stale derived rows, so no reconcile is needed there.

## Changes

- `workflows/embodied_energy.py` — rewrite: `_reconcile` (Counter-based
  multiset convergence) replaces `_post_create_building` /
  `_post_update_building` / `_get_embodied_energy_entry_id`;
  `create_derived_entries_for` becomes a pure map
  `building rows → {"room_name"} payloads` over the batch.
- `workflows/derived_entry_registry.py` — protocol takes a whole ingest
  batch; workflows filter it themselves.
- `services/data_ingestion/base_csv_provider.py` — derived-entry creation
  moves from `finalize` to `_process_batch`.
- `modules/buildings/data_entries.py` — DTOs keyed on `room_name`;
  `DiscardClientBuildingFieldsMixin` drops any client-sent `building_name`;
  response exposes resolved `building_name` / `room_surface_square_meter`
  as optional.
- `modules/buildings/handlers.py` — `BuildingEmbodiedEnergyModuleHandler`
  gains `prefetch_slice`/`pre_compute` (shared room helpers); `group_map` /
  `filter_map` read `building_name` from a `BuildingRoom` join and add
  `room_name`; factor context takes `building_name` from the resolved ctx.
- `repositories/data_entry_emission_repo.py` — embodied breakdown joins
  `BuildingRoom` (inner join: entries whose `room_name` no longer resolves
  carry no emission and drop out).
- `repositories/data_entry_repo.py` — `building_embodied_energy` included
  in the buildings enrichment branch (resolved `building_name` in listings);
  `list_by_creator_and_type` removed.
- `api/v1/carbon_report_module.py` — delete endpoint passes the entry's
  `data_entry_type_id` to `post_delete`.
- `seed/random_generator/seed_data_entries.py` — seeds `room_name`.

## Tests

- `tests/integration/services/data_ingestion/test_buildings_csv_pg.py` —
  derived rows carry `{"room_name"}` payloads; per-batch creation covered.
- `tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py`
  — rematch path updated to the batch-level registry protocol.
- `tests/unit/repositories/test_data_entry_emission_repo.py` — embodied
  breakdown resolves `building_name` through the `BuildingRoom` join.

## Delivery

Branch `fix/878-construction-not-showing`, on top of
`0e42be999` (bulk-ingest derivation) and `bbc8bea21` (registry
unification). No migration: pre-refactor derived rows persisted
`building_name` without `room_name`, so they compute no emission under the
new handler and count as surplus (falsy `room_name`) in the reconcile —
the next parent CRUD mutation or re-ingest of the module deletes them and
recreates `room_name`-keyed rows from the parents.
