# Service Manager — Audit Logs UI & API

> Unified Implementation Plan · `system/logs` · Vue 3 + Quasar + FastAPI

---

## 1. Context & Scope

### 1.1 What Exists Today

**Backend (done):**

| Component                 | File                             | Status                                                                                                                                                                                                     |
| ------------------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AuditDocument` model     | `app/models/audit.py`            | ✅ Table `audit_documents` with entity_type, entity_id, version, data_snapshot, data_diff, change_type, changed_by, changed_at, handler_id, handled_ids, ip_address, route_path, route_payload, hash chain |
| `AuditDocumentRepository` | `app/repositories/audit_repo.py` | ✅ `create`, `get`, `list`, `bulk_create`                                                                                                                                                                  |
| `AuditDocumentService`    | `app/services/audit_service.py`  | ✅ `create_version`, `bulk_create_versions`, `get_current_version`, `list_versions`, `rollback_to_version`, `verify_hash_chain`                                                                            |
| `AuditChangeTypeEnum`     | `app/models/audit.py`            | ✅ CREATE, READ, UPDATE, DELETE, ROLLBACK, TRANSFER                                                                                                                                                        |
| Request context utils     | `app/utils/request_context.py`   | ✅ `extract_ip_address`, `extract_route_payload`, `extract_route_info`                                                                                                                                     |
| Audit helpers             | `app/utils/audit_helpers.py`     | ✅ `extract_handled_ids`, `extract_handled_ids_from_list`                                                                                                                                                  |
| Auth audit logging        | `app/api/v1/auth.py`             | ✅ Login, logout, token refresh, failure events logged via `_log_auth_audit_event()`                                                                                                                       |

**Backend (missing):**

| Component                           | Notes                                             |
| ----------------------------------- | ------------------------------------------------- |
| Audit query API endpoints           | No route to query/filter/export `audit_documents` |
| Audit Pydantic schemas              | No response models for returning audit records    |
| Pagination/filtering on audit table | Repository only has basic `list(offset, limit)`   |

**Frontend (done):**

| Component                  | File                         | Status                                                                                  |
| -------------------------- | ---------------------------- | --------------------------------------------------------------------------------------- |
| Route `system/logs`        | `src/router/routes.ts`       | ✅ Exists, loads `LogsPage.vue`, guarded by `requirePermission('system.users', 'edit')` |
| `SYSTEM_LOGS` nav constant | `src/constant/navigation.ts` | ✅ `routeName: 'system-logs'`, `icon: 'o_list_alt'`                                     |
| i18n labels                | `src/i18n/admin.ts`          | ✅ "Logs" + description in en/fr                                                        |

**Frontend (missing):**

| Component           | Notes                                                         |
| ------------------- | ------------------------------------------------------------- |
| `LogsPage.vue`      | Placeholder only — displays "Placeholder: Add Grafana iFrame" |
| All UI components   | No filter bar, table, stat cards, detail view, or export      |
| API service layer   | No `src/api/audit.ts`                                         |
| Store or composable | No state management for audit log queries                     |

### 1.2 AUDIT vs APPLICATION Logs

| Type                     | Storage                    | Purpose                                                        | Owner                   |
| ------------------------ | -------------------------- | -------------------------------------------------------------- | ----------------------- |
| **AUDIT** (this feature) | `audit_documents` DB table | "Who did what when?" — track data modifications, logins, reads | Us                      |
| **APPLICATION**          | Kubernetes pod logs        | CPU/RAM, errors, API connectivity                              | DSI (Grafana/Loki/OTel) |

This plan covers **AUDIT logs only**. The `system/logs` route will expose the `audit_documents` table to service managers.

---

## 2. Route & Navigation

### 2.1 Route (extend existing)

The route already exists in `src/router/routes.ts`. Extend its `meta`:

```typescript
{
  path: 'system/logs',
  name: SYSTEM_NAV.SYSTEM_LOGS.routeName,           // 'system-logs'
  component: () => import('pages/system/LogsPage.vue'),
  beforeEnter: requirePermission('system.users', 'edit'),
  meta: {
    requiresAuth: true,
    note: 'System Admin - Audit logs viewer',
    breadcrumb: false,
    isSystem: true,
    title: 'Logs',
    icon: 'assignment',
    description: 'View, search, and export audit logs and user activity history for security auditing and troubleshooting.',
  },
},
```

### 2.2 SYSTEM_NAV constant (already exists, no change needed)

```typescript
SYSTEM_LOGS: {
  routeName: 'system-logs',
  description: 'system-logs-description',
  icon: 'o_list_alt',
},
```

---

## 3. Backend — API Endpoints

All endpoints live in a new file: `app/api/v1/audit.py`.

### 3.1 Paginated audit log query

```
GET /api/v1/audit/activity
  ?user_id=123                          # optional — filter by actor
  ?entity_type=DataEntry                # optional
  ?entity_id=456                        # optional — history of specific entity
  ?action=CREATE                        # optional — CREATE|READ|UPDATE|DELETE|ROLLBACK|TRANSFER
  ?date_from=2024-10-01T00:00:00Z       # optional ISO 8601
  ?date_to=2024-10-08T23:59:59Z         # optional ISO 8601
  ?search=sophie                        # optional — free-text on changed_by, change_reason, entity_type
  ?module=Auth                          # optional — filter by route_path prefix or entity_type group
  ?page=1
  ?page_size=25
  ?sort_by=changed_at                   # changed_at | entity_type | change_type | changed_by
  ?sort_desc=true

