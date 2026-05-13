# Bot Review TODOs: PR #1187

## Source Branch: `feat/430-internationalisation-classes`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR introduces i18n support for factor-sourced option labels by shifting from storing user-facing free-text labels in the DB to using i18n translation keys (and related frontend translation logic). It also removes purchase-label fallback resolution at query time and expands frontend i18n dictionaries for purchase/equipment/buildings/external cloud options.

**Changes:**

- Add `translation_key` plumbing to taxonomy nodes and frontend taxonomy typing/usage to translate factor-sourced option labels via i18n.
- Add new i18n dictionaries for purchase factors and equipment factors, plus additional keys for buildings room types and external cloud service types.
- Remove legacy purchase label fallback logic (`purchase_institutional_description`) in backend schemas, seeding, and stats endpoints.

### Reviewed changes

Copilot reviewed 21 out of 21 changed files in this pull request and generated 8 comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                                 | Description                                                                                             |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| frontend/src/stores/factors.ts                                                       | Adds `kindLabelMapBySubmodule` to the factors store state.                                              |
| frontend/src/api/factors.ts                                                          | Adds a client helper to fetch a kind→label map from the backend.                                        |
| frontend/src/i18n/purchase_factors.ts                                                | Adds a large purchase-factor translation dictionary (FR/EN).                                            |
| frontend/src/i18n/equipment_factors.ts                                               | Adds an equipment-factor translation dictionary (FR/EN).                                                |
| frontend/src/i18n/external_cloud.ts                                                  | Adds i18n keys for external cloud service types.                                                        |
| frontend/src/i18n/buildings.ts                                                       | Adds i18n keys for combustion types and buildings room types.                                           |
| frontend/src/constant/modules.ts                                                     | Extends `TaxonomyNode` typing with optional `translation_key`.                                          |
| frontend/src/constant/moduleConfig.ts                                                | Adds `optionLabelPrefix` for translating dynamic factor-sourced options.                                |
| frontend/src/constant/module-config/external-cloud-and-ai.ts                         | Configures `optionLabelPrefix` for external cloud `service_type`.                                       |
| frontend/src/constant/module-config/buildings.ts                                     | Switches room type labels to i18n keys (`optionLabelsAreKeys`).                                         |
| frontend/src/components/organisms/module/ModuleTable.vue                             | Adds taxonomy-aware label resolution and `optionLabelPrefix` rendering in table cells.                  |
| frontend/src/components/organisms/module/ModuleInlineSelect.vue                      | Uses taxonomy `translation_key` when available to label class options.                                  |
| frontend/src/components/organisms/module/ModuleForm.vue                              | Uses `optionLabelPrefix` and taxonomy `translation_key` when building select options.                   |
| backend/app/models/taxonomy.py                                                       | Adds `translation_key` field to `TaxonomyNode`.                                                         |
| backend/app/services/module_handler_service.py                                       | Populates taxonomy nodes with `translation_key` from factor values.                                     |
| backend/app/modules/purchase/schemas.py                                              | Removes purchase description fields and adds `translation_key` to purchase factor handler value fields. |
| backend/app/seed/random_generator/seed_data_entries.py                               | Stops seeding `purchase_institutional_description` on purchase entries.                                 |
| backend/app/repositories/data_entry_emission_repo.py                                 | Removes purchase label-resolution fallback from top-class breakdown.                                    |
| backend/app/api/v1/carbon_report_module.py                                           | Removes purchase “label_field” support for top-class breakdown endpoint.                                |
| backend/app/api/v1/carbon_report_module_stats.py                                     | Removes purchase “label_field” use in IT breakdown.                                                     |
| backend/alembic/versions/2026_05_13_1515-30c096280772_remove_purchase_description.py | Adds a migration purportedly related to purchase description removal.                                   |

</details>

---

### File: `frontend/src/stores/factors.ts` (Line 23) — Copilot

## `kindLabelMapBySubmodule` is introduced and returned from the store, but it is never populated/updated anywhere in this store (no fetch method writes to it). Either remove it and the related UI fallback usage, or implement a fetch (and import the API call) to actually populate it so consumers don’t rely on an always-empty map.

### File: `frontend/src/api/factors.ts` (Line 23) — Copilot

`getKindLabelMap()` calls `GET /factors/{submodule}/kind-label-map`, but there is no corresponding backend route in `backend/app/api/v1/factors.py` (only `class-subclass-map` and `classes/{kind}/values`). As-is, any caller will get a 404. Either implement the endpoint server-side or remove this client helper to avoid dead/incorrect API surface.

---

### File: `frontend/src/components/organisms/module/ModuleTable.vue` (Line 877) — Copilot

This comment says the factor-store kind-label map is “populated by fetchClassOptions”, but `useFactorsStore.fetchClassOptions()` currently only derives options from the subclass map and never sets `kindLabelMapBySubmodule`. Either update the store to actually populate this map (and ensure it’s kept fresh), or remove this fallback logic/comment to avoid misleading future changes.

---

### File: `frontend/src/components/organisms/module/ModuleTable.vue` (Line 965) — Copilot

