# Bot Review TODOs: PR #1732

## Source Branch: `refactor/reduce-data-entry-emission-type-reach`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR centralizes emissions taxonomy and data-entry-to-emission-type resolution into a unified `app.modules.emissions` domain, and refactors feature modules to expose dedicated emission-resolution helpers while removing `__init__.py` side-effect imports.

**Changes:**

- Introduces a new emissions domain API (`taxonomy.py`, `units.py`, `registry.py`, and `app.modules.emissions` re-exports) and removes the legacy `data_entry_emission_type_map.py`.
- Moves per-module emission-type resolution into module-scoped `emissions.py` files (buildings, professional travel, purchases, process emissions, headcount, external cloud/AI, research facilities).
- Updates services/repositories/tests to import emissions types and helpers from the new centralized API and registry.

### Reviewed changes

Copilot reviewed 83 out of 83 changed files in this pull request and generated no comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                            | Description                                                                                                                    |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| backend/app/api/v1/carbon_report_module.py                                                      | Switches additional-breakdown classification import to `app.modules.emissions`.                                                |
| backend/app/core/constants.py                                                                   | Replaces `TOTAL_MODULE_TYPES` dynamic computation with a fixed value.                                                          |
| backend/app/models/data_entry_emission.py                                                       | Removes embedded emissions taxonomy and imports `EmissionType` from the new emissions domain.                                  |
| backend/app/models/module_type.py                                                               | Updates `EmissionType` import to the new centralized emissions API.                                                            |
| backend/app/modules/**init**.py                                                                 | Removes re-export/side-effect imports; keeps package marker only.                                                              |
| backend/app/modules/buildings/**init**.py                                                       | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/buildings/emissions.py                                                      | Adds buildings-specific runtime emission-type resolution helpers.                                                              |
| backend/app/modules/buildings/schemas.py                                                        | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/equipment/**init**.py                                                       | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/external_cloud_and_ai/**init**.py                                           | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/external_cloud_and_ai/emissions.py                                          | Adds external cloud/AI runtime emission-type resolution helpers.                                                               |
| backend/app/modules/emissions/**init**.py                                                       | Introduces public emissions domain API re-exports (`EmissionType`, traversal, units helpers, etc.).                            |
| backend/app/modules/emissions/registry.py                                                       | Adds centralized registry for resolving emission types per `DataEntryTypeEnum`.                                                |
| backend/app/modules/emissions/taxonomy.py                                                       | Adds the canonical emissions taxonomy (enum + parent/child + scope/category derivation).                                       |
| backend/app/modules/emissions/units.py                                                          | Adds standardized units and “additional breakdown” semantics.                                                                  |
| backend/app/modules/headcount/**init**.py                                                       | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/headcount/emissions.py                                                      | Adds headcount-factor runtime emission-type resolution helper.                                                                 |
| backend/app/modules/headcount/schemas.py                                                        | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/process_emissions/**init**.py                                               | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/process_emissions/emissions.py                                              | Adds process-emissions runtime emission-type resolution helper.                                                                |
| backend/app/modules/professional_travel/**init**.py                                             | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/professional_travel/emissions.py                                            | Adds plane/train cabin-class runtime emission-type resolution helpers.                                                         |
| backend/app/modules/professional_travel/schemas.py                                              | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/purchase/**init**.py                                                        | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/purchase/emissions.py                                                       | Adds purchases runtime emission-type resolution helper (centralized purchases).                                                |
| backend/app/modules/purchase/schemas.py                                                         | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/research_facilities/**init**.py                                             | Removes schema import side effects; keeps package marker only.                                                                 |
| backend/app/modules/research_facilities/animals_schemas.py                                      | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/research_facilities/common_schemas.py                                       | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/modules/research_facilities/emissions.py                                            | Adds research-facilities runtime emission-type resolution helpers.                                                             |
| backend/app/repositories/carbon_report_module_repo.py                                           | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/repositories/data_entry_emission_repo.py                                            | Updates rollup ID import to `app.modules.emissions.registry`; updates `EmissionType` import.                                   |
| backend/app/repositories/data_entry_repo.py                                                     | Switches rollup/registry constants import to `app.modules.emissions.registry`.                                                 |
| backend/app/repositories/factor_repo.py                                                         | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/schemas/factor.py                                                                   | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/seed/random_generator/seed_data_entries.py                                          | Replaces `app.modules` re-exports with direct schema imports and updates `EmissionType` import.                                |
| backend/app/seed/random_generator/seed_emission_factors.py                                      | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/seed/random_generator/seed_factors.py                                               | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/seed/seed_generic_factors.py                                                        | Keeps explicit schema imports for handler registration; simplifies comments.                                                   |
| backend/app/seed/seed_helper.py                                                                 | Switches factor emission-type resolution import to `app.modules.emissions.registry`.                                           |
| backend/app/services/carbon_report_module_service.py                                            | Updates taxonomy helper imports (`get_children`, `get_subtree_leaves`, etc.) to new emissions API.                             |
| backend/app/services/data_entry_emission_service.py                                             | Switches registry + units helpers to `app.modules.emissions` / `app.modules.emissions.registry`; removes legacy utils imports. |
| backend/app/services/data_ingestion/computed_providers/research_facilities_animal.py            | Updates imports to new emissions API.                                                                                          |
| backend/app/services/data_ingestion/computed_providers/research_facilities_common.py            | Updates imports to new emissions API.                                                                                          |
| backend/app/services/factor_service.py                                                          | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/app/utils/data_entry_emission_type_map.py                                               | Removes legacy mapping/resolution module.                                                                                      |
| backend/app/utils/emission_category.py                                                          | Switches to new emissions API for additional-breakdown and emission-type ID resolution helpers.                                |
| backend/app/utils/it_breakdown.py                                                               | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/conftest.py                                                                       | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/modules/equipment_electric_consumption/test_sort.py                   | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/modules/plane/test_csv_import_smoke.py                                | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/modules/plane/test_persistence_invariant.py                           | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/modules/train/test_sort_uses_location.py                              | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_buildings_csv_pg.py                      | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_csv_ingest_matrix_pg.py                  | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_factor_lifecycle_pg.py                   | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_factor_replace_semantics_pg.py           | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_headcount_pg.py                          | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_kg_co2eq_override_async_path_pg.py       | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_plan_310b_emission_change_pg.py          | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_plan_310b_factor_reupload_endpoint_pg.py | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_recalc_source_uniformity_pg.py           | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_sql_factor_resolution_pg.py              | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_stats_json_pg.py                         | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py                 | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py                 | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/integration/services/data_ingestion/test_travel_pg.py                             | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/models/test_data_entry_emission_taxonomy.py                                  | Adds unit tests for taxonomy-derived parent/child/scope/category behavior and registry resolution.                             |
| backend/tests/unit/modules/test_buildings_schemas.py                                            | Updates `EmissionType` import to the new emissions API and doc references to new resolver name.                                |
| backend/tests/unit/modules/test_equipment_schemas.py                                            | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/repositories/test_data_entry_emission_repo.py                                | Updates `EmissionType` import and additional-breakdown helper import to the new emissions API.                                 |
| backend/tests/unit/repositories/test_data_entry_repo.py                                         | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/repositories/test_data_entry_repo_trips_map.py                               | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/repositories/test_factor_repo.py                                             | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/services/data_ingestion/test_professional_travel_api_provider.py             | Switches `resolve_emission_types` import to `app.modules.emissions.registry`.                                                  |
| backend/tests/unit/services/data_ingestion/test_research_facilities_common_factor_update.py     | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/services/test_data_entry_emission_service.py                                 | Updates `EmissionType` and registry constant imports to the new emissions API/registry.                                        |
| backend/tests/unit/services/test_recompute_stats_research_facilities.py                         | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/utils/test_building_rooms_resolver.py                                        | Switches building room resolver reference to module-scoped resolver and updates imports/docs.                                  |
| backend/tests/unit/utils/test_emission_category.py                                              | Updates imports to use new emissions API for constants/utilities.                                                              |
| backend/tests/unit/utils/test_it_breakdown.py                                                   | Updates `EmissionType` import to the new emissions API.                                                                        |
| backend/tests/unit/utils/test_plane_cabin_class.py                                              | Switches resolver reference to module-scoped resolver and updates imports/docs.                                                |
| backend/tests/unit/utils/test_plane_calculation.py                                              | Updates `EmissionType` import to the new emissions API.                                                                        |

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 106 out of 107 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 130 out of 132 changed files in this pull request and generated no new comments.

---

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 130 out of 132 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 132 out of 134 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 138 out of 140 changed files in this pull request and generated no new comments.

---

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 141 out of 143 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 143 out of 145 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 143 out of 145 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 151 out of 153 changed files in this pull request and generated no new comments.

---

### Summary Feedback (copilot-pull-request-reviewer)

## Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.

### Summary Feedback (copilot-pull-request-reviewer)

## Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.

### Summary Feedback (copilot-pull-request-reviewer)

## Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.

### File: `backend/app/modules/emissions/taxonomy.py` (Line 215) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/703)

### File: `backend/app/modules/emissions/taxonomy.py` (Line 233) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/704)

### File: `backend/app/modules/emissions/taxonomy.py` (Line null) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/705)

### File: `backend/app/seed/seed_generic_factors.py` (Line 13) — github-advanced-security[bot]

## CodeQL / Unused import

Import of 'schemas' is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/706)

### File: `backend/app/seed/seed_generic_factors.py` (Line 14) — github-advanced-security[bot]

## CodeQL / Unused import

Import of '\_pe_schemas' is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/707)

### File: `backend/app/seed/seed_generic_factors.py` (Line 15) — github-advanced-security[bot]

## CodeQL / Unused import

Import of '\_purchase_schemas' is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/708)

### File: `backend/app/generate_emission_taxonomy_ts.py` (Line 18) — github-advanced-security[bot]

## CodeQL / Non-iterable used in for loop

This for-loop may attempt to iterate over a [non-iterable instance](1) of class [type](2).

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/709)

### File: `backend/tests/unit/tasks/test_poller_dispatch.py` (Line 16) — github-advanced-security[bot]

## CodeQL / Module is imported with 'import' and 'import from'

Module 'app.tasks.\_poller' is imported with both 'import' and 'import from'.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/714)
