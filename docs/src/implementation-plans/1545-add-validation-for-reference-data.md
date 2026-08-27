---
status: delivered
issue: 1545
last_updated: 2026-08-20
title: "Reference-data CSV upload: fail on unexpected column names"
summary: "ReferenceDataCSVProvider silently logged (never raised) on unrecognized CSV columns, so a misspelled column resolved to None on every row with no error. Made unknown columns a hard failure; confirmed reduction_objective CSVs already validate column names correctly (every field is required)."
---

# Reference-data CSV upload: fail on unexpected column names

## Problem

Issue: uploading `building_rooms_reference.csv` with `room_surface_square_meters`
(extra `s`) instead of `room_surface_square_meter` was accepted with no error,
and every row silently got `room_surface_square_meter=None`, breaking the
building-rooms calculation with no visible cause. Comment on the issue:
"this bug is ONLY for References Data, because we don't do data_validation of
Reference data."

Root cause, confirmed by reading the code: `ReferenceDataCSVProvider._validate_headers`
(`backend/app/services/data_ingestion/csv_providers/reference_data.py`) checks
that all `required_columns` are present, but for anything outside
`expected_columns` it only `logger.warning(...)`s and continues — it never
raises. `room_surface_square_meter` is in `BUILDING_ROOMS_EXPECTED_COLUMNS`
but not in the required set, so a typo'd header passes validation, and the
per-row `raw.get("room_surface_square_meter")` silently returns `None`. The
same function also validates the plane/train `locations_reference.csv`
headers, so one fix covers both files named in the issue.

**Also checked (per issue-thread follow-up): reduction_objective CSVs.**
`InstitutionalFootprintRow`, `PopulationProjectionRow`, and `UnitScenarioRow`
(`backend/app/schemas/year_configuration.py`) — the DTOs behind the
footprint/population/scenarios reduction-objective CSV uploads — declare
every field as `Field(...)` (required, no optional columns). Their header
check (`base_reduction_objective_csv_provider.py::_validate_csv_headers`)
only checks required columns, but since every column there is required, a
misspelled column name already makes the required-columns check fail with
"CSV is missing required columns: ...". No bug found; no change made.

## Design

Change the "unknown columns" branch in `ReferenceDataCSVProvider._validate_headers`
from a warning log to a `raise ValueError(...)`, matching the style of the
existing "missing required columns" error a few lines above. The error
propagates through the existing job-error path (`_setup_and_validate` /
`_run` catches the exception and marks the job `FINISHED/ERROR` with the
message), so the failure surfaces to the user the same way every other CSV
validation failure already does — no new plumbing needed.

Scoped to this one function only. Verified the real seed CSVs
(`backend/INPUT_DATA/{travel_planes,travel_trains,building_rooms}_reference.csv`)
have headers that exactly match their `EXPECTED_COLUMNS` sets, so this is not
a behavior change for any file the app actually ships with — only for a CSV
whose header doesn't match the schema.

## Steps

- [x] `ReferenceDataCSVProvider._validate_headers`: raise `ValueError` listing
      the unexpected columns (and the full expected set) instead of logging a
      warning and continuing.
- [x] Regression test: upload a `building_rooms_reference.csv`-shaped header
      with `room_surface_square_meter` misspelled and assert `_validate_headers`
      raises (`backend/tests/unit/services/data_ingestion/csv_providers/test_reference_data.py::test_validate_headers_rejects_unknown_columns`).
- [x] Confirmed real seed CSV headers under `backend/INPUT_DATA/` still pass
      (no accidental breakage of the shipped seed data).
- [x] Confirmed reduction_objective CSV column validation already fails
      correctly on a misspelled column (all fields required) — no code
      change needed there.
