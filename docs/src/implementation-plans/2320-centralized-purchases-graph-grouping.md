---
status: delivered
issue: 2320
last_updated: 2026-08-28
title: "Centralized purchases graph grouped by product name"
summary: "The centralized-purchases bar chart showed every bar labeled 'Unknown' because the module's grouping fell back to an institutional/factor code these entries don't carry. Adds a per-data-entry-type override so purchases_centralized rows group by their free-text name field instead."
---

# Centralized purchases graph grouping (#2320)

## Problem

The horizontal-bar chart for centralized purchases (Purchases module) showed
a single bar labeled "Unknown" instead of the actual product names. Centralized
purchase entries carry no institutional/factor code — only a free-text
product `name` — and the chart's default grouping key assumed one, so every
row collapsed into the fallback bucket.

## What shipped

PR #2335, "feat: group centralized purchases by name (#2320)", merged
2026-08-25 (`2a333a360`).

- `backend/app/api/v1/carbon_report_module.py:431-440` —
  `_MODULE_TOP_CLASS_GROUP_FIELD_OVERRIDES` gains an entry for
  `ModuleTypeEnum.purchase` / `DataEntryTypeEnum.purchases_centralized` →
  group by `"name"` instead of the default code-based key.
- `frontend/src/composables/useEmissionTreemap.ts:36` — adds
  `['purchases_centralized', 'centralized']` to the data-entry-type-prefix →
  treemap-category map, so the same entries also render under the right
  category in the emission treemap.

Backend stays the grouping source of truth; the frontend change only fixes a
separate, unrelated treemap-category lookup for the same data-entry type.

No follow-up issues filed.
