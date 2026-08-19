---
status: delivered
issue: 2174
last_updated: 2026-08-19
title: "Equipment load error: double-space kind breaks factor-map matching"
summary: "normalize_kind() lowercased+stripped but never collapsed internal whitespace, and load_factors_map() built factor-side keys without even calling it — a double space in equipment_data.csv's equipment_class (vs. equipment_factors.csv's single space) silently failed the backoffice MODULE_PER_YEAR upload's kind→data_entry_type lookup. Also fixes the process_emissions gas-category resolver found while triaging the same `make bootstrap-years` log (root cause unrelated to #2174, bundled here on request)."
---

## Problem

Issue [#2174]: uploading equipment data from the backoffice errored for rows
classed `Other furniture equipment` / `Other IT / Telecom equipment`, even
though the reporter confirmed those categories exist in the factors.

## Root cause

`backend/INPUT_DATA/equipment_data.csv`'s `equipment_class` column carries a
stray double space before "equipment" (`Other furniture  equipment`,
`Other IT / telecom  equipment`), while
`backend/INPUT_DATA/equipment_factors.csv` has the clean single-space form.

The backoffice MODULE_PER_YEAR CSV upload (equipment has no
`data_entry_type_id` category column, so it infers the type) calls
`lookup_data_entry_type_by_kind` → `normalize_kind` (`app/seed/seed_helper.py`)
against keys built by `load_factors_map`. `normalize_kind` did
`.lower().strip()`, which trims edges but leaves internal double spaces
intact, so the row's kind never matched the factor's key — the row fails with
"no matching factor found in factors map" (surfaced as the backoffice error).
Separately, `load_factors_map` built its keys with bare `.lower()`, not even
calling `normalize_kind` — the two sides of the match weren't using the same
normalization to begin with.

Traced via `make bootstrap-years` producing `/tmp/log-error`, which surfaced
two other, unrelated factor-CSV issues in the same run:

1. **process_emissions gas-category resolution** (fixed here, see below) —
   `_PROCESS_GAS_MAP` (`app/modules/process_emissions/emissions.py`) only
   had 4 short-code keys (`co2`, `ch4`, `n2o`, `refrigerants`) matching the
   _data-entry_ CSV vocabulary (`processemissions_data.csv`'s `category` is
   `"CO2"`, `"CH4"`, …). It never covered the _factor_ CSV's descriptive
   names (`processemissions_factors.csv`'s `category` is
   `"Carbon dioxide (CO2)"`, `"Hydrofluorocarbons (HFCs)"`, …) — every one
   of the 66 process-emissions factor rows failed
   `get_factor_emission_type_id` and was dropped.
2. **`purchases_common_factors.csv` has 81 rows with no `purchase_category`
   and 136 rows with no `ef_kg_co2eq_per_currency`** — currently skipped
   with a log line per row (a silent fallback per the guardrails). Left
   out of this PR; needs a decision (repair the CSV, delete the rows, or
   make `bootstrap-years` fail hard) — tracked separately, not fixed here.

## Fix

`backend/app/seed/seed_helper.py`:

- `normalize_kind`: collapse internal whitespace too —
  `" ".join(kind.lower().split())`.
- `load_factors_map`: build factor-side keys through `normalize_kind` instead
  of a bare `.lower()`, so both sides of every match go through the same
  normalization.

`backend/app/modules/process_emissions/emissions.py`:

- `_PROCESS_GAS_MAP` gains the 9 descriptive factor-CSV category strings
  alongside the existing short codes. The taxonomy (`EmissionType`) has only
  4 process-emissions leaves (`co2`/`ch4`/`n2o`/`refrigerants`) — no bucket
  per fluorinated gas — so SF6, NF3, HFCs, perfluorinated compounds,
  fluorinated ethers, and perfluoropolyethers all roll into
  `process_emissions__refrigerants`. Finer-grained buckets are a taxonomy
  call for #2091, not made here.

## Test

`backend/tests/unit/seed/test_seed_helper.py`:

- `test_normalize_kind_collapses_internal_whitespace`
- `test_lookup_data_entry_type_by_kind_ignores_double_space` — reproduces the
  production path (double-space row kind vs. single-space factor key),
  fails without the fix.

`backend/tests/unit/modules/test_process_emissions_emissions.py` (new):

- short-code and descriptive-category resolution, all 6 fluorinated gases
  mapping to `refrigerants`, unknown category → `None`.
