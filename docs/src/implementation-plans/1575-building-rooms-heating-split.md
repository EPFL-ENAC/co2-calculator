---
status: delivered
issue: 1575
last_updated: 2026-06-30
title: "Fix building rooms heating split (electric vs thermal)"
summary: "Emit only the heating leaf matching the factor's energy_type instead of fanning heating energy into both heating_elec and heating_thermal and zeroing the mismatch. energy_type returns to classification; leaf selection moves to resolve_computations; the formula stops handling energy_type."
---

## Problem

Issue [#1575]: the building-rooms graph shows the **same** quantity for both
centralized (thermal) and electric heating. Root cause: `_resolve_building_rooms`
(`backend/app/utils/data_entry_emission_type_map.py`) always emits **both**
`heating_elec` and `heating_thermal` leaves for every room, and both map to the
same `heating_kwh_per_square_meter` field — so a room's heating energy is counted
twice, regardless of which heating mode the room actually uses.

The data model: **one factor per `(building_name, room_type)`**, carrying a single
`energy_type` (electric *or* thermal) and one `conversion_factor`. A room is
electric **or** thermal — never both.

### Why the prior fix (PR #1661) was wrong

PR #1661 kept emitting **both** heating leaves, then set `conversion_factor = 0`
inside `_compute_kwh_emission` on the leaf whose `energy_type` didn't match, so it
computed to `0.0`. Problems:

1. It wrote a spurious `0.0` emission row for the leaf that doesn't apply, instead
   of no row (a `0` that means "n/a" — a silent fallback).
2. It overloaded `conversion_factor` (a real physical multiplier) as a kill-switch.
3. It silently dropped **all** heating when `room_type` was missing/invalid: the
   gate checked `emission_type.parent == heating_elec`, which only matches
   room-type (WW) leaves; at the generic (ZZ) fallback level both heating leaves
   zeroed out while lighting/cooling/ventilation still computed.
4. It declared `energy_type` a **value** field, but the formula read it from
   `factor.values` while the integration fixture (and pre-#1661 convention) keep
   it in **classification** — so the end-to-end path never fed `energy_type` where
   the code read it; only hand-fed unit tests exercised the fix.

## Solution

Emit **only** the heating leaf matching the factor's `energy_type`, decided from
the entry's `primary_factor_id`. Never emit both. Apply `conversion_factor` to that
single real leaf. All changes in `backend/app/modules/buildings/schemas.py` unless
noted.

1. **`energy_type` → classification.** Added to `buildings_classification_fields`,
   removed from `buildings_value_fields`. Safe: the factor lookup keys only on
   `building_name` (kind) + `room_type` (subkind) via
   `FactorRepository.get_by_classification` (`one_or_none()`); `energy_type` is a
   stored, non-key classification column. One factor per `(building, room_type)` ⇒
   no ambiguous match.

2. **Load `energy_type` in `pre_compute`.** New `_resolve_energy_type` helper
   fetches the entry's primary factor (`FactorService.get`) and reads
   `classification["energy_type"]` into `ctx`. `primary_factor_id` is present at
   both first compute (`resolve_primary_factor_id`) and recalc. Comment notes the
   bulk-recalc `factor_cache` could be threaded in to skip the per-entry fetch.

3. **Select the heating leaf in `resolve_computations`.** New module-level
   `_heating_family(et)` resolves a leaf's family at both WW and ZZ levels. For
   heating leaves, `resolve_computations` returns `[]` (no row) when the family
   doesn't match `ctx["energy_type"]`.

4. **Simplify `_compute_kwh_emission`.** Removed the `energy_type`/zeroing block.
   `conversion_factor` applies to heating (default 1.0), else 1.0; the formula no
   longer reads `emission_type` or `energy_type`.

5. **Tests.** Unit tests drop the zeroing cases and add `resolve_computations`
   selection coverage (WW + ZZ match/mismatch, missing `primary_factor_id`,
   non-heating always emits). Integration test
   (`tests/integration/services/data_ingestion/test_buildings_csv_pg.py`) rollup
   `95.0` → `65.0`, asserts the mismatched heating leaf is **absent**, and adds a
   thermal-only variant.

## Out of scope

- `resolve_factor_emission_type` (factor CSV import) — unchanged.
- Issue [#1465] (frontend graph differentiation) — separate frontend task; this
  backend change (one real heating leaf per room) is its precondition.

## Verification

- `make lint` / `make type-check` — green.
- `uv run pytest backend/tests/unit/modules/test_buildings_schemas.py
  backend/tests/integration/services/data_ingestion/test_buildings_csv_pg.py`.
- End-to-end intent: an electric factor yields a `heating_elec` row and **no**
  `heating_thermal` row (and vice versa); the rollup excludes the phantom
  contribution.