Response 200:
{
  "data": AuditLogEntry[],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total": 1234
  }
}
```

### 3.2 Summary stats

```
GET /api/v1/audit/stats
  (same optional filters as above, excluding page/page_size/sort)

Response 200:
{
  "total_entries": 1200000,
  "creates": 800000,
  "reads": 350000,
  "updates": 45000,
  "deletes": 5000
}
```

### 3.3 Single audit entry detail

```
GET /api/v1/audit/activity/{id}

Response 200: AuditLogEntry (full data_snapshot + data_diff, no truncation)
```

### 3.4 Export

```
GET /api/v1/audit/export
  (same filters as query)
  ?format=csv                           # csv | json

Response: file download
Filename: audit_export_{YYYY-MM-DD}.{format}
```

### 3.5 Pydantic Schemas

New file: `app/schemas/audit.py`

```python
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.models.audit import AuditChangeTypeEnum


class AuditLogEntry(BaseModel):
    """Single audit log entry returned by the API."""
    id: int
    entity_type: str
    entity_id: int
    version: int
    change_type: AuditChangeTypeEnum
    change_reason: Optional[str]
    changed_by: str                     # email or 'system'
    changed_at: datetime                # ISO 8601
    handler_id: str                     # actor provider code
    handled_ids: List[str]              # affected user provider codes
    ip_address: str
    route_path: Optional[str]
    data_snapshot: Dict[str, Any]       # full JSON snapshot (detail only)
    data_diff: Optional[Dict[str, Any]] # JSON diff (detail only)
    message_summary: Optional[str]      # truncated human-readable summary (~80 chars)

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""
    data: List[AuditLogEntry]
    pagination: "PaginationMeta"


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int


class AuditStats(BaseModel):
    """Summary statistics for audit logs."""
    total_entries: int
    creates: int
    reads: int
    updates: int
    deletes: int


class AuditQueryParams(BaseModel):
    """Query parameters for filtering audit logs."""
    user_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    action: Optional[AuditChangeTypeEnum] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    module: Optional[str] = None
    page: int = 1
    page_size: int = 25
    sort_by: str = "changed_at"
    sort_desc: bool = True
```

### 3.6 Route Registration

In `app/api/v1/audit.py`, create a FastAPI `APIRouter` with prefix `/audit`. Register it in `app/main.py` alongside the existing routers.

```python
from fastapi import APIRouter, Depends, Query, Request, Response
from app.db import get_session
from app.schemas.audit import (
    AuditLogEntry, AuditLogListResponse, AuditStats, AuditQueryParams
)

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/activity", response_model=AuditLogListResponse)
async def list_audit_logs(...): ...

@router.get("/stats", response_model=AuditStats)
async def get_audit_stats(...): ...

@router.get("/activity/{log_id}", response_model=AuditLogEntry)
async def get_audit_log_detail(...): ...

@router.get("/export")
async def export_audit_logs(...): ...
```

### 3.7 Repository Extensions

Extend `AuditDocumentRepository` with:

```python
async def query(
    self,
    filters: AuditQueryParams,
) -> tuple[list[AuditDocument], int]:
    """Paginated, filtered, sorted query. Returns (results, total_count)."""