When `optionLabelPrefix` is set, this always returns `$t(prefix + value.toLowerCase())` without checking `$te()`. If the translation key is missing, vue-i18n will typically display the raw key, which is user-facing. Consider checking `$te()` first and falling back to the original label/value when the key doesn’t exist.

---

### File: `frontend/src/components/organisms/module/ModuleForm.vue` (Line 437) — Copilot

When `optionLabelPrefix` is set, the form rewrites dynamic option labels to `$t(prefix + value.toLowerCase())` without checking `$te()`. If a translation key is missing, this will surface the raw i18n key in the dropdown. Consider guarding with `$te()` and falling back to `o.label`/`o.value` when the translation is not available.

---

### File: `frontend/src/i18n/equipment_factors.ts` (Line 214) — Copilot

Typo in the i18n key name: `equipment_factor_lab_freezer_frigde` ("frigde") should be `equipment_factor_lab_freezer_fridge` for consistency/readability. If any DB `translation_key` values or code references use the corrected spelling, the current typo will cause missing translations.

---

### File: `backend/app/modules/purchase/schemas.py` (Line 467) — Copilot

## `purchase_common_value_fields` adds `translation_key`, but none of the Purchase common factor DTOs (Create/Update/Response) declare a `translation_key` field. This means the factor API responses won’t surface the key and API-driven create/update flows can’t round-trip it cleanly. Add `translation_key` (likely Optional[str]) to the relevant DTOs so managers can view/edit it via the API/UI, and keep the schema aligned with the handler’s stored values.

### File: `backend/alembic/versions/2026_05_13_1515-30c096280772_remove_purchase_description.py` (Line 73) — Copilot

## This migration drops several critical indexes/constraints (`uq_factor_identity*`, `uq_*_active`, and `ix_locations_keywords`) but does not drop/alter any purchase-description-related column (and these indexes are unrelated to the purchase description removal). Applying it would remove factor-identity uniqueness guarantees and can negatively impact ingestion concurrency and location search performance. This migration should be removed or rewritten to only include the intended schema change (likely none, since the removed field lived in JSON).

---

## Action Items

### Critical: logic, security, correctness

- [ ] **backend/alembic/versions/2026_05_13_1515-30c096280772_remove_purchase_description.py** — The `upgrade()` function drops `uq_factor_identity`, `uq_factor_identity_no_year`, `uq_aggregation_active`, `uq_emission_recalc_active`, and `ix_locations_keywords` — none of which are related to purchase description removal (that field lived in JSON, requiring no schema change). Applying this migration would silently remove factor uniqueness guarantees and degrade location GIN search. Fix: empty both `upgrade()` and `downgrade()` bodies (or delete the migration entirely); there is no intended schema change to carry out.

- [ ] **frontend/src/stores/factors.ts + frontend/src/api/factors.ts + frontend/src/components/organisms/module/ModuleTable.vue:874** — `kindLabelMapBySubmodule` is declared and exported from the Pinia store but is never written to by any store action; `getKindLabelMap()` in the API client targets `/{submodule}/kind-label-map`, which has no corresponding route in `backend/app/api/v1/factors.py` (404 at runtime). The fallback in `taxonomyKindLabelMap` (ModuleTable.vue:875) will always receive an empty map, and the comment on line 874 claiming it is "populated by fetchClassOptions" is wrong (`fetchClassOptions` never writes it). Fix: either (a) implement the `/{data_entry_type}/kind-label-map` backend route, add a store action that calls `getKindLabelMap()` and populates `kindLabelMapBySubmodule`, and correct the comment — or (b) remove `getKindLabelMap`, `kindLabelMapBySubmodule`, and the fallback block in `taxonomyKindLabelMap` if the taxonomy override path is sufficient on its own.

- [ ] **backend/app/modules/purchase/schemas.py:439–467** — `purchase_common_value_fields` lists `translation_key`, but none of `PurchaseCommonFactorCreate` (line 442), `PurchaseCommonFactorUpdate` (line 456), or `PurchaseCommonFactorResponse` (line 463) declare the field. Factor API responses will omit `translation_key` and create/update payloads cannot round-trip it. Fix: add `translation_key: Optional[str] = None` to all three DTOs.

- [ ] **frontend/src/components/organisms/module/ModuleTable.vue:965 + frontend/src/components/organisms/module/ModuleForm.vue:435** — Both sites call `$t(prefix + value.toLowerCase())` when `optionLabelPrefix` is set, with no `$te()` guard. A missing translation key causes vue-i18n to render the raw key string to the user. Fix: guard both with `$te(prefix + value.toLowerCase())` and fall back to `val` (table cell) / `o.label` (form option) when the key is absent.

### Maintainability / refactoring

- [ ] **frontend/src/i18n/equipment_factors.ts:214** — The key `equipment_factor_lab_freezer_frigde` is a typo ("frigde" → "fridge"). Fix: before renaming, verify whether factor seed data in the DB stores the misspelled string as the `translation_key` value; if so, rename the dictionary key and update the seed/DB values together to keep them in sync.
