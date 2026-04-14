# Code Review: Commit `b9c1b83b` — Aggregated Results Box (#460)

**Reviewer:** Claude (automated)
**Date:** 2026-03-24
**Commit:** `b9c1b83b1cbd9d9c11870826f3617ac826a89516`
**Message:** feat: implement Aggregated box section in backend's reporting tab
**Scope:** 27 files changed, ~1226 insertions, ~363 deletions

---

## Summary

This commit replaces the static placeholder image in the reporting page with functional aggregated results: a completion rate bar, carbon footprint charts (bar + per-FTE), and an emission breakdown treemap. It also implements real hierarchy filtering (lvl2/lvl3/lvl4) in the backend, replaces the mocked `get_available_years` with a real DB query, and extracts treemap logic into a shared composable.

---

## Critical Issues

### C1. `_get_descendant_unit_ids` — potential full table scan

**File:** `backend/app/repositories/carbon_report_module_repo.py`

When `path_conditions` is empty (selected units have no `institutional_code`), the query becomes `select(Unit.id)` with **no WHERE clause** — scanning the entire `units` table:

```python
descendants_stmt = select(Unit.id)
if path_conditions:
    descendants_stmt = descendants_stmt.where(or_(*path_conditions))
```

**Fix:** Return `selected_ids` directly when `selected_codes` is empty (no path-based lookup needed).

### C2. `headcountValidated` uses wrong proxy in ReportingPage

**File:** `frontend/src/pages/back-office/ReportingPage.vue:293-296`

```vue
:headcount-validated="
reportingEmissionBreakdown?.validated_categories?.includes('commuting') ?? false
"
```

This checks whether `commuting` is validated as a proxy for headcount validation. The backend already computes and returns `headcount_validated` — the field should be used directly instead of this fragile heuristic.

### C3. Completion rate counts only current page, not full filtered set

**File:** `frontend/src/pages/back-office/ReportingPage.vue:96-102`

```typescript
const tableRows = computed(() => units.value?.data ?? []);
const validatedCount = computed(
  () =>
    tableRows.value.filter((row) =>
      isFullyValidatedProgress(row.completion_progress),
    ).length,
);
const tableTotal = computed(() => tableRows.value.length);
```

`units.value.data` only contains the current page (max 50 rows). The `CompletionRateBar` therefore shows "X out of Y validated" scoped to the visible page, not the full filtered dataset. The backend should return aggregated counts for the full result set.

### C4. `filtered_report_ids` loaded into memory without limit

**File:** `backend/app/repositories/carbon_report_module_repo.py`

```python
filtered_report_ids = [
    report_id
    for report_id in (await self.session.exec(filtered_report_ids_stmt)).all()
    if report_id is not None
]
```

This loads **all** matching report IDs into a Python list, then passes them in `WHERE ... IN (...)`. For large deployments, this could be thousands of IDs. Consider using a subquery instead of materializing the list:

```python
# Use subquery instead of list
filtered_report_ids_subq = filtered_report_ids_stmt.subquery()
# Then: .where(col(CarbonReportModule.carbon_report_id).in_(select(filtered_report_ids_subq)))
```

---

## Warnings

### W1. `emission_category.py` — `kg_co2eq is None` still checked despite `float` type

**File:** `backend/app/utils/emission_category.py`

The type signature was changed from `float | None` to `float`, but the loop body still checks `if kg_co2eq is None: continue`. This is dead code now — either remove the check or keep `float | None` if `None` values are still possible in practice.

### W2. Duplicate filter construction between `count_statement` and `units_stmt`

**File:** `backend/app/repositories/carbon_report_module_repo.py`

The `hierarchy_unit_ids` and `completion_status` WHERE clauses are applied identically to `count_statement`, `units_stmt`, and `filtered_report_ids_stmt`. This triplication is error-prone — if one changes, the others may diverge. Consider extracting a shared filter-builder.

### W3. `build_chart_breakdown` called with module stats rows, not emission rows

