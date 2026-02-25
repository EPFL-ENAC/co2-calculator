# Plan: PR #524 Review Fixes — Buildings Module v2

Address all review comments from **guilbep** on PR #524 (`173-task-module-buildings-v2`).

---

## Summary of Changes Required

| # | File | Why | How |
|---|------|-----|-----|
| 1 | `backend/app/api/v1/carbon_report_module.py` | Archibus helpers don't belong here | Extract to own file |
| 2 | `backend/app/api/v1/carbon_report_module.py` | `get_archibus_rooms` missing FastAPI response type | Add `response_model` or `-> list[...]` |
| 3 | `backend/app/services/data_ingestion/csv_providers/building_room_csv_provider.py` | Manual column constants duplicate what `BaseCSVProvider` already provides | Use parent helpers |
| 4 | `backend/app/services/data_ingestion/csv_providers/building_room_csv_provider.py` | `_process_row` manually maps fields one-by-one instead of using a simple dict merge | Simplify to `{**row, **room.model_dump()}` |
| 5 | `backend/app/utils/emission_breakdown.py` | Large structural refactor (`ChartBar` dataclass, `BARS` list) is unrelated to the buildings task and should not be in this PR | Move to separate branch |
| 6 | `frontend/src/stores/factors.ts` | Archibus room state was added to the factors store where it doesn't belong | Create dedicated `useArchibusRoomStore` |
| 7 | `frontend/src/stores/factors.py` | Building-specific `unit_id` caching added to the generic factors store | Revert to pre-PR state |
| 8 | `frontend/src/composables/useEquipmentClassOptions.ts` | `classOptionId`/`subClassOptionId` fields were added to `FieldConfig` unnecessarily | Roll back to original interface |
| 9 | `frontend/src/components/organisms/module/ModuleInlineSelect.vue` | `?? undefined` added to `classFieldId`/`subClassFieldId` with no clear reason | Revert or document the reason |
| 10 | `frontend/src/components/organisms/module/ModuleForm.vue` | Dynamic options lookup uses `inp.id` in addition to `inp.optionsId` — inconsistent | Use only `optionsId` |
| 11 | `frontend/src/components/organisms/module/ModuleForm.vue` | Loading state check uses `inp.id === kindFieldId` in addition to `optionsId` | Keep only `optionsId` check |
| 12 | `frontend/src/components/organisms/module/ModuleForm.vue` | Archibus auto-fill watcher placed inline in `ModuleForm.vue` | Extract to `useArchibusRoomDynamicOptions.ts` |
| 13 | `frontend/src/components/organisms/module/ModuleForm.vue` | `dynamicOptions[i.id]` used in `init()` radio-group default — unclear why | Investigate and remove or justify |
| 14 | `frontend/src/api/factors.ts` | `unit_id` parameter added to `getSubclassMap` with no clear justification | Investigate and remove or document |
| 15 | `frontend/src/constant/module-config/buildings.ts` | `room_type` option values (`'Office'`, `'Miscels'`, etc.) are used as factor lookup keys and must never be translated, but there is no comment warning about this | Add a comment referencing the issue |

---

## Detailed Changes

### 1 & 2 — Extract `/archibus-rooms` to its own router file

**File:** `backend/app/api/v1/carbon_report_module.py`

**Review comments:**
> Line 48: *"@BenBotros I'd move `_unit_institutional_ids` and all related `/archibus-rooms` to its own file in `api/v1`"*
> Line 99: *"use fastapi response type"*

**Why:**
> `_unit_institutional_ids` and all `/archibus-rooms` logic was added directly to the existing `carbon_report_module` router file. This mixes unrelated concerns — the module router handles data entries, while Archibus is a building-specific lookup service.
> Additionally, the endpoint has no return type annotation, losing FastAPI's automatic response validation and OpenAPI docs.

**How:**
1. Create `backend/app/api/v1/archibus.py` with its own `APIRouter`.
2. Move `_unit_institutional_ids()` helper and `get_archibus_rooms()` into that file.
3. Add a proper return type: `-> list[dict]` or a typed `ArchibusRoomResponse` Pydantic model, and set `response_model=list[ArchibusRoomResponse]` on the route.
4. Register the new router in `backend/app/api/v1/__init__.py` (or wherever routers are registered).
5. Remove the moved code from `carbon_report_module.py`.

