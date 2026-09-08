---
status: delivered
issue: 1489
last_updated: 2026-09-08
title: "Factor/entry join-key normalization"
summary: "Shared pydantic field types normalize every factor-resolution join key symmetrically on both DTO families (strip, lowered currency/cabin class, uppered country codes with the RoW sentinel kept, spreadsheet numeric ids coerced, blank optional keys to None). A data migration rewrites existing factor classifications to the same canonical form and merges the duplicates that fall out, repointing emissions first."
---

# 1489: Factor/entry join-key normalization

Implements the normalization plan Guilbert posted on #1489 (2026-08-24).
Written up after the fact alongside the PR, since the work could not wait for
his review round; deviations from his plan are listed at the bottom.

## Problem

Factor resolution compares `factor.classification[k]` to `entry.data[k]` by
exact string equality (`factor_resolver._build_maps`), and the factor upsert
keys on `(data_entry_type_id, year, emission_type_id, classification::text)`.
Nothing guaranteed the two sides agreed on casing or whitespace:

- an entry saved with currency `CHF` never matched a factor stored as `chf`
- re-importing the same factor CSV with different casing inserted a second
  factor row instead of updating the first
- each module hand-rolled its own `_non_empty` / `str(v)` validators, so the
  rules drifted per module

## Canonical forms

Defined once in `backend/app/schemas/fields.py` and applied symmetrically to
the `*FactorCreate/Update` and `*HandlerCreate/Update` DTO of every field that
participates in a factor lookup:

| Alias                       | Rule                                                                                                 | Used for                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `CurrencyCode`              | strip + lower                                                                                        | currency everywhere                                      |
| `CountryCode`               | strip + upper, `RoW` sentinel kept as-is (case-insensitive)                                          | travel country codes                                     |
| `ClassificationKey`         | strip only, case carries meaning                                                                     | names, codes, categories                                 |
| `OptionalClassificationKey` | strip, blank becomes `None`                                                                          | optional join keys (matches the CSV provider convention) |
| `IdentifierKey`             | spreadsheet numeric forms collapse (`1`, `1.0`, `"1.0"` all become `"1"`, zero-padded ids untouched) | `researchfacility_id` / `researchfacility_name`          |

Closed-vocabulary validators (cabin class, energy type) keep their membership
checks but normalize with strip + lower before comparing.

## The two choke points the plan missed

Typing the DTO fields alone normalizes nothing that persists. Two code paths
discarded the validated DTO output:

1. **Entries**: `DataEntryPayloadMixin.unflatten_payload` (mode="before")
   copies the RAW payload into `data` before field validators run, and `data`
   is what `DataEntryService.create` persists. Fixed with a central
   mode="after" validator on the mixin that syncs every validated field value
   back into `data` (only for keys already present there, so PATCH semantics
   survive).
2. **Factors**: `base_factor_csv_provider._process_row` hand-built
   `classification` from the raw CSV row and only used the DTO for type
   validation. It now copies the validated DTO value into `classification`
   for every classification field, so the canonical form is what lands in
   the upsert identity.

## Data migration

`backend/alembic/versions/2026_09_08_1000-09fe9e551783_...py` rewrites
existing `factors.classification` values to the same canonical form, then
merges rows whose identity collides after normalization: lowest id wins,
`data_entry_emissions.primary_factor_id` is repointed BEFORE the duplicates
are deleted (the FK is `ondelete=CASCADE`, an unpointed delete would silently
drop emission rows). Downgrade is a no-op: the old casing is gone by design.

Entry data (`data_entries.data`) gets the same treatment in the follow-up
migration `cf237968fba7`, see plan 2592 (shipped in the same PR after the
lead approved it on 2026-09-08). With both in place the compute handlers no
longer re-lower entry currency: the stored value is the canonical one.

The migration was re-parented onto `095d98bc390c` when the PR was rebuilt on
`dev` (2026-09-08), so the chain is linear: `095d98bc390c` → `09fe9e551783`
→ `cf237968fba7`.

A unit test pins the migration's normalization function to the DTO aliases,
so the two cannot drift silently.

## Closed vocabularies from the #1489 audit (#2588, #2587)

Bundled into the same PR on the lead's decision (2026-09-08):

- Headcount factors: `headcount_category`, `headcount_class` and `unit` are
  pinned to the values the shipped factor CSVs carry (`HEADCOUNT_*` lists in
  `app/modules/headcount/factors.py`), strip + lower first. `headcount_subclass`
  is an `OptionalClassificationKey`.
- Plane factors: `category` is pinned to `short_to_medium_haul` /
  `medium_to_long_haul`, `max_distance` must exceed `min_distance`, and a
  factor upload fails when two factors of one cabin class have overlapping
  `[min, max)` bands (`check_plane_distance_bands`, run by the new
  `BaseFactorHandler.validate_year_factors` hook on the year's resulting set
  in `BaseFactorCSVProvider._validate_year_factor_sets`, before the commit).
  `get_haul_category` takes the first band a distance falls into, so overlap
  would make resolution order-dependent.
- Building rooms reference upload: `room_type` checked against
  `VALID_ROOM_TYPES`, `room_surface_square_meter >= 0`.
- External AI factor payloads resolve the provider through `resolve_ai` and
  raise `EmissionTypeResolutionError` on an unknown one (#2587).

## Tests

- `tests/unit/schemas/test_normalized_fields.py`: canonical forms per alias,
  RoW sentinel, whitespace rejection, normalized-value-reaches-`data`
  regressions, an end-to-end FactorResolver match from a noisy payload, and
  the migration/DTO symmetry pin.
- `tests/unit/services/data_ingestion/test_factor_csv_normalized_identity.py`:
  re-importing the same purchase factor row with `CHF`/whitespace noise
  produces the identical classification identity.
- `tests/unit/services/data_ingestion/test_factor_csv_shipped_identity.py`:
  every row of every shipped factor CSV (committed smoke fixture always,
  `backend/INPUT_DATA/*_factors.csv` when present) keeps the same
  classification under whitespace/casing/`1.0` noise, and passes the closed
  vocabularies.
- `tests/unit/modules/test_headcount_factor_schemas.py`,
  `test_professional_travel_schemas.py`,
  `test_base_factor_csv_provider.py`: the vocabularies, the band check and
  its wiring.
- `tests/integration/test_alembic_migrations.py`
  (`test_1489_factor_classifications_normalized_and_duplicates_merged`):
  real Postgres, old-style factor rows plus two emissions, upgrade, assert
  canonical form, merge into the lowest id, emissions repointed, and a
  downgrade + re-upgrade changes nothing.
- `tests/integration/services/data_ingestion/test_normalized_entry_pipeline_pg.py`:
  a noisy CSV row (`PIC-IT`, `EUR`, `1.0`) through the real ingest chain
  stores normalized `data`, resolves the canonical factor and computes the
  expected kg CO2eq.
- Existing suites updated where messages or blank-handling changed
  (blank optional codes now store `None`, not `""`).

## Deviations from the plan on the issue

- The defensive `.lower()` in the purchase and external-cloud compute
  handlers is gone, as the plan asked, but only because the entry-data
  migration (plan 2592) ships in the same PR.
- Added the two choke-point fixes above (data sync validator, provider
  classification from DTO); without them the typed aliases are cosmetic.
- `researchfacility_name` also got `IdentifierKey`, not just
  `researchfacility_id`: both arrive from spreadsheet exports and both join
  against the factor classification.

## Decisions (lead, 2026-09-08)

- Target branch stays `dev`.
- No recompute after the factor merge migration: emission rows are
  repointed, numbers move at the next natural recompute.
