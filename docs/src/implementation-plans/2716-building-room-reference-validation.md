---
status: delivered
issue: 2716
last_updated: 2026-09-11
summary: "Close every silent-zero path in the building-room reference pipeline: the reference pack is validated as a whole at import (empty cells, duplicate rooms, buildings without factors), uploads naming a room with no surface are rejected, room names match with spaces ignored and persist in the reference spelling (#2268), a building with no factor row fails at compute instead of producing no rows, and the unvalidated seed_building_rooms importer is removed."
---

# Building-room reference validation (#2716)

## Context

Buildings emissions are `surface × kWh/m² × EF`. Every known failure in the
room-reference pipeline produced a missing or zero surface silently, so a
wrong calculation looked like a completed one. Issue #2716 is the master
issue; #2253 (unknown room on upload) and #2268 (spacing) are symptoms.
The delivered pack `input_data_v2.12.5_2026-09-03` has 4 rooms with an empty
surface, 12 byte-identical duplicate rooms, 2 buildings absent from
`building_rooms_factors.csv` and 3 trailing-space locations, and all of it
imported.

## What already existed (verified, not redone)

- Upload-time unknown-room rejection (#2253, `8ee8843`) in
  `modules/buildings/handlers.py::_reject_unknown_room`, one query per session.
- Compute-time failure on a null surface (#2050 Track I/J):
  `data_entry_emission_service.py::_apply_formula` raises when a formula
  returns `None`; the recalc loop records it per entry. Covered by
  `test_building_room_without_ref_data_fails_loudly`.
- Reference import header, `room_type` vocabulary, non-negative and
  parseable-surface checks (#1489, #2588).

## Delivered

### A. Whole-pack validation at import

`csv_providers/reference_data.py::_ingest_building_rooms` parses every row
(cells stripped, file line kept), then raises one `ValueError` listing every
defect grouped by class, capped at 20 lines per class. Nothing is written
when any row fails.

| Class                | Rule                                                                                                                                                                                                                                |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Empty mandatory cell | `building_location`, `building_name`, `room_name`, `room_type`, `room_surface_square_meter` (0 stays valid; the guard is on None). Rows are rejected, no longer counted as skipped.                                                 |
| Duplicate room       | `room_name` compared with all spaces removed, both line numbers reported.                                                                                                                                                           |
| Unknown building     | `building_name` must appear as a classification value of a buildings `Factor` row in any year (`FactorRepository.list_classification_values`). An empty factors table is one message telling the admin to upload the factors first. |

All five columns are now required headers. `building_location` stays
mandatory even though the issue's target schema allows None: the column is
`nullable=False` and relaxing it needs a migration, deferred.

### B. Upload guard: surface and space-insensitive match

`_reject_unknown_room` loads `dict[normalized_name -> (room_name, surface)]`
once per session (`BuildingRoomService.get_room_surfaces`, replacing
`get_room_names`). A row is rejected when the room is unknown or when its
surface is None; otherwise `room_name` is rewritten to the reference's own
spelling, so `pre_compute`, sort and filter keep exact matching.
`normalize_room_name` lives in `modules/buildings/data_entries.py` and is
shared with the import-side duplicate check, so the index can never resolve
one name to two rooms. The manual form already picks rooms from the
reference, so no frontend change.

### C. No factor for the building is an error

`BuildingRoomModuleHandler.resolve_computations` raises when
`primary_factor_id` is None instead of returning no computations. Embodied
energy and energy combustion are untouched (embodied's `default` fallback is
tracked in #2715).

### D. One importer

`app/seed/seed_building_rooms.py` bypassed every provider check and was what
`make seed-data` ran. Deleted; `make seed-data` now runs
`seed_generic_factors` then `seed_reference_data`, the same provider the
backoffice upload uses. `bootstrap_years` already seeds in that order. The
note in `bootstrap-years-from-input-data.md` saying the seeder is untouched
is superseded by this plan.

## Consequence for the current pack

`INPUT_DATA/building_rooms_reference.csv` as delivered (v2.12.5) is rejected
by `seed_reference_data` and by the backoffice upload with one message
listing lines 19514/19838/19870/19885 (empty surface, `ZEBRAFISH`/`B` also
unknown buildings) and the 12 duplicate pairs. Trailing spaces are stripped
and are not a defect. The data manager fixes the pack (issue #2716 has the
per-line list); locally, trim those 16 lines meanwhile.

## Tests

- `tests/unit/services/data_ingestion/csv_providers/test_reference_data.py`:
  empty surface / empty cells / duplicates (exact and spacing-only) /
  unknown building / empty factors table / several classes in one message /
  valid rows incl. `0.0` against a real `Factor` row.
- `tests/unit/modules/test_buildings_enrich_csv_row.py`: null surface
  rejected, `0.0` passes, `AI 9121` resolves and persists as `AI 9 121` for
  both handlers, one query per session.
- `tests/unit/modules/test_buildings_schemas.py`: missing factor raises,
  naming the building.