async def count_by_change_type(
    self,
    filters: AuditQueryParams,
) -> dict[str, int]:
    """Count audit entries grouped by change_type, with same filters (minus pagination)."""
```

### 3.8 Database Indexes (migration)

Add indexes on `audit_documents` for query performance:

```sql
CREATE INDEX ix_audit_documents_changed_at ON audit_documents (changed_at DESC);
CREATE INDEX ix_audit_documents_changed_by ON audit_documents (changed_by);
CREATE INDEX ix_audit_documents_change_type ON audit_documents (change_type);
CREATE INDEX ix_audit_documents_composite ON audit_documents (entity_type, entity_id, changed_at DESC);
```

---

## 4. Frontend — Page Architecture

```
pages/system/LogsPage.vue                  ← orchestrator (replaces placeholder)
├── components/audit/
│   ├── AuditFilterBar.vue                 ← Action / Entity Type / Module / Date Range dropdowns
│   ├── AuditSearchBar.vue                 ← full-width search input + Search button + Export button
│   ├── AuditTable.vue                     ← dark-background data table
│   │   ├── AuditTableHeader.vue           ← sortable column headers
│   │   └── AuditTableRow.vue              ← single log row with status dot
│   ├── AuditPagination.vue                ← "Showing X–Y of Z | Rows per page" + page stepper
│   ├── AuditStatCards.vue                 ← summary cards (Total / Creates / Updates / Deletes)
│   └── AuditDetailDrawer.vue             ← side panel with full entry details + diff viewer
├── api/
│   └── audit.ts                           ← API calls using shared ky client
└── composables/
    └── useAuditLogs.ts                    ← fetch/filter/sort/pagination state
```

### 4.1 Naming Convention

Components use the `Audit` prefix (not `Logs`) to be precise about what they display: **audit trail data from `audit_documents`**, not application/system logs.

The page remains at `system/logs` route for user-facing simplicity, but internal components reference "audit" for code clarity.

---

## 5. API Service Layer

New file: `src/api/audit.ts`

Follows the existing pattern (named exports using shared `ky` instance from `src/api/http.ts`):

```typescript
import { api } from "./http";
import type {
  AuditLogEntry,
  AuditLogListResponse,
  AuditStats,
  AuditQueryParams,
} from "@/types/audit";

export async function fetchAuditLogs(
  params: AuditQueryParams,
): Promise<AuditLogListResponse> {
  return api.get("audit/activity", { searchParams: params }).json();
}

export async function fetchAuditStats(
  params: Partial<AuditQueryParams>,
): Promise<AuditStats> {
  return api.get("audit/stats", { searchParams: params }).json();
}

export async function fetchAuditLogDetail(id: number): Promise<AuditLogEntry> {
  return api.get(`audit/activity/${id}`).json();
}

export async function exportAuditLogs(
  params: AuditQueryParams & { format: "csv" | "json" },
): Promise<Blob> {
  return api.get("audit/export", { searchParams: params }).blob();
}
```

---

## 6. TypeScript Types

New file: `src/types/audit.ts`

```typescript
export type AuditAction =
  | "CREATE"
  | "READ"
  | "UPDATE"
  | "DELETE"
  | "ROLLBACK"
  | "TRANSFER";

export interface AuditLogEntry {
  id: number;
  entity_type: string; // e.g. 'DataEntry', 'User', 'Factor'
  entity_id: number;
  version: number;
  change_type: AuditAction;
  change_reason: string | null;
  changed_by: string; // email or 'system'
  changed_at: string; // ISO 8601
  handler_id: string; // actor provider code
  handled_ids: string[]; // affected user provider codes
  ip_address: string;
  route_path: string | null;
  data_snapshot: Record<string, unknown>;
  data_diff: AuditDiff | null;
  message_summary: string | null; // truncated human-readable summary
}

export interface AuditDiff {
  added: Record<string, unknown>;
  removed: Record<string, unknown>;
  changed: Record<string, { old: unknown; new: unknown }>;
}

export interface AuditStats {
  total_entries: number;
  creates: number;
  reads: number;
  updates: number;
  deletes: number;
}

