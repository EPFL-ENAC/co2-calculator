---
status: in-progress
issue: 2771
last_updated: 2026-10-29
summary: "Reference tests for the kg-CO2-eq formulas: every worked example in the back-office data-description doc runs through the real handler computations and DataEntryEmissionService._apply_formula and must match the domain owner's expected value. Rows where doc and code disagree are pinned as strict xfails and listed for the domain owner; AI and common purchases stay out until the doc and code agree on a formula."
---

# 2771 — CO₂ formula reference tests

## Source

The "test calculation" boxes of
[`data-description.md`](https://github.com/EPFL-ENAC/co2-calculator-back-office-doc/blob/main/docs/data-description.md)
(back-office doc, `main`, read 2026-10-29). The domain owner owns the
examples; the tests copy them row for row.

## Harness

- **Path under test:** `resolve_emission_types` → `handler.resolve_computations`
  → `DataEntryEmissionService._apply_formula`, summed over the entry's
  leaves. That is `prepare_create` minus its DB steps.
- **`pre_compute` is skipped.** Its outputs (`distance_km`, `country_code`,
  `room_surface_square_meter`) go into `ctx` straight from the doc.
  `haul_category` is left out: it only picks the factor row, so the plane
  handler logs its "unknown" warning and the kg is unchanged. The distance helpers (+95 km, ×1.2, integer rounding, haul
  bands, train country) are already pinned by
  `tests/unit/utils/test_distance_geography.py`.
- **Factor values are hardcoded** from the `INPUT_DATA` CSVs, each row
  citing its file. `INPUT_DATA` is not in git, so CI cannot read it.
- **Exchange rates** are patched to the doc's fixed rates (CHF 1.0672,
  USD 0.8849 → EUR). No ECB call.
- **Tolerance:** `pytest.approx(expected, abs=0.01)` — the doc gives two
  decimals. A row outside it is a strict xfail naming the gap, never a
  looser tolerance.
- **Override rows are not repeated** per module: the kg override is one
  generic branch, covered by
  `test_prepare_create_with_kg_co2eq_override_short_circuits_formula` and
  `test_csv_override_with_multiple_factors_creates_single_row`.

## Files

All under `backend/tests/unit/modules/`, one per module, examples
parametrized with the doc's row id:

| File                                             | Submodules               |
| ------------------------------------------------ | ------------------------ |
| `reference_examples.py`                          | shared helper, no tests  |
| `test_process_emissions_reference_examples.py`   | process emissions        |
| `test_buildings_reference_examples.py`           | energy combustion, rooms |
| `test_equipment_reference_examples.py`           | equipment                |
| `test_purchase_reference_examples.py`            | centralized purchases    |
| `test_external_cloud_reference_examples.py`      | clouds                   |
| `test_professional_travel_reference_examples.py` | planes, trains           |

## Findings (for the domain owner)

The point of these tests is to tell a wrong implementation from a doc
slip. Either side can be wrong: the back-office and dev teams agree
which, then that side is fixed and the tests follow. Ranked by impact
on published totals.

### Doc and code disagree on the formula

| #   | Where            | Doc                                                                                                              | Code                                                                                 | Impact if the doc is right                                                    |
| --- | ---------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| 1   | external_ai      | `fte × requests × 235 × ef`, ef in kg per request                                                                | `… × 230 × ef / 1000`; the variable is `factor_g`, so the kg column is read as grams | code is 1000× too low                                                         |
| 2   | purchases_common | rows 1, 2, 3, 5 equal the code's kg ÷ 1173 exactly: ÷ 1000 is tonnes, ÷ 1.173 is unexplained (a price deflator?) | `spent_eur × ef` in kg, no ÷ 1.173                                                   | code is 17.3 % too high                                                       |
| 3   | equipment        | 47 weeks a year                                                                                                  | `WEEKS_PER_YEAR` = 52                                                                | code is 10.6 % too high                                                       |
| 4   | external_ai      | 235 days = 47 weeks × 5                                                                                          | 230 days = 46 × 5                                                                    | code is 2 % too low; the code uses two week counts (52, 46), the doc one (47) |
| 5   | external_ai      | the examples give numeric requests/day, the spec buckets                                                         | buckets count as 3, 12.5, 60 and 100 requests                                        | the bucket values need sign-off                                               |
| 6   | planes           | the spec allows `cabin_class` first                                                                              | `PLANE_CABIN_MAP` has business and economy, no first factor rows                     | first-class rows are rejected at upload (loud, not silent)                    |

On #1: the `/ 1000` dates from the grams column `factor_gCO2eq`
(`d0452a37b`). #535 (`e7c36a007`, 2026-03-11) renamed it
`ef_kg_co2eq_per_request` and kept the `/ 1000`. The factor CSV is not
in git, so whether its values were converted at the rename is unknown;
the factor file's owner settles it. v2.12.5 (2026-09-22) has the same
values.

### Doc slips — the code follows the doc's own spec

| Row                     | Doc                                          | Code / CSV                                                         | In the tests             |
| ----------------------- | -------------------------------------------- | ------------------------------------------------------------------ | ------------------------ |
| plane GVA-LHR           | 1024.57                                      | the row's own formula gives 1024.53                                | strict xfail             |
| plane LHR-JFK           | 8968.97                                      | the row's own formula gives 8968.95                                | strict xfail             |
| train Genève–London     | 90.78, which is 976.1 km, not the note's 980 | 980 × 1.2 × 0.0775 (RoW) = 91.14                                   | strict xfail             |
| equipment EQ007 Servers | 500 W / 100 W                                | `equipment_factors.csv`: 160 W / 30 W (or the CSV is stale)        | strict xfail             |
| trains, all rows        | `cabin_class` blank                          | the spec marks it mandatory, the code requires `first` or `second` | rows use `second`        |
| purchases_common row 4  | 0.088                                        | the row's own note gives 80.05 kg                                  | not tested               |
| planes, trains          | unrounded km                                 | one-trip distance rounded to integer km                            | not tested (pre_compute) |

### Not checked by these tests

- **Factor selection** — factor values are hardcoded, so a wrong lookup
  (haul band, country fallback, purchase code) still passes. Distances and
  haul bands are pinned by `tests/unit/utils/test_distance_geography.py`.
- **headcount, research facilities, embodied energy, planner** — no
  examples in the doc yet.

## Done when

- The domain owner has answered the gaps above and the xfails are gone.
- A deliberate code change fails the matching tests — done 2026-10-29,
  both mutations at once gave exactly these 6 failures. Factor values are
  hardcoded, so the mutation goes in the code:
  - drop `multiplier_key="rfi_adjustment"` in the plane handler → the 4
    passing plane rows fail;
  - skip `conversion_factor` in `_compute_kwh_emission` → `CSV-0-32` and
    `SOS1-0-32` fail (the electric rooms use 1.0 and cannot catch it).
