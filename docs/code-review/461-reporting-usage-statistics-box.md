# Code Review: Branch `feat/461-reporting-usage-statistics-box` — Usage Statistics Box (#461)

**Reviewer:** Claude (automated)
**Date:** 2026-03-24
**Branch:** `feat/461-reporting-usage-statistics-box`
**Latest commit:** `f811b43b`

---

## Summary

This branch adds the Usage Statistics Box to the reporting page (issue #461), wires up the `CompletionRateBar` component, replaces mock data with live API counts, and fixes several filter/year selection bugs. It builds on the Aggregated Results Box work from #460.

---

## Bugs / Incomplete Implementation

### 1. `ReportingStatCards.vue` — `total` prop declared but never rendered

**Severity: High** — The plan specifies `"X / Y"` display format for all stat cards. A `total` prop was correctly added to the interface, but the template still renders only `stats[card.key].toLocaleString()`. The denominator is silently dropped.

**File:** `frontend/src/components/organisms/backoffice/reporting/ReportingStatCards.vue:51`

```vue
<!-- current -->
{{ stats[card.key].toLocaleString() }}

<!-- expected -->
{{ stats[card.key].toLocaleString() }} / {{ total.toLocaleString() }}
```

---

### 2. `ReportingStatCardUnit.vue` — 1 card instead of 3 (plan deviation)

**Severity: High** — The implementation plan (step 6) explicitly requires rewriting this component to show 3 cards: Validated modules / In-progress modules / Not started modules, matching the shape of `ReportingStatCards`. The current implementation shows only 1 card with a `validatedModules / totalModules` ratio, which loses the in-progress and not-started breakdown entirely.

The backend already returns `module_status_counts: {0: X, 1: Y, 2: Z}` and the store exposes `moduleStats` of the correct `ReportingStats` shape — the frontend component just hasn't consumed it.

---

### 3. `backoffice.py` — `ValueError` causes HTTP 500

**Severity: High** — In `list_backoffice_units`, when no years are provided:

```python
raise ValueError("At least one year must be specified for reporting overview")
```

FastAPI does not catch bare `ValueError` from route handlers — the server returns a 500 Internal Server Error instead of a client-facing 422. Should use:

```python
from fastapi import HTTPException
raise HTTPException(status_code=422, detail="At least one year must be specified")
```

**File:** `backend/app/api/v1/backoffice.py` — `list_backoffice_units`

---

### 4. `ReportingStatCardUnit.vue` — `<q-tooltip>` placed outside `<q-icon>`

**Severity: Medium** — The `<q-tooltip>` must be a child of the element it annotates to receive hover events. The current structure puts it as a sibling of `<q-icon>`, so it never triggers.

```vue
<!-- current (broken) -->
<q-icon :name="outlinedInfo" ... />
<q-tooltip anchor="center right" ...>...</q-tooltip>

<!-- correct -->
<q-icon :name="outlinedInfo" ...>
  <q-tooltip anchor="center right" ...>...</q-tooltip>
</q-icon>
```

**File:** `frontend/src/components/organisms/backoffice/reporting/ReportingStatCardUnit.vue:23-31`

---

### 5. `CompletionRateBar.vue` — helper text rendered twice

**Severity: Low** — `resolvedHelperText` appears both inside the `<q-tooltip>` on the info icon and as a plain `text-body2` paragraph below the progress bar. This is redundant — the two placements serve the same purpose.

**File:** `frontend/src/components/organisms/backoffice/reporting/CompletionRateBar.vue:86-89`

---

## Minor Issues

### 6. `backoffice_reporting_completion_bar_count` — unused `{scope}` interpolation param

The `CompletionRateBar` template passes `scope: resolvedScopeLabel` to `$t(...)`, but neither the EN nor FR translation strings include the `{scope}` placeholder. The scope label is silently discarded at runtime.

```
en: '{validated} out of {total} total units validated'   ← no {scope}
fr: '{validated} unités validées sur {total}'            ← no {scope}
```

Either add `{scope}` to the strings (e.g. `'{validated} out of {total} units validated {scope}'`) or remove the unused parameter.

**Files:** `frontend/src/components/organisms/backoffice/reporting/CompletionRateBar.vue:62-70`, `frontend/src/i18n/backoffice_reporting.ts`

---

### 7. French i18n strings missing accents

Several new French strings appear to be placeholder copy rather than final translations:

| Current                                     | Should be                                   |
| ------------------------------------------- | ------------------------------------------- |
| `'Empreinte carbone par unite'`             | `'Empreinte carbone par unité'`             |
| `'Une barre par unite avec l empreinte...'` | `'Une barre par unité avec l'empreinte...'` |
| `'Calculee comme empreinte...'`             | `'Calculée comme empreinte...'`             |
| `'Aucune donnee disponible'`                | `'Aucune donnée disponible'`                |

**File:** `frontend/src/i18n/backoffice_reporting.ts`

---

### 8. `ReportingYear.vue` — early-return guard removed without trace

The removed check `if (newYears.length === 0) return {}` is now handled upstream in `ReportingPage.fetchUnits()` with an early return + `backofficeStore.units = null`. This is the right approach, but the two locations are non-obvious to connect. A brief comment in `fetchUnits()` would help future readers.

**File:** `frontend/src/pages/back-office/ReportingPage.vue` — `fetchUnits()`

---

## Positive Notes

- Replacing the `selectedUnits` flat array with separate `path_lvl2/3/4` refs is a clean improvement that aligns frontend filter structure with the backend query parameters.
- The `CompletionRateBar` component is well-isolated and reusable (title/helper/scope all have sensible defaults via `withDefaults`).
- Fixing the `@update:model-value` missing from the completion status `q-select` in `ReportingFilters.vue` is a good catch.
- Moving `/years` from mocked data to a real `CarbonReport.year DISTINCT` query is a correct and overdue fix.
- `emit-value` + `map-options` addition to `ReportingYear.vue` is necessary for Quasar `q-select` with `option-value` to emit primitive values rather than full option objects.

---

## Issue Checklist

| #                                             | Severity | Status |
| --------------------------------------------- | -------- | ------ |
| `total` prop unused in `ReportingStatCards`   | High     | Open   |
| `ReportingStatCardUnit` shows 1 card not 3    | High     | Open   |
| `ValueError` causes HTTP 500                  | High     | Open   |
| Tooltip outside `q-icon`                      | Medium   | Open   |
| Helper text duplicated in `CompletionRateBar` | Low      | Open   |
| `{scope}` unused in i18n string               | Low      | Open   |
| French strings missing accents                | Low      | Open   |
| `fetchUnits` guard comment missing            | Trivial  | Open   |