export interface AuditQueryParams {
  user_id?: string;
  entity_type?: string;
  entity_id?: number;
  action?: AuditAction;
  date_from?: string;
  date_to?: string;
  search?: string;
  module?: string;
  page: number;
  page_size: number;
  sort_by: string;
  sort_desc: boolean;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
}

export interface AuditLogListResponse {
  data: AuditLogEntry[];
  pagination: PaginationMeta;
}
```

---

## 7. `useAuditLogs` Composable

New file: `src/composables/useAuditLogs.ts`

### 7.1 State

```typescript
// Filter state
const actionFilter = ref<AuditAction | null>(null);
const entityTypeFilter = ref<string | null>(null);
const moduleFilter = ref<string | null>(null);
const dateRange = ref<{ from: string; to: string } | null>(null);
const searchQuery = ref("");

// Pagination state
const page = ref(1);
const pageSize = ref(25);
const totalEntries = ref(0);

// Table state
const logs = ref<AuditLogEntry[]>([]);
const isLoading = ref(false);
const sortBy = ref<string>("changed_at");
const sortDesc = ref(true);

// Stats (loaded independently)
const stats = ref<AuditStats>({
  total_entries: 0,
  creates: 0,
  reads: 0,
  updates: 0,
  deletes: 0,
});
const statsLoading = ref(false);

// Detail drawer
const selectedLog = ref<AuditLogEntry | null>(null);
const detailOpen = ref(false);
```

### 7.2 Methods

```typescript
function buildParams(): AuditQueryParams {
  /* assemble from refs */
}

async function fetchLogs() {
  isLoading.value = true;
  try {
    const result = await fetchAuditLogs(buildParams());
    logs.value = result.data;
    totalEntries.value = result.pagination.total;
  } finally {
    isLoading.value = false;
  }
}

async function fetchStats() {
  statsLoading.value = true;
  try {
    stats.value = await fetchAuditStats(buildParams());
  } finally {
    statsLoading.value = false;
  }
}

function onSearch() {
  page.value = 1;
  fetchLogs();
  fetchStats();
}
function onFilterChange() {
  page.value = 1;
  fetchLogs();
  fetchStats();
}
function onSort(column: string) {
  if (sortBy.value === column) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = column;
    sortDesc.value = true;
  }
  fetchLogs();
}
function onPageSizeChange(n: number) {
  pageSize.value = n;
  page.value = 1;
  fetchLogs();
}
function onPageChange(n: number) {
  page.value = n;
  fetchLogs();
}

async function openDetail(id: number) {
  selectedLog.value = await fetchAuditLogDetail(id);
  detailOpen.value = true;
}

