---
status: delivered
last_updated: 2026-07-23
title: "Bootstrap year configurations from INPUT_DATA"
summary: "make bootstrap-years replays the whole post-db-drop backoffice click-path — year configuration, unit sync, every factor CSV, the three reference CSVs, and the reduction-objective files + goals — from backend/INPUT_DATA, for 2025 and 2026. No data entries."
---

# Bootstrap year configurations from INPUT_DATA

## Problem

After every `make db-drop` / `make clean-db`, a developer had to redo the whole
backoffice click-path by hand: create the year, wait for the Accred unit sync,
upload ~15 factor CSVs plus the 3 reference CSVs, then fill the three
reduction-objective file slots and re-enter the institutional goals. Several
times a week, ~15 minutes each.

Second problem found on the way: `app/seed/seed_generic_factors.py` (behind
`make seed-data`) pointed at `backend/seed_data/` while listing the _current_
filenames, which only exist in `backend/INPUT_DATA/` — `equipment_factors.csv`,
`purchases_centralized_factors.csv`, `headcount_students_factors.csv`,
`buildings_construction_renovation_factors.csv`. It died on
`FileNotFoundError`.

## What shipped

`make bootstrap-years` (in `backend/Makefile`, `YEARS ?= 2025 2026`) runs
`app.seed.bootstrap_years`. Per year, in order:

1. **Year configuration** — insert the `year_configuration` row with
   `generate_default_year_config()` if absent. Years are validated against
   `settings.MIN_CONFIGURABLE_YEAR` and the current year, the same bounds
   `POST /year-configuration/{year}` enforces.
2. **Unit sync** — build the same `unit_sync` `DataIngestionJob` the endpoint
   enqueues (`ensure_pipeline_exists` → `create_ingestion_job` →
   `meta.config.target_year`) and **await** `run_job(job_id)` instead of firing
   it in the background. `run_job` converts handler failures into
   FINISHED+ERROR rather than raising, so the job row is re-read afterwards and
   a non-`SUCCESS` result raises. This is what creates `units`, `users`,
   `carbon_reports`, `carbon_report_modules` and the `configuration_completed`
   stamp that unblocks uploads.
3. **Factors** — `seed_all_factors(session, year)` over `FACTOR_SEEDS`.
4. **Reference data** — `seed_all_reference_data(session, year)`.
5. **Emission recalculation** — one `module_emission_recalc` job per module,
   mirroring `POST /sync/recalculate-emissions/{module_type_id}`. See
   [Why recalculation has to run](#why-recalculation-has-to-run) below.
6. **Reduction objectives + goals** — the three CSVs plus goals
   `2030 / 10 % / ref 2016`, `2035 / 10 % / ref 2016`, `2040 / 10 % / ref 2016`.
7. **Open the year** — `is_started = True`.

Data entries are deliberately not seeded;

### Files

| File                                            | Change                                                                  |
| ----------------------------------------------- | ----------------------------------------------------------------------- |
| `backend/app/seed/bootstrap_years.py`           | New — the orchestrator + `--years` CLI                                  |
| `backend/app/seed/seed_reference_data.py`       | New — `LocalReferenceCSVProvider` + `REFERENCE_SEEDS`                   |
| `backend/app/seed/seed_reduction_objectives.py` | New — CSV loading, file storage, `DEFAULT_GOALS`                        |
| `backend/app/seed/seed_generic_factors.py`      | Repointed at `INPUT_DATA/`; `seed_factors`/`main` parameterized by year |
| `backend/app/tasks/_background.py`              | New `wait_for_background_tasks()` drain helper                          |
| `backend/Makefile`                              | `bootstrap-years` target                                                |

### Reuse over reinvention

- `LocalReferenceCSVProvider` subclasses the production
  `ReferenceDataCSVProvider` and overrides only `validate_connection`,
  `_stage_file` (read from disk), `_move_to_processed` (no-op) and `_update_job`
  (no-op) — exactly the shape `LocalFactorCSVProvider` already uses in
  `csv_providers/local_seed.py`. Header validation, the locations
  COPY + natural-key UPSERT, the per-mode replace and the building-rooms
  delete-and-insert are inherited untouched.
- Reduction-objective CSVs go through the endpoint's own
  `validate_reduction_objective_csv()`, and are stored using the endpoint's own
  `get_files_storage_path()` / `generate_unique_filename()`, so the on-disk
  layout cannot drift from a real upload.
- Every seeded CSV plants a `create_seed_stub_job(...)` row so the backoffice
  data-management cards show the seed instead of staying blank.

### Why recalculation has to run

Seeded factors go in through `LocalFactorCSVProvider`, which bypasses
`factor_ingest` and therefore never fans out the `emission_recalc` children a
real upload chains. `get_recalculation_status_by_year` flags any type whose
latest FACTORS job is newer than its latest computed DATA_ENTRIES job — so
without this step backoffice showed **"Recalculation needed"** on every module
right after a clean bootstrap.

The fan-out targets are read off `FACTOR_SEEDS`, not off
`get_recalculation_status_by_year`: a multi-type CSV (`equipment_factors.csv`,
`purchases_common_factors.csv`) plants its stub job with
`data_entry_type_id = NULL`, and that query filters NULLs out, so it does not
name every type that just received factors.

`module_emission_recalc` (rather than per-type `emission_recalc`) is used
because its handler already writes the per-type stub jobs the status query
matches on, and chains a single `aggregation` child per module instead of one
per type.

Those chained aggregations are dispatched through `fire_and_forget`. A CLI has
to wait for them before the event loop closes or they are cancelled mid-run and
left stuck in RUNNING — hence `wait_for_background_tasks()` in
`app/tasks/_background.py`.

### Reference seeds

| CSV in `INPUT_DATA/`           | data_entry_type | module_type               |
| ------------------------------ | --------------- | ------------------------- |
| `travel_planes_reference.csv`  | `plane` (20)    | `professional_travel` (2) |
| `travel_trains_reference.csv`  | `train` (21)    | `professional_travel` (2) |
| `building_rooms_reference.csv` | `building` (30) | `buildings` (3)           |

`seed_locations.py` / `seed_building_rooms.py` are untouched — they still back
`make seed-data` from `seed_data/`, and `_NATURAL_KEY_EXPR` still lives in
`seed_locations.py` where `reference_data.py` imports it.

## Verification

Ran twice against a local Postgres, second run confirming idempotency
(identical counts, no unique-index collisions on `is_current` or factor
identity):

- `year_configuration`: 2025 + 2026, `is_started=t`, `configuration_completed`
  set, 3 goals and 3 file entries each
- `factors`: 24 296 per year
- `locations`: 4 478 plane + 51 299 train
- `building_rooms`: 19 925
- `data_entries`: 0
- 18 seeded `is_current` ingestion jobs per year (15 FACTORS + 3 REFERENCE_DATA)
- `needs_recalculation = false` for every `(module, data_entry_type)` — no
  "Recalculation needed" badges in backoffice
- every `data_ingestion_jobs` row FINISHED/SUCCESS, including the chained
  `aggregation` children — nothing stuck in RUNNING