**File:** `backend/app/repositories/carbon_report_module_repo.py`

The reporting endpoint aggregates from `CarbonReportModule.stats['by_emission_type']` (pre-computed JSON), while the results page aggregates from live `DataEntryEmission` rows. If stats are stale (e.g., not recomputed after data edits), the reporting charts will show outdated data.

### W4. `GenericEmissionTreeMapChart` — i18n labels removed

**File:** `frontend/src/components/charts/GenericEmissionTreeMapChart.vue`

The entire `TREEMAP_LABEL_KEY_MAP` was removed. Labels now use raw keys like `scientific`, `it`, `co2` via `node.name.replace(/_/g, ' ')`. This means the treemap will show English-only machine keys instead of translated labels, breaking FR i18n for the results page treemap.

### W5. `Promise.resolve().then()` instead of `nextTick`

**File:** `frontend/src/stores/unitFilters.ts`

The comment says "Use nextTick to ensure data is reset before fetching", but `Promise.resolve().then()` is used instead of Vue's `nextTick()`. While both are microtask-based, `nextTick` is the idiomatic Vue approach and ensures the DOM/reactivity flush has completed. This pattern is also duplicated 3 times — should be a shared helper.

### W6. `recompute_report_progress` called before `db.commit()`

**File:** `backend/app/api/v1/carbon_report.py:139`

```python
await report_service.recompute_report_progress(carbon_report_id)
await db.commit()
```

If `recompute_report_progress` reads data that was just written in the same transaction, it may not see the uncommitted changes depending on the isolation level. Verify that this ordering is intentional.

---

## Notes

### N1. `CompletionRateBar` — `loading` prop declared but never used

**File:** `frontend/src/components/organisms/backoffice/reporting/CompletionRateBar.vue:452`

The `loading` prop is defined with a default of `false` but is not referenced in the template or script.

### N2. `ResultsPage.vue` — `viewUncertainties` props removed

**File:** `frontend/src/pages/app/ResultsPage.vue`

The `:view-uncertainties` prop was removed from `ModuleCarbonFootprintChart` and `CarbonFootPrintPerPersonChart`. Verify these components no longer use this prop (or that it's optional) to avoid a silent regression.

### N3. `UnitReportingData.ts` — duplicate interface

**File:** `frontend/src/constant/UnitReportingData.ts`

This new file defines `UnitReportingData` interface, but `BackofficeUnitData` in `frontend/src/stores/backoffice.ts` defines the same shape. Having two sources of truth for the same data shape will cause drift.

### N4. `Makefile` — seed commands uncommented

**File:** `backend/Makefile`

`seed_locations` and `seed_building_rooms` were uncommented. Ensure these seeds are idempotent, as they will now run on every `make seed-data` invocation.

### N5. Color prop always `'primary'` in `EmissionBreakdownChart`

**File:** `frontend/src/components/charts/EmissionBreakdownChart.vue:114`

```vue
:color="activeTab === mod ? 'primary' : 'primary'"
```

Both branches of the ternary are identical — the outline/unelevated distinction handles the visual difference, but this should likely be cleaned up.

### N6. `ReportingYear.vue` — guard removed

**File:** `frontend/src/components/organisms/backoffice/reporting/ReportingYear.vue`

The `if (newYears.length === 0) return {}` guard was removed from the watcher. Now an empty selection will emit `update:years` with `[]`, which the parent handles by clearing state. This is fine but is a behavior change worth noting.

---

## Overall Assessment

The commit delivers the core #460 feature successfully — the reporting page now shows real aggregated charts. The main concerns are:

1. **Performance**: Full table scan risk in `_get_descendant_unit_ids` and in-memory materialization of all filtered report IDs (C1, C4)
2. **Data accuracy**: Completion rate scoped to current page only (C3), stale stats risk (W3)
3. **i18n regression**: Treemap labels lost translations (W4), FR text missing diacritics (W5)
4. **Fragile proxy**: `headcountValidated` derived from `commuting` presence instead of using the backend field (C2)
