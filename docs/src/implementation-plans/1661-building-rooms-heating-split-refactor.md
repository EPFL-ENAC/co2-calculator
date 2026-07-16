---
status: delivered
issue: 1575
last_updated: 2026-07-05
title: "Building rooms: emit a single heating leaf (electric OR thermal) per room"
summary: "Refactor the PR #1661 heating split so a room emits only the heating leaf matching its factor's energy_type, ending the thermal/electric double-count (#1575)."
---

# Building rooms: single heating leaf per room

## Context

Issue **#1575**: the building-rooms results graph showed the **same** quantity for
centralized (thermal) and electric heating. Uploading only an electric factor
should give **0 thermal / 100% electric**; instead both appeared equal.

PR **#1661** first split heating into `heating_elec` / `heating_thermal` leaves,
but emitted a room's `kwh/m²` against **both** leaves and zeroed the mismatched
one with an overloaded `conversion_factor = 0`. That approach was wrong on four
counts:

1. It emitted a spurious `0.0` row for the non-applicable heating leaf.
2. It overloaded `conversion_factor` as a kill-switch — and a legitimate `0.0`
   (e.g. a carbon-free thermal network) was coerced to `1.0` by a falsy `or`.
3. It silently dropped **all** heating at ZZ level (missing/invalid `room_type`),
   because the gate keyed on `emission_type.parent`.
4. `energy_type` was declared a value field yet read from a place inconsistent
   with the classification-based ingestion.

## Approach

Decide the correct heating leaf **once, up front**, from the matched factor's
`energy_type`, so a room emits **electric OR thermal — never both**. Selection
moves out of the per-leaf formula and into emission-type resolution.

### Changes

- **`energy_type` → classification.** Moved back to
  `buildings_classification_fields`; alias-normalization dropped (stored values
  are already `electric` / `thermal`).
- **Resolve the factor's energy type in the service.**
  `DataEntryEmissionService._get_building_energy_type` reads the matched factor's
  `classification.energy_type` — cache-aware for bulk recalc, single DB `get`
  otherwise. It **fails loudly** on a missing factor or an invalid `energy_type`
  rather than silently dropping heating. `None` means "no matched factor → no
  heating".
- **Explicit dispatch, no smuggling.** `resolve_emission_types` takes an explicit
  keyword `building_energy_type` and routes building rooms through
  `_resolve_building_rooms(data, energy_type)`, which appends only the matching
  `heating_electric` / `heating_thermal` leaf (WW leaf when `room_type` is set,
  ZZ parent otherwise). `data_entry.data` is never mutated.
- **Enum rename.** `EmissionType.buildings__rooms__heating_elec` →
  `heating_electric`; frontend chart constants updated to match.
- **Formula simplified.** `_compute_kwh_emission` no longer inspects
  `energy_type`. `conversion_factor` applies to heating only, defaults to `1.0`,
  and an explicit `is None` check preserves a legitimate `0.0`.

## Result

- A room with only an electric factor emits `0` thermal / `100%` electric (and
  vice-versa).
- Rollup no longer double-counts: **65.0**, not 95.0.
- Corrupt/missing building factors fail loudly instead of vanishing heating.

## Tests

- **Unit** — `test_buildings_schemas.py` (formula + `resolve_computations`
  selection), `test_building_rooms_resolver.py` (leaf selection per energy type
  and room-type presence), `test_data_entry_emission_service.py` (energy-type
  resolution, cache path, loud failure on corrupt factor).
- **Integration** — `test_buildings_csv_pg.py`: an electric factor emits only the
  electric leaf, a thermal factor only the thermal leaf, no double-count;
  `test_strategy_b_rematch_pg.py` updated for the enum rename.

## Delivery

- Branch `fix/1661-refactor` → commit `9f2d6bb8` (fix) + `206fdc8f`
  (`int()`-cast cleanup on `primary_factor_id`).
- PR **#1714** → `dev`, closes #1575.

## Follow-up

Frontend graph differentiation (issue **#1465**) is tracked separately.
