# Implementation Plan: Issue #461 — Usage Statistics Box

**Date:** 2026-03-24
**Branch:** `feat/461-reporting-usage-statistics-box`
**Builds on:** Issue #460 (Aggregated Results Box) — commits `04c364d3`, `1088c408`

---

## Objective

Add a "Usage Statistics Box" to the reporting page that displays status breakdown counts as "big number" stat cards. The box behavior depends on how many units are in the filtered result set:

- **Multiple units:** Show 3 cards — Total units validated, Total units in progress, Total units not started (each as `"X / Y"` where Y = total units)
- **Single unit:** Show 3 cards — Validated modules, In-progress modules, Not-started modules (each as `"X / Y"` where Y = total modules for that unit)

**Placement:** Below the Units Table, above the Aggregated Results Box (current position in template is correct — lines 244-258 of `ReportingPage.vue`).

---

## Current State

### What exists (from #460 branch)

| Layer                   | What's done                                                                                         | What's missing                                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Backend**             | `get_reporting_overview()` returns `validated_units_count` and `total_units_count`                  | Missing `in_progress_units_count` and `not_started_units_count`. Missing per-module status counts for single-unit case. |
| **Frontend store**      | `BackofficeUnitDataPagination` has `validated_units_count` and `total_units_count` fields           | Missing `in_progress_units_count`, `not_started_units_count`. Missing module-level status counts.                       |
| **Frontend components** | `ReportingStatCards.vue` and `ReportingStatCardUnit.vue` exist with correct card layout and styling | Both use **hardcoded mock data** (lines 247-251, 256). `ReportingStatCardUnit` only shows 1 card instead of 3.          |
| **i18n**                | Keys `backoffice_reporting_usage_box_validated`, `_in_progress`, `_not_started`, `_one_unit` exist  | May need new keys for the `"X / Y"` format labels                                                                       |
| **API types**           | `ReportingStats` type defined in `frontend/src/api/reporting.ts`                                    | Correct shape for multi-unit; single-unit needs same shape                                                              |

---

## Implementation Steps

### Step 1: Backend — Add per-status unit counts

**File:** `backend/app/repositories/carbon_report_module_repo.py`
**Location:** `get_reporting_overview()`, after the existing `validated_units_count` query (line ~377)

Add two more count queries using the same `base_count_stmt` pattern:

```python
in_progress_units_count = (
    await self.session.exec(
        base_count_stmt.where(
            col(CarbonReport.overall_status) == int(ModuleStatus.IN_PROGRESS)
        )
    )
).one()

not_started_units_count = (
    await self.session.exec(
        base_count_stmt.where(
            col(CarbonReport.overall_status) == int(ModuleStatus.NOT_STARTED)
        )
    )
).one()
```

**Alternative (single query, more efficient):** Use a `GROUP BY` on `overall_status` to get all three counts in one query instead of three separate queries:

```python
status_counts_stmt = (
    base_count_stmt  # but select status + count instead of just count
    # i.e.:
    select(
        col(CarbonReport.overall_status),
        func.count(col(Unit.id))
    )
    .join(CarbonReport, ...)
    .where(...)
    .group_by(col(CarbonReport.overall_status))
)
```

Then parse the result into `{0: X, 1: Y, 2: Z}`.

Update the return dict (line ~644) to include:

```python
"in_progress_units_count": in_progress_units_count,
"not_started_units_count": not_started_units_count,
```

### Step 2: Backend — Add per-module status counts for single-unit case

**File:** `backend/app/repositories/carbon_report_module_repo.py`
**Location:** Within `get_reporting_overview()`, after paginated data is assembled

When the total filtered result has exactly 1 unit, query `CarbonReportModule` for that unit's report to get per-module status breakdown:

```python
if total == 1 and reporting_data:
    single_report_id = reporting_data[0]["carbon_report_id"]  # already available from STEP 2
    module_status_stmt = (
        select(
            col(CarbonReportModule.status),
            func.count(col(CarbonReportModule.id))
        )
        .where(col(CarbonReportModule.carbon_report_id) == single_report_id)
        .group_by(col(CarbonReportModule.status))
    )
    module_status_rows = (await self.session.exec(module_status_stmt)).all()
    module_status_counts = {int(status): count for status, count in module_status_rows}
```

Add to return dict:

```python
"module_status_counts": module_status_counts if total == 1 else None,
```

This gives `{0: 3, 1: 2, 2: 5}` (not_started: 3, in_progress: 2, validated: 5).

### Step 3: Backend — Update response schema

**File:** `backend/app/api/v1/backoffice.py`
**Location:** `PaginatedUnitReportingData` schema (or wherever this Pydantic model is defined)

Add fields:

```python
in_progress_units_count: int = 0
not_started_units_count: int = 0
module_status_counts: Optional[dict[int, int]] = None  # only set when single unit
```

Update the endpoint to pass these through from the repository result.

### Step 4: Frontend store — Add new fields

**File:** `frontend/src/stores/backoffice.ts`
**Location:** `BackofficeUnitDataPagination` interface (line ~37)

```typescript
interface BackofficeUnitDataPagination {
  // ... existing fields
  in_progress_units_count?: number;
  not_started_units_count?: number;
  module_status_counts?: Record<number, number> | null; // {0: X, 1: Y, 2: Z}
}
```

No action code changes needed — the store already assigns the full API response to `units`.

### Step 5: Frontend — Update `ReportingStatCards.vue` (multi-unit)

**File:** `frontend/src/components/organisms/backoffice/reporting/ReportingStatCards.vue`

