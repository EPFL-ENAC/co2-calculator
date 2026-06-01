---
status: delivered
issue: 1183
last_updated: 2026-05-29
title: "Train CSV station disambiguation — required country_code"
summary: "Sources the train location seed from the trainline-eu stations.csv (ISO-2 country per station) and makes country_code REQUIRED in the train CSV trip resolver — no more CH default. Retires the CH-backfill script."
---

# 1183 — Train CSV station disambiguation

## 1. Problem

The train CSV trip format ships station names (`origin_name`,
`destination_name`). Same-name stations exist in multiple countries
(`BERNE, CH` vs `BERNE, DE`), so the CSV-time resolver in
`ProfessionalTravelTrainModuleHandler.enrich_csv_row` cannot disambiguate
cross-country collisions from names alone.

The earlier approach defaulted the missing country to `CH`. That silently
mis-resolved every non-Swiss station and violated the no-silent-fallbacks
rule. This iteration removes the default and requires the country instead —
made viable by sourcing the seed from a dataset that carries country natively.

## 2. Location seed: trainline-eu `stations.csv`

The train location seed is built from the open trainline-eu dataset
(<https://github.com/trainline-eu/stations>), which ships an ISO-2 `country`
per station — so country codes come from the source, not a backfill.

- Builder: `backend/scripts/build_train_seed_from_trainline.py`
  (stdlib `csv` only; LF terminators; ≤40-line functions).
- Input `backend/stations.csv` (`;`-delimited, gitignored) →
  output `backend/seed_data/seed_travel_location_train.csv` (the 10-column
  comma schema `ReferenceDataCSVProvider` ingests).
- Kept rows: `is_suggestable=t`, `is_airport≠t`, non-empty
  `latitude`/`longitude` (NOT NULL in `locations`), non-empty `country`.
  → **51,299 stations**.
- `continent`/`municipality`/`iata_code`/`airport_size` are absent from the
  source and stay blank (all optional for trains); `keywords` mirrors `name`
  for station search.

Re-upload via the backoffice **train station reference** slot
(`data_entry_type_id=21`, not plane=20).

## 3. Required country_code in the trip resolver

`enrich_csv_row` now **rejects** any train CSV row that lacks a
`{role}_country_code` for an endpoint without a precomputed
`{role}_natural_key` — before any station lookup. There is no `CH` default.

- `app/modules/professional_travel/schemas.py::enrich_csv_row` — missing
  country_code → row error `Missing {role}_country_code`.
- `app/services/location_service.py::resolve_train_station_for_csv` —
  `country_code` is now a required parameter (no `default_country_code="CH"`).
- UI/API entries are unaffected: they carry `*_natural_key` from the station
  autocomplete and skip the resolver branch entirely.

`location_repo.search_locations` keeps its CH-first **autocomplete ranking** —
that is UI ordering, not an ingestion default, and is out of scope here.

## 4. Tests

- `tests/unit/services/data_ingestion/test_train_enrich_csv_row.py` — new.
  Asserts a row missing `origin`/`destination` country_code is rejected and
  never queries the DB (sentinel session). Fast, no Postgres.
- `tests/integration/.../test_travel_pg.py::test_train_csv_resolves_station_by_required_country_code`
  — renamed from the CH-default-override test; pins the CH-vs-DE `Berne`
  collision, asserting `destination_country_code=DE` resolves to the German
  station.

## 5. Backfill risk (accepted)

Legacy `DataEntry` rows ingested under the old CH-default resolver may carry
`natural_key`s pointing at the Swiss station. Per project policy
("No DB backfill until v1.x" — `v0.x` drops the DB between deploys) we
**accept the drift** and do not migrate historical rows.

## 6. Verification

1. `cd backend && uv run python scripts/build_train_seed_from_trainline.py`
   → `wrote 51299 train stations`.
2. `uv run pytest tests/unit/services/data_ingestion/test_train_enrich_csv_row.py`
3. `uv run pytest tests/integration/services/data_ingestion/test_travel_pg.py -k train`
4. `make type-check`

## 7. Files

- `backend/scripts/build_train_seed_from_trainline.py` — new (replaces the
  retired `add_country_codes_to_train_csvs.py`).
- `backend/app/modules/professional_travel/schemas.py` — require country_code.
- `backend/app/services/location_service.py` — drop `CH` default param.
- `backend/tests/unit/services/data_ingestion/test_train_enrich_csv_row.py` — new.
- `backend/tests/integration/services/data_ingestion/test_travel_pg.py` — test rename/rescope.
- `docs/src/implementation-plans/1183-train-csv-country-code.md` — this plan.
