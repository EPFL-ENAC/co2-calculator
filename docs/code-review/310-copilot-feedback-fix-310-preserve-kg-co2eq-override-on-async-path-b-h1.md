# Bot Review TODOs: PR #1076

Source Branch: `fix/310-kg-co2eq-async-path`
PR Title: fix(310): preserve kg_co2eq override on async path [B-H1]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR fixes a bulk-ingestion regression under `BULK_PATH_PURE_ASYNC=True` where per-row `kg_co2eq` overrides were dropped before async emission recalculation, causing emissions to be recomputed from formulas instead of preserving the override. It introduces a reserved `DataEntry.data` carrier key for the override and makes `prepare_create` honor it when no function-arg override is provided.

**Changes:**

- Add `KG_CO2EQ_OVERRIDE_KEY="__kg_co2eq_override__"` and make `DataEntryEmissionService.prepare_create()` fall back to that persisted carrier (while keeping function-arg precedence).
- Persist the override carrier during ingestion in both the CSV provider and the professional travel API provider so async recalculation preserves the override.
- Add/extend unit + integration tests to pin carrier persistence and end-to-end async-path behavior in Postgres.

### Reviewed changes

Copilot reviewed 6 out of 6 changed files in this pull request and generated 5 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                      | Description                                                                                                      |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| backend/app/services/data_entry_emission_service.py                                       | Adds reserved override carrier constant and `prepare_create` fallback logic; strips carrier from `meta` context. |
| backend/app/services/data_ingestion/base_csv_provider.py                                  | Persists override into `DataEntry.data` under the reserved carrier key during `_process_row`.                    |
| backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py     | Persists travel override under the reserved carrier key so async recalc preserves Tableau-corrected CO2.         |
| backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py       | Adds assertions that the override carrier is persisted for parseable values.                                     |
| backend/tests/unit/services/data_ingestion/test_base_csv_provider.py                      | Adds assertions that the override carrier is persisted for CSV rows with `kg_co2eq`.                             |
| backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py | New Postgres integration coverage for async-path override preservation and precedence rules.                     |

</details>

---

### File: `backend/app/services/data_ingestion/base_csv_provider.py` (Line 1004) — Copilot

## The `_process_row` docstring earlier in this method states that `kg_co2eq_override` is carried out-of-band so it never lands in `DataEntry.data`, but this hunk now persists the override under `KG_CO2EQ_OVERRIDE_KEY`. Please update the docstring/commentary to reflect the new reserved-key carrier behavior so future readers don’t get misled about where overrides are stored.

### File: `backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py` (Line 508) — Copilot

## These tests hardcode the reserved key string `"__kg_co2eq_override__"`. Since the key is now a public constant (`KG_CO2EQ_OVERRIDE_KEY`) used by providers/services, consider importing and using the constant here to avoid test drift if the reserved key ever changes.

### File: `backend/tests/unit/services/data_ingestion/test_base_csv_provider.py` (Line 752) — Copilot

## These assertions hardcode `"__kg_co2eq_override__"`. Prefer importing `KG_CO2EQ_OVERRIDE_KEY` and using it here (and in other override-related tests) to keep test expectations aligned with the production reserved-key constant.

### File: `backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py` (Line 116) — Copilot

## This integration test seeds and asserts against the reserved override carrier using the literal key `"__kg_co2eq_override__"`. Using the production constant (`KG_CO2EQ_OVERRIDE_KEY`) would reduce the chance of this test becoming stale if the reserved key changes.

### File: `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py` (Line 431) — Copilot

## `kg_co2eq = item.get("kg_co2eq") or item.get("OUT_CO2_CORRECTED")` (and the similar `distance_km` line) treats `0`/`0.0` as falsy and will incorrectly fall back to the `OUT_*` key (or `None`) even when `kg_co2eq`/`distance_km` is a valid zero value. Use an explicit `is not None` check (or a helper) so zero overrides/distances are preserved correctly.