The component already has the correct 3-card layout with the right labels, colors, and keys. It expects `stats: ReportingStats` which is `{[MODULE_STATES.Default]: number, [MODULE_STATES.InProgress]: number, [MODULE_STATES.Validated]: number}`.

**Change the display format** to show `"X / Y"` instead of just `X`:

- Add a `total` prop
- Update the value display: `{{ stats[card.key] }} / {{ total }}`

### Step 6: Frontend — Update `ReportingStatCardUnit.vue` (single unit)

**File:** `frontend/src/components/organisms/backoffice/reporting/ReportingStatCardUnit.vue`

Currently shows only 1 card. **Rewrite to show 3 cards** matching the multi-unit pattern but for modules:

- Validated modules (green)
- In-progress modules (yellow)
- Not started modules (grey)

Accept same `ReportingStats` type + `total` prop. Display as `"X / Y"`.

### Step 7: Frontend — Wire up `ReportingPage.vue`

**File:** `frontend/src/pages/back-office/ReportingPage.vue`
**Location:** Lines 244-258

Replace hardcoded mock data with computed values:

```typescript
// Multi-unit stats
const usageStats = computed<ReportingStats>(() => ({
  [MODULE_STATES.Default]: units.value?.not_started_units_count ?? 0,
  [MODULE_STATES.InProgress]: units.value?.in_progress_units_count ?? 0,
  [MODULE_STATES.Validated]: units.value?.validated_units_count ?? 0,
}));

// Single-unit stats (from module_status_counts)
const moduleStats = computed<ReportingStats>(() => {
  const counts = units.value?.module_status_counts ?? {};
  return {
    [MODULE_STATES.Default]: counts[0] ?? 0,
    [MODULE_STATES.InProgress]: counts[1] ?? 0,
    [MODULE_STATES.Validated]: counts[2] ?? 0,
  };
});

const totalModules = computed(() => {
  const counts = units.value?.module_status_counts ?? {};
  return Object.values(counts).reduce((a, b) => a + b, 0);
});
```

Update template:

```vue
<ReportingStatCards
  v-if="(units?.data ?? []).length > 1"
  :stats="usageStats"
  :total="tableTotal"
  :loading="loading"
/>
<ReportingStatCardUnit
  v-else-if="(units?.data ?? []).length === 1"
  :stats="moduleStats"
  :total="totalModules"
  :loading="loading"
/>
```

### Step 8: i18n — Verify/add translation keys

Check that these keys exist in both EN and FR:

- `backoffice_reporting_usage_box_validated` — "Units validated" / "Unités validées"
- `backoffice_reporting_usage_box_in_progress` — "Units in progress" / "Unités en cours"
- `backoffice_reporting_usage_box_not_started` — "Units not started" / "Unités non commencées"
- `backoffice_reporting_usage_box_one_unit` — May need renaming/splitting for the 3-card single-unit variant: "Modules validated", "Modules in progress", "Modules not started"

---

## File Change Summary

| File                                                    | Change                                                                                                |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `backend/app/repositories/carbon_report_module_repo.py` | Add `in_progress_units_count`, `not_started_units_count` queries + single-unit `module_status_counts` |
| `backend/app/api/v1/backoffice.py`                      | Add new fields to response schema, pass through from repo                                             |
| `frontend/src/stores/backoffice.ts`                     | Add `in_progress_units_count`, `not_started_units_count`, `module_status_counts` to interface         |
| `frontend/src/api/reporting.ts`                         | No change needed (ReportingStats type already correct)                                                |
| `frontend/src/components/.../ReportingStatCards.vue`    | Add `total` prop, display `"X / Y"` format                                                            |
| `frontend/src/components/.../ReportingStatCardUnit.vue` | Rewrite to 3-card layout with `ReportingStats` + `total` props                                        |
| `frontend/src/pages/back-office/ReportingPage.vue`      | Replace hardcoded mock data with computed values from store                                           |
| `frontend/src/i18n/...`                                 | Verify/add EN+FR keys for single-unit module labels                                                   |

---

## Design Decisions

1. **Single GROUP BY vs 3 separate COUNT queries** — Prefer the GROUP BY approach for the multi-unit status counts. It's one DB round-trip instead of three.

2. **`module_status_counts` only for single-unit** — Only compute per-module breakdown when exactly 1 unit is filtered. This avoids an expensive cross-unit module aggregation that isn't needed for the multi-unit view.

3. **Reuse `ReportingStats` type** — Both the multi-unit and single-unit cards use the same `{0: X, 1: Y, 2: Z}` shape keyed by `ModuleStatus`. The components can share the same interface; only the labels differ (units vs modules).

4. **`total` as separate prop** — Rather than computing `X / Y` in the backend as a string, pass `total` as a prop so the component can format it. This keeps the API clean and allows flexible frontend formatting.

---

## Dependencies

- Issue #460 (Aggregated Results Box) must be merged or the current branch must be rebased on it — **already done** (commits `04c364d3`, `1088c408` are on this branch).
- Issue #245 mentioned in GitHub comments (module status tracking) — `CarbonReportModule.status` field already exists and is populated, so no dependency.

## Testing Notes

- Test multi-unit case: Select a hierarchy level that returns multiple units → verify 3 cards show correct `validated / total`, `in_progress / total`, `not_started / total`
- Test single-unit case: Filter to a single unit → verify 3 cards show per-module status breakdown
- Test zero results: Ensure stats box doesn't render when no data
- Verify counts: `validated + in_progress + not_started` should equal `total` in both cases