---

### 3 — Use `BaseCSVProvider` column helpers in `BuildingRoomCSVProvider`

**File:** `backend/app/services/data_ingestion/csv_providers/building_room_csv_provider.py` (lines 19–28)

**Review comment:**
> Line 20: *"@BenBotros Have a look at the base_csv_provider (that you use!) why not using `_get_expected_columns_from_handlers` / `_get_required_columns_from_handler` to retrieve the REQuired_columns and OPTIONAL columns?"*

**Why:**
> The three module-level constants (`BUILDING_ROOM_CSV_REQUIRED_COLUMNS`, `BUILDING_ROOM_CSV_OPTIONAL_COLUMNS`, `BUILDING_ROOM_CSV_ALL_COLUMNS`) duplicate functionality that already exists in `BaseCSVProvider`:
> ```python
> # Already in base_csv_provider.py
> def _get_expected_columns_from_handlers(handlers):  # all fields from handler.create_dto
> def _get_required_columns_from_handler(handler):    # only required fields
> ```
> Keeping custom constants means the column list can drift out of sync with the handler DTO.

**How:**
1. Remove `BUILDING_ROOM_CSV_REQUIRED_COLUMNS`, `BUILDING_ROOM_CSV_OPTIONAL_COLUMNS`, and `BUILDING_ROOM_CSV_ALL_COLUMNS` constants.
2. In `_setup_and_validate()`, replace the manual constants with calls to the base class helpers:
   ```python
   expected_columns = _get_expected_columns_from_handlers([handler])
   required_columns = _get_required_columns_from_handler(handler)
   ```
3. Pass `expected_columns` and `required_columns` to `_validate_csv_headers()`.

---

### 4 — Simplify `_process_row` row transformation

**File:** `backend/app/services/data_ingestion/csv_providers/building_room_csv_provider.py` (lines 271–308)

**Review comment:**
> Line 275: *"EUH @BenBotros ? `transformed_row={**row, **room.model_dump()}` ???"*

**Why:**
> The `_process_row` method manually copies each field from the `ArchibusRoom` model into `transformed_row` with explicit `if room.field is not None` checks. The reviewer suggests this is unnecessarily verbose and should simply be:
> ```python
> transformed_row = {**row, **room.model_dump()}
> ```
> This merges the CSV row with all Archibus room fields at once, letting Archibus data override CSV data where both are present.

**How:**
1. Replace the manual field-by-field construction of `transformed_row` (the ~40-line block) with:
   ```python
   transformed_row = {**row, **room.model_dump(exclude_none=True)}
   ```
2. Verify that `room.model_dump()` keys match the handler DTO field names (they should, as the `ArchibusRoom` model uses the same naming).
3. Keep the `note` field handling if it is not part of `room.model_dump()`.

---

### 5 — Move `emission_breakdown.py` refactor to a separate branch

**File:** `backend/app/utils/emission_breakdown.py`

**Review comment:**
> Line 18: *"@BenBotros keep the code! but in another branch! nothing to do in this PR"*

**Why:**
> The PR introduced a large structural refactor replacing the old dict-based `MODULE_TYPE_TO_CATEGORY` / `_MODULE_EMISSION_CATEGORY` pattern with a new `ChartBar` dataclass and `BARS` list. While this is a legitimate improvement, it is unrelated to the buildings task scope and makes the PR significantly harder to review.

**How:**
1. Create a new branch (e.g. `refactor/emission-breakdown-chart-bars`) from `main`.
2. Cherry-pick or re-apply the `emission_breakdown.py` structural refactor onto that branch.
3. In this PR, revert `emission_breakdown.py` to the pre-PR version and apply **only** the minimal changes needed for buildings:
   - Add `(3, EmissionTypeEnum.energy): "Buildings energy consumption"` to `_MODULE_EMISSION_CATEGORY`
   - Replace `(3, EmissionTypeEnum.grey_energy): "Buildings room"` → `(3, EmissionTypeEnum.combustion): "Energy combustion"`
   - Update `MODULE_BREAKDOWN_ORDER` and `CATEGORY_CHART_KEYS` accordingly.

