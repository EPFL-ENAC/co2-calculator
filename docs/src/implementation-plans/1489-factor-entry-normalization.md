---
status: in-progress
issue: 1489
last_updated: 2026-08-31
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

`backend/alembic/versions/2026_08_31_1935-09fe9e551783_...py` rewrites
existing `factors.classification` values to the same canonical form, then
merges rows whose identity collides after normalization: lowest id wins,
`data_entry_emissions.primary_factor_id` is repointed BEFORE the duplicates
are deleted (the FK is `ondelete=CASCADE`, an unpointed delete would silently
drop emission rows). Downgrade is a no-op: the old casing is gone by design.

Entry data (`data_entries.data`) is deliberately not migrated. That touches
validated emission data and needs its own audited pass; until then the
compute handlers keep their defensive `.lower()` on entry currency (see
deviations).

A unit test pins the migration's normalization function to the DTO aliases,
so the two cannot drift silently.

## Tests

- `tests/unit/schemas/test_normalized_fields.py`: canonical forms per alias,
  RoW sentinel, whitespace rejection, normalized-value-reaches-`data`
  regressions, an end-to-end FactorResolver match from a noisy payload, and
  the migration/DTO symmetry pin.
- `tests/unit/services/data_ingestion/test_factor_csv_normalized_identity.py`:
  re-importing the same purchase factor row with `CHF`/whitespace noise
  produces the identical classification identity.
- Existing suites updated where messages or blank-handling changed
  (blank optional codes now store `None`, not `""`).

## Deviations from the plan on the issue

- Kept the defensive `.lower()` in the purchase and external-cloud compute
  handlers instead of deleting them: pre-#1489 entries still carry
  un-normalized currency in `data` because this migration normalizes factors
  only. They go when entry data gets its audited migration.
- Added the two choke-point fixes above (data sync validator, provider
  classification from DTO); without them the typed aliases are cosmetic.
- `researchfacility_name` also got `IdentifierKey`, not just
  `researchfacility_id`: both arrive from spreadsheet exports and both join
  against the factor classification.

## Open questions for review

- Target branch: this went to `dev` as schema/DTO work. If the merge
  migration counts as pipeline-adjacent it can be re-targeted to
  `fix/pipeline-debug`.
- Reports whose duplicate factors got merged may want a recompute pass after
  deploy so recomputed numbers use the surviving factor row.
