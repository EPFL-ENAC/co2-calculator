# Bot Review TODOs: PR #988

## Source Branch: `fix/data-entry-data-mutation`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR prevents derived/computed values (e.g., `kg_co2eq`, `primary_factor`, travel/building enrichments) from being persisted into the source-of-truth `data_entries.data` JSON column by moving enrichment out-of-band on read paths and by routing CSV/API `kg_co2eq` overrides through an explicit parameter rather than embedding them into `DataEntry.data`.

**Changes:**

- Read path: `ModuleHandler.to_response(...)` now accepts `enriched_data` so `get_submodule_data` can enrich responses without mutating ORM-backed `DataEntry.data` (plus detach/expunge defense-in-depth).
- Ingestion path: CSV/API providers extract `kg_co2eq` overrides out-of-band and pass them transiently to `DataEntryEmissionService.prepare_create(kg_co2eq_override=...)`; `prepare_create` no longer reads `kg_co2eq` from `data_entry.data`.
- Fixes a latent response-shape bug in buildings energy-combustion (`primary_factor` is flat; no nested `values`), and adds regression tests/fixtures to lock in the non-persistence guarantees.

### Reviewed changes

Copilot reviewed 20 out of 20 changed files in this pull request and generated 5 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                  | Description                                                                                                                                                           |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| docs/implementation-plans/fix-data-entry-data-mutation.md                             | Implementation plan documenting the two leak sources and the chosen mitigation approach.                                                                              |
| backend/app/schemas/data_entry.py                                                     | Extends `ModuleHandler.to_response` protocol to accept `enriched_data` for non-persisted enrichment.                                                                  |
| backend/app/repositories/data_entry_repo.py                                           | Builds `enriched_data` dict instead of mutating `DataEntry.data`, and adds `_detach()` expunge defense in `get_submodule_data` (plus TODO notes for other read APIs). |
| backend/app/services/data_entry_emission_service.py                                   | Introduces `kg_co2eq_override` parameter; removes fallback reading `kg_co2eq` from `data_entry.data`; deletes stale strip workaround in `upsert_by_data_entry`.       |
| backend/app/services/data_ingestion/base_csv_provider.py                              | Extracts `kg_co2eq` from raw CSV row out-of-band, carries parallel override list through batching, and forwards overrides to `prepare_create`.                        |
| backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py | Mirrors the CSV override carrier approach for API ingestion (parallel override list + per-entry forwarding).                                                          |
| backend/app/services/data_ingestion/csv_providers/local_seed.py                       | Updates overridden method signatures to match the new CSV provider tuple/flow shape.                                                                                  |
| backend/app/modules/buildings/schemas.py                                              | Updates handlers to accept `enriched_data`; fixes energy-combustion `primary_factor` flat-dict access for `name`/`unit`.                                              |
| backend/app/modules/equipment/schemas.py                                              | Uses `enriched_data` (when provided) for response construction, including `primary_factor` reads.                                                                     |
| backend/app/modules/external_cloud_and_ai/schemas.py                                  | Updates response building to use `enriched_data` and factor-derived fields consistently.                                                                              |
| backend/app/modules/headcount/schemas.py                                              | Updates handlers to accept `enriched_data` for response building.                                                                                                     |
| backend/app/modules/process_emissions/schemas.py                                      | Uses `enriched_data` and `primary_factor` (from enrichment) for category/subcategory response fields.                                                                 |
| backend/app/modules/professional_travel/schemas.py                                    | Updates handler to accept `enriched_data` for response building (travel listing enrichment).                                                                          |
| backend/app/modules/purchase/schemas.py                                               | Updates handlers to accept `enriched_data` and uses it consistently for response fields.                                                                              |
| backend/app/modules/research_facilities/animals_schemas.py                            | Updates handler to accept `enriched_data` for response building.                                                                                                      |
| backend/app/modules/research_facilities/common_schemas.py                             | Updates handler to accept `enriched_data` for response building.                                                                                                      |
| backend/tests/unit/repositories/test_data_entry_repo.py                               | Adds regression test ensuring `get_submodule_data` does not dirty/persist computed keys into `DataEntry.data`.                                                        |
| backend/tests/unit/services/test_data_entry_emission_service.py                       | Adds/updates unit tests for `kg_co2eq_override` behavior and removes obsolete strip-workaround tests.                                                                 |
| backend/tests/unit/services/data_ingestion/test_base_csv_provider.py                  | Adds regression tests verifying `kg_co2eq` is extracted out-of-band and correctly routed through batch processing.                                                    |
| backend/tests/integration/data_ingestion/fixtures/regression_kg_co2eq_plane.csv       | Adds a “dumb” plane CSV fixture used by ingestion regression tests.                                                                                                   |

