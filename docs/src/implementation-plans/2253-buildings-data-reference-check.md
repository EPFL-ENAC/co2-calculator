---
status: delivered
issue: 2253
last_updated: 2026-08-28
title: "Buildings data CSV: reject rows whose room is missing from the reference"
summary: "building_rooms_data.csv rows with a room_name absent from the BuildingRoom reference used to persist and silently compute with surface 0/None; ingestion now rejects those rows via the enrich_csv_row hook (same mechanism as the train #1186 natural-key check), so the upload finishes WARNING with per-row errors instead of a wrong total."
---

# Buildings data CSV: reject rows whose room is missing from the reference

## Problem

Issue #2253: an operator uploaded a `building_rooms_data.csv` whose
`room_name` values did not exactly match `building_rooms_reference.csv`.
The upload reported success; the mismatched rows persisted, resolved no
`room_surface_square_meter` at compute time, contributed zero emission,
and the module total was silently wrong.

The data→factor direction already fails loudly (row errors / job WARNING);
the data→reference direction had no ingest-time check at all — only a
`logger.warning` in `BuildingRoomModuleHandler.pre_compute`, which no
operator sees.

## Design

Reuse the existing per-row CSV enrichment hook (`enrich_csv_row`), the
same mechanism the train handler uses since #1186 to reject rows whose
station cannot be resolved. Returning a non-None error message makes the
provider skip the row and record it in `row_errors`, and
`_compute_ingestion_result` turns any skipped rows into a `WARNING`
terminal result with the re-upload hint (#1398) — exactly the behavior
the issue asks for, with no new plumbing.

The lookup mirrors `pre_compute`'s resolution: by `room_name` only, via
`BuildingRoomService.get_room`. Validating the `(building_name,
room_name)` pair would reject rows that compute fine today; consistency
with the compute path wins.

## Change

`backend/app/modules/buildings/handlers.py`:

- New module-level helper `_reject_unknown_room(data, session)` — returns
  a row error when `data["room_name"]` has no `BuildingRoom` row.
- `BuildingRoomModuleHandler.enrich_csv_row` and
  `BuildingEmbodiedEnergyModuleHandler.enrich_csv_row` delegate to it.
  Both DETs persist entries that resolve surface from the same reference
  table, so both get the same guard. `energy_combustion` doesn't
  reference rooms and is untouched.

`pre_compute`'s skip-and-warn behavior stays: entries created before this
check, or orphaned by a later reference re-upload (full delete+insert
semantics), still need the recalc-time skip.

UI/API single-entry creates are unaffected — the room dropdown is fed
from the reference endpoint, and `enrich_csv_row` only runs on the CSV
ingest path.

## Out of scope

- The back-office "Data Validation" doc line for references — the issue
  author adds it once this ships (per issue thread).
- Making the reference upload itself warn about newly-orphaned data
  entries (reverse direction).