---

### 6 & 7 — Create `useArchibusRoomStore` and revert `useFactorsStore`

**File:** `frontend/src/stores/factors.ts`

**Review comments:**
> Line 37: *"@ create an another Store for archibusRoom,"*
> Line 59: *"@BenBotros comme avant!"*
> Line 73: *"@BenBotros c'est quoi ?"*

**Why (line 37 — new store):**
> The Archibus room lookup state (buildings list, rooms list, caching by unit) was added into `useFactorsStore`. Factors and Archibus rooms are completely different concerns — the factors store should only manage emission factor trees. Mixing them violates single-responsibility and makes the store harder to test.

**Why (line 59 — revert):**
> The PR added `workspaceStore`, `subclassMapUnitId`, and the `SUBMODULE_BUILDINGS_TYPES.Building`-specific `requestedUnitId` logic into the generic `ensureTree()` function. This makes a generic utility module-aware. The reviewer wants it reverted to the pre-PR state ("comme avant" = as it was before).

**Why (line 73 — questioning `getOptionsAtPath`):**
> The `getOptionsAtPath(submodule, path)` function was added as part of the refactor. The reviewer questions its necessity ("c'est quoi ?" = what is this?). If it only exists to serve the Archibus-specific dropdown path, it should live in the new dedicated store.

**How:**
1. **Revert `frontend/src/stores/factors.ts`** to its pre-PR state:
   - Restore `ensureSubclassOptionMap()` function name and its original `Record<string, Option[]>` return type.
   - Remove `workspaceStore` import and usage.
   - Remove `subclassMapUnitId` reactive state.
   - Remove `SUBMODULE_BUILDINGS_TYPES` import.
   - Remove `requestedUnitId` / `cachedUnitId` logic from `ensureTree` / `ensureSubclassOptionMap`.
   - Remove `getOptionsAtPath()` function (if it was only needed for Archibus).
2. **Create `frontend/src/stores/archibus.ts`** as a new Pinia store:
   ```ts
   export const useArchibusRoomStore = defineStore('archibus', () => {
     // state: buildings by unitId, rooms by (unitId, buildingName)
     // actions: fetchBuildings(unitId), fetchRooms(unitId, buildingName)
     // uses src/api/archibus.ts internally
     // caches results keyed by unitId
   })
   ```

---

### 8 — Roll back `useEquipmentClassOptions` `FieldConfig` interface

**File:** `frontend/src/composables/useEquipmentClassOptions.ts`

**Review comments:**
> Line 8: *"Roll back comme avant?"*
> Line 148: *"@BenBotros mais non?"*

**Why (line 8 — roll back):**
> The PR added `classOptionId` and `subClassOptionId` to `FieldConfig` as separate properties from `classFieldId` and `subClassFieldId`. This created a confusing split where `classFieldId` tracks the actual entity field (used to read the value) and `classOptionId` tracks the key used to store options in `dynamicOptions`. The reviewer asks to roll this back to the simpler original design ("comme avant" = as it was before).

**Why (line 148 — "mais non?"):**
> Inside the `watch(submoduleType, ...)` handler the code was changed from clearing `dynamicOptions[classFieldId]` to clearing `dynamicOptions[classOptionId]`. The reviewer disagrees ("mais non?" = but no?) — if options are keyed by `classFieldId`, clearing by a separate `classOptionId` key is wrong.

**How:**
1. Remove `classOptionId` and `subClassOptionId` from `FieldConfig` interface.
2. Restore the `watch` handlers to clear/read `dynamicOptions` using `classFieldId` / `subClassFieldId` directly (as before the PR).
3. Update all call sites (`ModuleForm.vue`, `ModuleInlineSelect.vue`) to remove the `classOptionId`/`subClassOptionId` params.

---

### 9 — Revert `ModuleInlineSelect.vue` `?? undefined` change

**File:** `frontend/src/components/organisms/module/ModuleInlineSelect.vue` (line 79)

