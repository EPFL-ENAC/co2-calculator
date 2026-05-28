---
status: delivered
issue: 1183
last_updated: 2026-05-28
title: "Train CSV station disambiguation — country_code column (Phase 1)"
summary: "Adds origin_country_code / destination_country_code columns to the train CSV seed + committed-fixture files, defaulting to CH. Backend wiring (schemas, enrich_csv_row, resolve_train_station_for_csv) was already in place; this PR closes the data-side gap. Same-country collision cleanup (Phase 2) is explicitly deferred."
---

# 1183 — Train CSV station disambiguation, Phase 1

## 1. Problem

The train CSV format ships only station names (`origin_name`,
`destination_name`). Same-name stations exist in multiple countries
(e.g. `BERNE, CH` vs `BERNE, DE`), and the CSV-time resolver in
`app/modules/professional_travel/schemas.py::ProfessionalTravelTrainModuleHandler.enrich_csv_row`
cannot disambiguate cross-country collisions from names alone.

## 2. Pre-existing backend wiring (not changed by this PR)

- `app/modules/professional_travel/schemas.py`
  - `ProfessionalTravelTrainHandlerCreate` already declares
    `origin_country_code: Optional[str] = None` and the destination
    counterpart (lines ~159-160).
  - `ProfessionalTravelTrainModuleHandler.enrich_csv_row` already reads
    `enriched.get(f"{role}_country_code") or "CH"` (line 376) and
    forwards it to the resolver as `default_country_code`.
- `app/services/location_service.py::resolve_train_station_for_csv`
  already accepts the `default_country_code` parameter and applies it
  to the lookup.

So the runtime path already honours the column when present — Phase 1
is purely a data migration on the CSV side.

## 3. Phase 1 deliverable (this PR)

A small idempotent script that inserts the two columns into each train
CSV directly after its corresponding `*_name` column, defaulting every
existing row to `CH`.

- New script: `backend/scripts/add_country_codes_to_train_csvs.py`.
- Stdlib `csv` only. No new deps. ≤40-line functions, ≤2 nesting.
- Targets four files:
  - `backend/seed_data/travel_trains_data.csv`
  - `backend/seed_data/travel_trains_test.csv`
  - `backend/tests/fixtures/csv/travel_trains_smoke.csv`
  - `backend/tests/fixtures/csv/travel_trains_unknown_station.csv`

### Why include the trimmed fixtures in the script's scope?

`backend/seed_data/` is gitignored (`backend/.gitignore:39`) — those
CSVs are dev-only and never land in CI. The CI-safe trimmed fixtures in
`backend/tests/fixtures/csv/` are the only train CSVs that ship in
this repo. Without extending the script to those, the committed diff
would be the script + plan only and the new column contract would
never be exercised by CI. Both seed and fixture paths use the same
ingest header contract, so a single script covers both.

### Why CH as the default?

- Matches the project's data center of mass (all four committed
  sample stations are Swiss: Lausanne Gare, Zürich HB, Genève-Cornavin,
  Basel SBB).
- Matches the existing resolver fallback (`enrich_csv_row` line 376),
  so behaviour is preserved bit-for-bit on legacy CSVs without the
  column.

### Idempotency

Re-running the script on a file that already carries both columns is a
no-op (status: `unchanged`). Missing files (typical on a fresh clone —
`seed_data/` is gitignored) are reported and skipped, not treated as
an error.

## 4. Phase 2 — out of scope

Same-country collision cleanup is **explicitly deferred** to a follow-
up. Issue #1183 documents the surface:

- ~121 European same-country collisions (FI, DE, GB, UA, IT, NO, RS,
  ES, RO, BY, BA, PT, AT, FR, HU, PL).
- ~1500 non-European collisions dominated by RU/JP/MX/AU, deferred
  until a real ingest need surfaces.
- Three candidate mechanisms tracked in the issue body
  (location dedupe, curated winner map, distinctive seed names) —
  open PM decision.

This PR does not pick a Phase 2 mechanism. See issue #1183 for the
open question.

## 5. Backfill risk (accepted)

Legacy `DataEntry` rows ingested under the CH-default resolver may
already carry `natural_key`s that point at the Swiss station when the
upstream context was actually a different country. Project policy
(see project memory: "No DB backfill until v1.x", `v0.x` drops the DB
between deploys) means we **accept the drift** and do not migrate
historical rows. New uploads that supply the country_code column
resolve correctly going forward.

If a backfill ever becomes warranted (v1.x or before, by exception),
the path is to re-run `enrich_csv_row` against the historical CSVs
with the now-richer column. That's a Phase 3 conversation, not Phase
1.

## 6. Verification

E2E recipe in the PR description:

1. `cd backend && uv run python scripts/add_country_codes_to_train_csvs.py`
2. `git diff backend/tests/fixtures/csv/travel_trains_*.csv` — two new
   columns per file, all rows default to CH.
3. Re-run the script — no diff (idempotency).
4. `cd backend && uv run pytest tests/integration/services/data_ingestion/test_travel_pg.py -k train -v`
5. `cd backend && make type-check`

## 7. Files

- `backend/scripts/add_country_codes_to_train_csvs.py` — new.
- `backend/tests/fixtures/csv/travel_trains_smoke.csv` — +2 columns,
  rows default to CH.
- `backend/tests/fixtures/csv/travel_trains_unknown_station.csv` —
  same.
- `docs/src/implementation-plans/1183-train-csv-country-code.md` —
  this plan.
