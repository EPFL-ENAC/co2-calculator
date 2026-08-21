---
status: delivered
issue: 2183
last_updated: 2026-08-20
summary: "A research-facilities create/update 500'd on dev with a bare 'Failed to create data entry'. Root cause: #2050 Track J1's fail-hard raise for a formula that can't produce a value, hitting a factor (CLIMACT-GE, factor_id=37756) whose kg_co2eq_sum was never backfilled because its unit is closed and has no CarbonReport for the year. Three fixes: surface the ValueError as 422 with its real message, name the facility when kg_co2eq_sum is the specific gap, and make the computed backfill write an explicit 0.0 for a closed unit instead of raising and leaving the factor permanently incomplete."
---

# Research facilities 500 on a closed unit's factor (#2183)

## Symptom

```
POST /v1/carbon-reports/15490/modules/research-facilities/research-facilities -> 500
{"detail":"Failed to create data entry"}
```

Backend log had the real reason, never returned to the client:

```
ValueError: data_entry_id=9237, emission_type='research_facilities__facilities',
factor_id=37756: The formula for 'research_facilities__facilities' could not
produce a value. Null inputs on the entry: none. Factor keys available:
['total_use', 'use_unit'].
```

## Root cause chain

1. **Immediate cause**: `ResearchFacilitiesCommonModuleHandler`'s formula
   (`app/modules/research_facilities/handlers.py`) needs `total_use`,
   `use_unit`, and `kg_co2eq_sum` from the factor's `values`. Factor
   `37756` (researchfacility_id `1012`, CLIMACT-GE) only had
   `{"total_use": 118750.0, "use_unit": "CHF"}` — `kg_co2eq_sum` was
   absent, not `0`.
2. **Why it 500'd instead of silently zeroing (old behavior)**: #2050
   Track J1 removed the silent-fallback that used to drop a leaf whose
   formula returned `None`, and made `prepare_create` raise instead — by
   design, so an incomplete number doesn't ship as if it were complete.
   The route's generic `except Exception` then flattened that into a bare
   500, discarding the specific message.
3. **Why `kg_co2eq_sum` was never populated**: it's optional at factor
   creation, meant to be filled by
   `ResearchFacilitiesCommonFactorUpdateProvider.compute_factor_values`
   (`app/services/data_ingestion/computed_providers/research_facilities_common.py`),
   which sums the unit's `CarbonReport.stats` for the year. CLIMACT-GE is
   a **closed unit** (`Unit.is_active=False`) — it has no `CarbonReport`
   for the requested year and never will, so the provider's own
   `CarbonReport not found` guard raised on every recompute attempt
   instead of ever writing a value. The gap was permanent, not
   transient — a normal recompute could never fix it.

## Fixes

1. **`CarbonReportModuleWorkflow.create`/`update`** — added a dedicated
   `except ValueError` clause ahead of the generic `except Exception`,
   returning `422` with `detail=str(e)` instead of a bare 500. Mirrors
   the existing `IntegrityError`-specific handling in `create()` and the
   `ValueError` handling already used in `delete()`.
2. **`_research_facilities_formula`** (common variant) — raises a
   specific `ValueError` naming the facility when `kg_co2eq_sum` is the
   missing key, instead of returning `None` and falling through to
   `_apply_formula`'s generic message. Mirrors the animal variant's
   existing per-source raise.
3. **`ResearchFacilitiesCommonFactorUpdateProvider.compute_factor_values`**
   — when the `CarbonReport` lookup misses **and** the unit is closed
   (`is_active=False`), returns `{"kg_co2eq_sum": 0.0}` instead of
   raising. A closed unit has stopped reporting; no report for the year
   is the expected case, and 0 is the correct total, not an unknown one.
   An **active** unit with no report for the year still raises — that
   case is a real data gap, not a closed-unit fact.

Combined: the client now gets a 422 naming the exact problem, and for the
closed-unit case specifically, the next factor recompute self-heals —
`kg_co2eq_sum` gets written as `0.0` and the entry create succeeds.

## Not in scope here

- The one-off backfill of factor `37756` itself (and any other
  already-affected closed-unit factors) — self-heals on the next
  `ResearchFacilitiesCommonFactorUpdateProvider` recompute run for
  data_entry_type=research_facilities, year matching the affected
  factors; no manual data fix needed once this ships.
- Whether other computed-factor providers have the same
  active-vs-closed-unit gap — not audited, worth a follow-up sweep if
  this pattern recurs elsewhere.

## Verification

- `uv run pytest tests/unit` — 2199 passed.
- New regression tests: `test_create_value_error_from_emission_service_returns_422`,
  `test_update_value_error_from_emission_service_returns_422`,
  `tests/unit/modules/test_research_facilities_common_formula.py`,
  `test_closed_unit_with_no_carbon_report_returns_zero_sum`.
- `make lint`, `make type-check` — clean.