**Review comments:**
> Line 79: *"@BenBotros roll back comme avant?"*
> Line 79: *"peut-être que y'a une raison pour le undefined?"* (maybe there's a reason for the undefined?)

**Why:**
> The PR changed `classFieldId: kindFieldId.value` to `classFieldId: kindFieldId.value ?? undefined`. The reviewer first asks to revert ("comme avant"), then asks if there's a deliberate reason for it. The `?? undefined` coercion is a no-op when `kindFieldId.value` is already `string | null` — passing `null` vs `undefined` to an optional string param is effectively the same. This change adds noise without clear intent.

**How:**
1. Revert to `classFieldId: kindFieldId.value` and `subClassFieldId: subkindFieldId.value`.
2. If the TypeScript types require `string | undefined` (not `string | null`), fix the computed return type of `kindFieldId` instead of adding `?? undefined` at every call site.

---

### 10 & 11 — Use only `optionsId` in `ModuleForm.vue` dynamic option lookup

**File:** `frontend/src/components/organisms/module/ModuleForm.vue` (lines 190, 415)

**Review comments:**
> Line 415: *"on garde que optionsId et on ne se base pas sur le id"* (keep only `optionsId`, do not base ourselves on the `id`)
> Line 190: *"Keep optionsId everywhere?"*

**Why (line 415 — `filteredOptionsMap`):**
> The PR changed dynamic options lookup from `dynamicOptions[inp?.optionsId ?? '']` to `dynamicOptions[inp?.id ?? ''] ?? dynamicOptions[inp?.optionsId ?? '']`. Using `inp.id` as a fallback creates ambiguity — if a field has no `optionsId` set, it will accidentally match options keyed by the field's raw `id`. The convention is that `optionsId` is the sole key for dynamic options.

**Why (line 190 — loading state):**
> Similarly, `:loading` was changed to check both `inp.id === kindFieldId` and `inp.optionsId === 'kind'`. The reviewer asks to keep `optionsId` as the only signal — consistent with the convention above.

**How:**
1. In `filteredOptionsMap` computed, revert to: `const dynamicOpts = dynamicOptions[inp?.optionsId ?? ''];`
2. In the `:loading` binding, revert to: `inp.optionsId === 'kind' ? loadingClasses : inp.optionsId === 'subkind' ? loadingSubclasses : false`

---

### 12 & 13 — Extract Archibus auto-fill watcher from `ModuleForm.vue`

**File:** `frontend/src/components/organisms/module/ModuleForm.vue` (lines 526–563, 605)

**Review comments:**
> Line 533: *"@BenBotros ??"* (questioning the whole inline watcher block)
> Line 537 (two comments): *"@BenBotros move in a `useArchibusRoomDynamicOptions.ts` or something like that"* and *"put that inside a if module === building"*
> Line 512: *"@BenBotros ?"* (questioning `classOptionId: kindFieldId.value ?? undefined` passed to `useEquipmentClassOptions`)
> Line 605: *"@BenBotros why ? not sure"* (questioning `dynamicOptions[i.id]` used in radio-group init)

**Why (lines 533/537 — extract to composable):**
> The Archibus room auto-fill watcher (watching `form['room_name']` and populating kWh fields from the Archibus API) is placed inline in `ModuleForm.vue`. This is buildings-specific logic in a generic component. The reviewer asks to move it to a dedicated composable (`useArchibusRoomDynamicOptions.ts`) and guard it with `if module === building`.

**Why (line 512 — `classOptionId` param):**
> `classOptionId: kindFieldId.value ?? undefined` was added as a new param to `useEquipmentClassOptions`. The reviewer questions this — once `classOptionId`/`subClassOptionId` are removed from `FieldConfig` (Change 8), this argument disappears too.

**Why (line 605 — `dynamicOptions[i.id]` in `init()`):**
> In the `init()` function's radio-group default-value block, `dynamicOptions[i.id]` was added as a fallback before `i.options`. The reviewer questions why — radio-group defaults should come from static config or `optionsId`-keyed dynamic options, not by field `id`.

**How:**
1. Create `frontend/src/composables/useArchibusRoomDynamicOptions.ts`:
   - Accepts `form` ref, `moduleType`, `submoduleType`, `unitId`.
   - Contains the `isBuildingsRoomSubmodule` computed.
   - Contains the `watch(() => form['room_name'], ...)` watcher that calls `getArchibusRooms` and auto-fills fields.
   - Returns nothing (side-effect composable).
2. In `ModuleForm.vue`, import and call `useArchibusRoomDynamicOptions(form, moduleType, submoduleType, unitId)` — wrapped in a guard so it only runs when `moduleType === MODULES.Buildings`.
3. Remove the `isBuildingsRoomSubmodule` computed and the inline watcher from `ModuleForm.vue`.
4. In `init()`, revert to using only `i.options` (not `dynamicOptions[i.id]`) for radio-group defaults.

---

### 14 — Investigate `unit_id` in `getSubclassMap`

**File:** `frontend/src/api/factors.ts` (line 14)

**Review comment:**
> Line 14: *"Find out why! doesn't make sense to me"*

**Why:**
> The `unit_id` parameter was added to the `getSubclassMap` API call and forwarded to the backend `/factors/{submodule_type_id}/class-subclass-map` endpoint. For the buildings module, the class-subclass map (buildings → rooms) is unit-specific. However, the factors endpoint is generic — it is not clear whether it actually filters by `unit_id`, or whether this concern belongs entirely in the dedicated Archibus endpoint instead.

**How:**
1. Check whether `GET /factors/{submodule_type_id}/class-subclass-map?unit_id=X` on the backend actually filters by unit. If not, the `unit_id` param is a no-op.
2. If the buildings dropdown (building_name / room_name) should be sourced from the Archibus endpoint (not from the factors class-subclass map), then:
   - Remove `unitId` from `getSubclassMap`.
   - Route buildings dropdowns through `useArchibusRoomStore` instead.
   - This aligns with Copilot's separate comment that `room_name` using `optionsId: 'subkind'` (factors tree) is wrong — rooms should come from Archibus, not the factors map.
3. If `unit_id` filtering via factors is intentional, document it with a comment.

---

### 15 — Add comment to `buildings.ts` about non-translatable `room_type` values

**File:** `frontend/src/constant/module-config/buildings.ts` (line 47)

**Review comment:**
> Line 47: *"@BenBotros Add a comment linking to the issue saying that we should not translate this"*

**Why:**
> The `room_type` field's option values (`'Office'`, `'Miscels'`, `'Laboratories'`, `'Archives'`, `'Libraries'`, `'Auditoriums'`) are the exact string keys used by the backend to look up emission factors. If these values are ever translated or changed, factor lookups will silently return `null` and no CO₂ will be calculated. The reviewer asks for an explicit warning comment with a link to the issue.

**How:**
```ts
// IMPORTANT: these option values are used as emission-factor lookup keys on the backend.
// They MUST NOT be translated or changed without updating the corresponding seed data.
// See: https://github.com/EPFL-ENAC/co2-calculator/issues/173
options: [
  { value: '', label: '-' },
  { value: 'Office', label: 'Office' },
  ...
```

---

## Execution Order

The changes are mostly independent but the following ordering avoids conflicts:

1. **Step 5** (revert `emission_breakdown.py`) — do first to reduce diff size and clarify scope.
2. **Steps 1 & 2** (extract Archibus router) — backend-only, no frontend dependency.
3. **Steps 3 & 4** (simplify CSV provider) — backend-only.
4. **Step 14** (investigate `unit_id`) — determines whether Steps 6/7 need adjustment before proceeding.
5. **Steps 6 & 7** (revert `factors.ts`, create `archibus.ts` store) — foundation for frontend changes.
6. **Steps 8 & 9** (revert `useEquipmentClassOptions`, `ModuleInlineSelect`) — depend on Step 6 being clear first.
7. **Steps 10 & 11** (fix `ModuleForm.vue` options lookup) — can be done alongside Step 6.
8. **Steps 12 & 13** (extract Archibus watcher composable) — done after Steps 6/7.
9. **Step 15** (add comment) — trivial, do last.