</details>

---

### File: `backend/app/repositories/data_entry_repo.py` (Line 61) — github-advanced-security[bot]

## CodeQL / Empty except

'except' clause does nothing but pass and there is no explanatory comment.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/641)

### File: `backend/app/schemas/data_entry.py` (Line 144) — github-advanced-security[bot]

## CodeQL / Statement has no effect

This statement has no effect.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/640)

### File: `backend/app/services/data_ingestion/base_csv_provider.py` (Line 982) — Copilot

## `_process_row` currently always returns `None` for the `factor` tuple element (`return data_entry, None, None, kg_co2eq_override`) even when a matching factor was resolved/populated earlier. This makes `process_csv_in_batches` count every successful row as `rows_without_factors`, and the job summary/status message will be incorrect. Consider returning the resolved factor (or an explicit boolean) in that third position so stats remain accurate.

### File: `backend/app/services/data_ingestion/base_csv_provider.py` (Line 826) — Copilot

When `kg_co2eq` is present but not a valid float, the code logs a debug message and silently ignores the override. This can hide bad input and lead to unexpected formula-based emissions instead of failing the row. Consider recording a row error / skipping the row (or at least logging a warning and surfacing it in `stats['row_errors']`) when a non-empty `kg_co2eq` value cannot be parsed.

---

### File: `backend/app/repositories/data_entry_repo.py` (Line 56) — Copilot

## `_detach` uses an inline import (`from sqlalchemy.exc import InvalidRequestError`). This repository generally keeps imports at the top of the module; moving this import to the top-level keeps import structure consistent and avoids repeatedly executing imports on hot paths (e.g., list endpoints calling `_detach` per row).

### File: `backend/app/repositories/data_entry_repo.py` (Line 204) — Copilot

## New TODOs were added to `get_list` about auditing callers before expunging/detaching. Please avoid landing TODOs in mainline code; consider creating/linking a tracked issue and referencing it here (or completing the audit within this PR) so the follow-up work is not lost.

### File: `backend/app/repositories/data_entry_repo.py` (Line 233) — Copilot

New TODOs were added to `list_by_data_entry_type_and_year` about auditing whether expunging is safe. Please replace TODOs with a tracked issue reference (or complete the audit in this PR) to prevent unfinished work from lingering indefinitely.

---

## Action Items

### Maintainability / refactoring

- [ ] **`backend/app/repositories/data_entry_repo.py` — `_detach`** — Two style nits on the same helper: (1) CodeQL #641 flags `except InvalidRequestError: pass` as an empty handler with no inline explanation, and (2) the `from sqlalchemy.exc import InvalidRequestError` is mid-function while the rest of the module imports at the top. Fix: hoist the import to the top of the file alongside other `sqlalchemy` imports, and add a one-line comment on the `pass` (e.g. `# Already detached or session-state edge case; nothing to do.`) so the silent-swallow intent is readable at the call site, not just in the docstring.
- [ ] **`backend/app/schemas/data_entry.py:144`** — CodeQL #640 flags the bare `...` after the docstring on `to_response` as a statement with no effect. The docstring on its own is already a valid Protocol/abstract body. Fix: remove the `...` line so the function is just `def to_response(...) -> ...: """docstring"""`. Mechanical and removes the alert.
- [ ] **`backend/app/services/data_ingestion/base_csv_provider.py:823` and `professional_travel_api_provider.py` (kg_co2eq parse failure)** — Copilot's symptom is real: a `kg_co2eq` cell that parses as garbage today logs at DEBUG and silently produces formula-based emissions instead of the override the user expected. Copilot's _suggested fix_ (record a row error / skip the row) is too aggressive — the rest of the row is valid and should still create a `DataEntry`; only the override should be dropped. Fix: bump `logger.debug` → `logger.warning` in both providers so the parse failure is visible in normal log levels without changing flow. The symmetric API-provider site (added in the latest commit) needs the same bump.

### Skipped after verification

- **`base_csv_provider.py:982` — Copilot says `_process_row` always returns `None` in the factor tuple position, breaking `rows_with_factors` accounting.** Verified at parent commit `b39fec7e`: the third position was `None` _before_ this PR (`return data_entry, None, None`). My change only added a 4th element, so this is a pre-existing stats-counter bug, not a regression introduced here. Should be a separate ticket if the counter matters; out of scope for this PR.
- **`data_entry_repo.py:204` and `:233` — Copilot wants the new `# TODO:` comments replaced with tracked-issue references.** Skip — these were explicitly requested by the user during design ("only expunge get_submodule_data, TODO comments on the other ones") to keep the audit deferred without losing the reminder. Converting them to a separate issue would contradict the agreed scope.