async function handleExport(format: "csv" | "json") {
  const blob = await exportAuditLogs({ ...buildParams(), format });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `audit_export_${new Date().toISOString().slice(0, 10)}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}
```

---

## 8. Component Specs

### 8.1 `AuditFilterBar.vue`

Four dropdowns in a flex row (`gap: 16px`, each `height: 40px`):

| Dropdown    | Icon             | Options                                                    |
| ----------- | ---------------- | ---------------------------------------------------------- |
| Action      | `manufacturing`  | All, CREATE, READ, UPDATE, DELETE, ROLLBACK, TRANSFER      |
| Entity Type | `category`       | All, DataEntry, User, Factor, CarbonReport, EmissionFactor |
| Module      | `view_module`    | All, Auth, Data Import, Headcount, Travel, Factors         |
| Date Range  | `calendar_today` | Today, Last 7 days, Last 30 days, Custom range             |

Custom range opens a `QDate` in range mode.

Each dropdown emits `update:modelValue`. Parent calls `useAuditLogs.onFilterChange()`.

### 8.2 `AuditSearchBar.vue`

Full-width row: search input on the left, Export + Search buttons pinned right.

- Input: `border: 1px solid #C1C1C1; border-radius: 3px; height: 40px`
- Search icon in `#707070` inside input
- Placeholder: `"Search by user, entity, or reason..."`
- Search button: `background: #FF0000; color: #FFFFFF; height: 40px`
- Export button: `q-btn` with `download` icon, opens small dropdown: `Export as CSV` / `Export as JSON`
- `Enter` key triggers search

### 8.3 `AuditTable.vue`

Container: `border: 1px solid #C1C1C1; border-radius: 3px; background: #FFFFFF`

#### 8.3.1 Header row (`AuditTableHeader.vue`)

`height: 42px; border-bottom: 1px solid #C1C1C1; padding: 12px`

Columns:

1. **Action** — CREATE/READ/UPDATE/DELETE with color dot
2. **Entity Type** — DataEntry, User, Factor, etc.
3. **Entity ID**
4. **Timestamp** — formatted `changed_at`
5. **User** — `changed_by` email
6. **Summary** — truncated `message_summary` / `change_reason`
7. **Actions** — View / Copy (right-aligned, no sort)

All columns except Actions are sortable. Active sort column shows filled `arrow_drop_down`.

#### 8.3.2 Data rows (`AuditTableRow.vue`)

`height: 26px; background: #212121; padding: 4px 12px`
Font: `SF Mono, 12px, line-height: 18px`

**Action cell** — Status dot (8×8 circle) + bold action text:

| Action   | Color     |
| -------- | --------- |
| CREATE   | `#28A745` |
| READ     | `#0D6EFD` |
| UPDATE   | `#FFC107` |
| DELETE   | `#DC3545` |
| ROLLBACK | `#6C757D` |
| TRANSFER | `#17A2B8` |

**Summary cell** — Text color matches action color, truncated at ~80 chars with `...`

**Actions cell** — `[View] [Copy]` inline text-links, `color: #FFFFFF`:

- **[View]** → opens `AuditDetailDrawer.vue` side panel
- **[Copy]** → copies full entry JSON to clipboard, shows `q-notify` toast

### 8.4 `AuditPagination.vue`

`height: 50px; border-bottom: 1px solid #C1C1C1; padding: 8px 12px`

Left: `"Showing {start}–{end} of {total} entries | Rows per page:"`
Rows-per-page selector cycles: 10 → 25 → 50 → 100 → 10
Prev/next `chevron_left` / `chevron_right` icon buttons on the right.

### 8.5 `AuditStatCards.vue`

Four cards in a flex row (`gap: 18px`), each `border: 1px solid #C1C1C1; border-radius: 3px; padding: 24px; height: 131px`:

| Card          | Value Color | Icon         | Label         |
| ------------- | ----------- | ------------ | ------------- |
| TOTAL ENTRIES | `#0D6EFD`   | `edit_note`  | TOTAL ENTRIES |
| CREATES       | `#28A745`   | `add_circle` | CREATES       |
| UPDATES       | `#FFC107`   | `edit`       | UPDATES       |
| DELETES       | `#DC3545`   | `delete`     | DELETES       |

Value: `font-size: 38px; font-weight: 700`
Label: `font-size: 18px; font-weight: 700; color: #000000`

Stats loaded independently via `fetchStats()` so cards populate even while the table loads.

### 8.6 `AuditDetailDrawer.vue`

Side drawer (right panel, `q-drawer` or `q-dialog` in `position="right"`) opened via `[View]`.

Contains:

**1. Header** — Status dot + action label + timestamp (right-aligned)

**2. Metadata section:**

- Entity Type / Entity ID
- User (`changed_by`)
- Handler ID
- IP Address
- Route Path
- Change Reason (if present)
- Handled IDs (list of affected user provider codes)

**3. Diff viewer** (if `data_diff` exists, i.e., UPDATE/DELETE):

```
Before:                         After:
{                               {
  "name": "Old Name"    →         "name": "New Name"
}                               }
```

- Display `data_diff.changed` with old/new values highlighted
- Display `data_diff.added` in green
- Display `data_diff.removed` in red
- Render in `SF Mono` on `#212121` background

**4. Full snapshot** — Collapsible JSON viewer for `data_snapshot`

**5. Footer** — `[Copy JSON] [Close]` buttons

---

## 9. `LogsPage.vue` — Full Template

Replaces the existing placeholder. Follows existing system page pattern:

```vue
<template>
  <q-page>
    <NavigationHeader :item="SYSTEM_NAV.SYSTEM_LOGS" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <!-- Filter dropdowns row -->
        <AuditFilterBar
          v-model:action="actionFilter"
          v-model:entity-type="entityTypeFilter"
          v-model:module="moduleFilter"
          v-model:date-range="dateRange"
          @filter-change="onFilterChange"
        />

        <!-- Search + Export -->
        <AuditSearchBar
          v-model="searchQuery"
          @search="onSearch"
          @export="handleExport"
        />

        <!-- Table + pagination -->
        <div class="logs-table-container">
          <AuditTable
            :rows="logs"
            :loading="isLoading"
            :sort-by="sortBy"
            :sort-desc="sortDesc"
            @sort="onSort"
            @view="openDetail"
            @copy="copyEntry"
          />
          <AuditPagination
            :page="page"
            :page-size="pageSize"
            :total="totalEntries"
            @update:page="onPageChange"
            @update:page-size="onPageSizeChange"
          />
        </div>

        <!-- Summary stat cards -->
        <AuditStatCards :stats="stats" :loading="statsLoading" />

        <!-- Detail drawer -->
        <AuditDetailDrawer
          v-model="detailOpen"
          :entry="selectedLog"
          @copy="copyEntry"
        />
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import NavigationHeader from "@/components/organisms/backoffice/NavigationHeader.vue";
import { SYSTEM_NAV } from "@/constant/navigation";
import { useAuditLogs } from "@/composables/useAuditLogs";
// Import audit sub-components...

const {
  actionFilter,
  entityTypeFilter,
  moduleFilter,
  dateRange,
  searchQuery,
  page,
  pageSize,
  totalEntries,
  logs,
  isLoading,
  sortBy,
  sortDesc,
  stats,
  statsLoading,
  selectedLog,
  detailOpen,
  onSearch,
  onFilterChange,
  onSort,
  onPageChange,
  onPageSizeChange,
  openDetail,
  handleExport,
} = useAuditLogs();

function copyEntry(entry: AuditLogEntry) {
  navigator.clipboard.writeText(JSON.stringify(entry, null, 2));
  // show q-notify toast
}

onMounted(() => {
  onSearch();
});
</script>
```

---

## 10. Permissions & Guards

### 10.1 Route Guard (existing)

```typescript
beforeEnter: requirePermission("system.users", "edit");
```

This already restricts access to service managers and admins.

### 10.2 Export Guard (optional)

```typescript
const canExport = usePermission("system.logs", "export");
```

### 10.3 Sensitive Data Masking

The `ip_address` and `handled_ids` fields contain potentially sensitive data. In `AuditDetailDrawer.vue`, consider:

```typescript
const canViewSensitive = usePermission("audit.logs", "view_sensitive");
```

If `false`, mask IP addresses (`192.168.x.x → 192.168.***`) and truncate handled_ids.

---

## 11. Loading, Empty & Error States

**Loading:** Skeleton shimmer over table rows while `isLoading === true`. Header and stat cards remain visible.

**Empty (no results):**

```
┌──────────────────────────────────────────────────┐
│  No audit entries found                          │
│  Try adjusting your filters or search query.     │
└──────────────────────────────────────────────────┘
```

Displayed inside the table container in place of rows. Stat cards still show.

**Error (API failure):**

Inline `q-banner` below the search bar:`⚠ Failed to load audit logs. [Retry]`

---

## 12. Styling Tokens

| Token               | Value                                  |
| ------------------- | -------------------------------------- |
| Page bg             | `#FFFFFF`                              |
| Table row bg        | `#212121`                              |
| Table row hover     | `#2A2A2A`                              |
| Table header border | `1px solid #C1C1C1`                    |
| CREATE color        | `#28A745`                              |
| READ color          | `#0D6EFD`                              |
| UPDATE color        | `#FFC107`                              |
| DELETE color        | `#DC3545`                              |
| ROLLBACK color      | `#6C757D`                              |
| TRANSFER color      | `#17A2B8`                              |
| Blue accent         | `#0D6EFD`                              |
| Search button       | `#FF0000`                              |
| Divider             | `#C1C1C1`                              |
| Muted text          | `#707070`                              |
| Body font           | `Suisse Int'l EPFL`, 14px/20px regular |
| Log/code font       | `SF Mono`, 12px/18px                   |
| Heading font        | `Suisse Int'l EPFL`, 18px/27px bold    |

---

## 13. URL Query Sync

Filters should sync with the URL to enable:

- Sharing investigation links
- Bookmarking filtered views
- Browser back/forward support

```
/system/logs?action=UPDATE&entity_type=DataEntry&date_from=2026-01-01&search=sophie
```

In `useAuditLogs.ts`, use `useRoute` / `useRouter` to:

1. Initialize filter state from URL query on mount
2. Update URL query when filters change (using `router.replace`)

---

## 14. Implementation Order

### Phase 1 — Backend API (Sprint 1)

| #   | Task                                                         | File(s)                                 |
| --- | ------------------------------------------------------------ | --------------------------------------- |
| 1   | Pydantic schemas for audit responses                         | `app/schemas/audit.py`                  |
| 2   | Extend `AuditDocumentRepository` with filtered query + count | `app/repositories/audit_repo.py`        |
| 3   | Create audit API router                                      | `app/api/v1/audit.py`                   |
| 4   | Register router in `app/main.py`                             | `app/main.py`                           |
| 5   | DB migration for query indexes                               | `alembic/versions/xxx_audit_indexes.py` |
| 6   | Unit tests for repository query/count                        | `tests/`                                |

### Phase 2 — Frontend Core (Sprint 1)

| #   | Task                                                            | File(s)                                    |
| --- | --------------------------------------------------------------- | ------------------------------------------ |
| 7   | TypeScript types                                                | `src/types/audit.ts`                       |
| 8   | API service layer                                               | `src/api/audit.ts`                         |
| 9   | `useAuditLogs` composable                                       | `src/composables/useAuditLogs.ts`          |
| 10  | `AuditStatCards.vue`                                            | `src/components/audit/AuditStatCards.vue`  |
| 11  | `AuditFilterBar.vue` + `AuditSearchBar.vue`                     | `src/components/audit/`                    |
| 12  | `AuditTableHeader.vue` → `AuditTableRow.vue` → `AuditTable.vue` | `src/components/audit/`                    |
| 13  | `AuditPagination.vue`                                           | `src/components/audit/AuditPagination.vue` |
| 14  | Wire everything in `LogsPage.vue`                               | `src/pages/system/LogsPage.vue`            |

### Phase 3 — Detail & Export (Sprint 2)

| #   | Task                                           | File(s)                                      |
| --- | ---------------------------------------------- | -------------------------------------------- |
| 15  | `AuditDetailDrawer.vue` with diff viewer       | `src/components/audit/AuditDetailDrawer.vue` |
| 16  | Export functionality (CSV/JSON download)       | Backend endpoint + frontend flow             |
| 17  | URL query sync                                 | `src/composables/useAuditLogs.ts`            |
| 18  | Loading/empty/error states                     | All components                               |
| 19  | Permission guards on export + sensitive fields | Components                                   |

### Phase 4 — Polish & Testing (Sprint 2)

| #   | Task                                                         |
| --- | ------------------------------------------------------------ |
| 20  | E2E tests: filter, search, export, detail drawer, pagination |
| 21  | Unit tests: composable logic, API query building             |
| 22  | Performance testing with large audit tables (100k+ rows)     |
| 23  | Accessibility review (keyboard nav, screen reader)           |

---

## 15. Future Extensions (Out of Scope for Now)

These are planned but deferred beyond the initial implementation:

| Extension                                             | Description                                                       | Depends On       |
| ----------------------------------------------------- | ----------------------------------------------------------------- | ---------------- |
| **User Timeline** (`/system/audit/user/:userId`)      | Vertical timeline of all actions by a specific user               | Phase 3 complete |
| **Entity History** (`/system/audit/entity/:type/:id`) | Full change history for one entity with diff between each version | Phase 3 complete |
| **ElasticSearch archival**                            | Move audit logs older than 1 year to ES for long-term retention   | IS-GOV access    |
| **Automatic purge**                                   | Cron job to archive + delete old local records                    | ES integration   |
| **Async export**                                      | Background job for large exports with email notification          | Task queue setup |
| **PDF export**                                        | Compliance reports in PDF format                                  | Export baseline  |
| **Audit-of-audit**                                    | Log when someone views audit logs (meta-auditing)                 | Permission model |

---

## 16. Open Questions

Carried forward from progress report — pending DPO/legal team response:

1. **READ Logging Threshold** — Below what `sciper` count does aggregated data become personally identifiable? Tentative rule: log all READs where affected sciper count < 20.
2. **Headcount vs Travel Logging** — Both modules involve `sciper`. Confirm both require full CRUD + READ audit to ES.
3. **Anonymous/Aggregated Data** — Should dashboard aggregate queries (no individual sciper) be logged?
4. **Data Recipient Identification** — How to populate `recipient_id` for different query types (end-user vs system)?
