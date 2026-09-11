---
status: delivered
issue: 2474
last_updated: 2026-09-11
summary: "Research-facilities Tableau transform merged every no-unit month of a facility into one yearly row before rows_missing_centre_financier was tallied, so the stat counted facilities instead of months; drop_reasons was also never reset per call. Same PR fixes the 'tuple index out of range' row error from #2700 (model-level pydantic errors have an empty loc) and records why the CPG animal-facility recalc fails: the computed factor backfill is never triggered by bootstrap or by a data upload."
---

# Research facilities: no-unit months under-counted (#2474)

## What shipped

- `ResearchFacilitiesApiProvider.transform_data` keeps monthly rows with no
  Centre financier unmerged. They can never load, and `_inject_module_ids`
  now counts one `rows_missing_centre_financier` per month, not per facility.
- `drop_reasons` is cleared at the top of `transform_data`, so a reused
  provider instance cannot report the previous call's tallies.
- `_format_pydantic_validation_error` (`base_csv_provider.py`) no longer
  indexes `loc[-1]`: a `@model_validator` error has an empty `loc`, which
  surfaced as `Row processing error: tuple index out of range` (#2700's
  open note). Model-level errors now keep the message alone, without the
  whole-row `input`, so row contents never land in job metadata.

Regression tests: `test_research_facilities_yearly_aggregation.py` (no-unit
months counted, drop_reasons reset) and `test_csv_row_error_formatting.py`.

## Investigation record: CPG animal-facility recalc failures

Dev worker log (2026-09) showed 36 `Missing kg_co2eq_sum for source
purchases_common in factor values for facility CPG` errors, 6 fish + 30
rodent. Reproduced identically on a local seed from
`input_data_v2.12.5_2026-09-03`.

- `researchfacilities_animals_factors.csv` leaves
  `kg_co2eq_sum_purchases_common` / `_purchases_additional` empty on purpose;
  `ResearchFacilitiesAnimalFactorUpdateProvider` is meant to fill them from
  the facility unit's carbon-report stats.
- Nothing triggers that computed step: `bootstrap_year` runs unit_sync →
  seed factors → module recalcs → aggregation and stops; a data upload for
  det 71 chains `emission_recalc` directly. The only trigger is the
  backoffice computed factor sync (`POST /sync/factors/6/71`, which chains
  its own recalc). Zero FACTORS+computed jobs existed in the job table.
- The animal handler raises on the missing key, so every CPG entry fails
  until that step runs. Not a key mismatch, not linked to the 7 skipped
  rows of the common-data upload (1 tuple-index crash, 6 units absent from
  unit sync).
- Open data question: the factors CSV maps CPG to unit `1321`, which the
  unit sync labels "CPG-GE, CPG - Administration". A unit "CPG, Center of
  PhenoGenomics" also exists (`20201` locally). All CPG purchases,
  equipment and rooms rows in the input files sit under `1321`, none under
  the other, so `1321` is the unit whose emissions the backfill would sum.

Decision pending with the maintainer: wire the computed backfill into the
pipeline (before the research-facilities recalc, in bootstrap and after a
det 70/71 data upload), or keep it a manual backoffice step and point the
error message at it.
