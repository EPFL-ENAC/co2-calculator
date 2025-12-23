# Implementation Plan: Refactor Pagination & Lazy Loading for Equipment Module

## Overview

Implement lazy loading with per-submodule pagination and sorting. Load only summary totals on initial page load, then fetch individual submodule data when users expand collapsible sections.

## Requirements

1. Modify existing endpoint to return totals only when `preview_limit=0`
2. Load only totals on page load, fetch submodule data on expansion
3. Per-submodule state: independent sort/filter/pagination
4. Default limit: 20, changing sort/pagination resets to page 1
5. After mutations, refetch only affected submodule
6. No test coverage needed

---

## Implementation Steps

### Backend (3 files)

#### 1. Repository Layer

**File**: [backend/app/repositories/equipment_repo.py:119-188](backend/app/repositories/equipment_repo.py#L119-L188)

- Add `sort_by` and `sort_order` parameters to `get_equipment_with_emissions()`
- Create field mapping dict: `{"id": Equipment.id, "name": Equipment.name, "kg_co2eq": EquipmentEmission.kg_co2eq, ...}`
- Apply dynamic `ORDER BY` based on sort parameters

#### 2. Service Layer

**File**: [backend/app/services/equipment_service.py:35-263](backend/app/services/equipment_service.py#L35-L263)

**In `get_module_data()`**:

- When `preview_limit=0`, skip item fetching, return empty items arrays with summaries only

**In `get_submodule_data()`**:

- Add `sort_by` and `sort_order` parameters
- Pass to repository layer

#### 3. API Layer

**File**: [backend/app/api/v1/modules.py:22-143](backend/app/api/v1/modules.py#L22-L143)

- Update `preview_limit` Query validator: `ge=0` (allow 0)
- Pass `sort_by` and `sort_order` from submodule endpoint to service layer

---

### Frontend (4 files)

#### 4. Store

**File**: [frontend/src/stores/modules.ts](frontend/src/stores/modules.ts)

**State**: Add `loadedSubmodules: Record<string, boolean>`

**New method**: `getModuleTotals()` - calls endpoint with `preview_limit=0`

**Update `getSubmoduleData()`**:

- Add `sortBy` and `sortOrder` parameters
- Build query string with sort params
- Mark as loaded: `state.loadedSubmodules[submoduleId] = true`

**New helper**: `findSubmoduleForEquipment(equipmentId)` - searches loaded data to find which submodule contains equipment

**Update mutations** (`postItem`, `patchItem`, `deleteItem`):

- Find affected submodule using helper
- Refetch only that submodule with current pagination/sort state
- Also call `getModuleTotals()` to refresh counts

**Exports**: Add `getModuleTotals`

#### 5. ModulePage

**File**: [frontend/src/pages/app/ModulePage.vue:68-86](frontend/src/pages/app/ModulePage.vue#L68-L86)

- Replace `moduleStore.getModuleData()` with `moduleStore.getModuleTotals()`

#### 6. SubModuleSection

**File**: [frontend/src/components/organisms/module/SubModuleSection.vue](frontend/src/components/organisms/module/SubModuleSection.vue)

**Template**:

- Add `@before-show="onExpand"` to q-expansion-item
- Pass to ModuleTable: `:loading="submoduleLoading"`, `:pagination-data="paginationData"`, `:submodule-id="submodule.id"`
- Add handlers: `@page-change="onPageChange"`, `@sort-change="onSortChange"`

**Script**:

- Add computed: `submoduleData`, `submoduleLoading`, `submoduleError`, `submoduleCount`, `paginationData` (all read from store state)
- Add methods:
  - `onExpand()`: Check `loadedSubmodules[id]`, fetch if not loaded
  - `onPageChange(page)`: Call `getSubmoduleData()` with new page
  - `onSortChange(sortBy, sortOrder)`: Call `getSubmoduleData()` with sort, reset to page 1
- Update `rows` computed: Use `submoduleData.value?.items`

#### 7. ModuleTable

**File**: [frontend/src/components/organisms/module/ModuleTable.vue](frontend/src/components/organisms/module/ModuleTable.vue)

**Props**: Add `submoduleId?: string`, `paginationData?: { page, limit, total, sortBy?, sortOrder? }`

**Emits**: Add `page-change`, `sort-change`

**Pagination**:

- Remove local `pagination` ref
- Replace with computed that uses `props.paginationData` (server-side) or fallback to local state

**Template**: Add `@request="onRequest"` to q-table

**Handler**: `onRequest()` - emit `page-change` or `sort-change` based on user action

---

## Data Flow

**Initial Load**: `ModulePage → getModuleTotals() → GET /modules?preview_limit=0 → Display collapsed headers with counts`

**Expand**: `onExpand() → Check loaded → getSubmoduleData(page=1, limit=20) → GET /modules/.../sub_scientific?page=1&limit=20 → Display table`

**Paginate**: `Click next → emit('page-change', 2) → getSubmoduleData(page=2) → Table updates`

**Sort**: `Click column → emit('sort-change', 'name', 'asc') → getSubmoduleData(page=1, sortBy='name') → Table sorted`

**Mutate**: `postItem() → POST → findSubmodule → refetch that submodule + totals → Table updates`

---

## Critical Files (7 total)

### Backend

1. [backend/app/repositories/equipment_repo.py](backend/app/repositories/equipment_repo.py)
2. [backend/app/services/equipment_service.py](backend/app/services/equipment_service.py)
3. [backend/app/api/v1/modules.py](backend/app/api/v1/modules.py)

### Frontend

4. [frontend/src/stores/modules.ts](frontend/src/stores/modules.ts)
5. [frontend/src/pages/app/ModulePage.vue](frontend/src/pages/app/ModulePage.vue)
6. [frontend/src/components/organisms/module/SubModuleSection.vue](frontend/src/components/organisms/module/SubModuleSection.vue)
7. [frontend/src/components/organisms/module/ModuleTable.vue](frontend/src/components/organisms/module/ModuleTable.vue)

---

## Edge Cases

- Re-expand: Check `loadedSubmodules`, skip if already loaded
- Errors: Display in table, retry on collapse/re-expand
- Loading: Show spinner during fetch
- Empty submodule: Show "No data", form available
- Sort persistence: State maintained across collapse/expand

## Success Criteria

✅ Initial load fetches only totals
✅ Lazy load on first expansion only
✅ Independent pagination per submodule
✅ Sorting resets to page 1
✅ Mutations refetch only affected submodule + totals
✅ Loading/error states displayed
