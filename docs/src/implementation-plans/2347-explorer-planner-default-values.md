---
status: delivered
issue: 2347
last_updated: 2026-08-28
title: "Fix misleading default values in Explorer/Planner forms"
summary: "Three Explorer/Planner form fields defaulted to misleading values (FTE forced to 0, no traveler pre-selected sensibly, Equipment ID blank) instead of leaving them empty or picking a sensible default. Part of the #2061 default-values cleanup."
---

# Explorer/Planner default values (#2347)

## Problem

`gh issue view 2347` resolves to a pull request, not a standalone issue —
#2347 is the PR number, on branch `fix/2061`. It delivers part of umbrella
issue **#2061**, "Dynamic default values different in Explorer, Project
Planner and Calculator" (#2061 stays open: other sub-items are tracked
separately, delivered via other PRs — #1998, #1995, #2000, #2119, #2297).

This PR's slice: in the Explorer's External Cloud & AI form, FTE count
defaulted to `0` instead of empty; in the Explorer's Professional Travel
form, no sensible traveler was pre-selected; in the Explorer's Equipment
form, Equipment ID defaulted to blank instead of `"Unknown"`.

## What shipped

PR #2347, "fix: apply various default values in planner/explorer forms",
merged 2026-08-25 (`32fe8c442`). All frontend, 5 files:

- `frontend/src/constant/moduleConfig.ts` — widens
  `ModuleField.explorerDefault` from `number` to `string | number | null` to
  allow non-numeric sentinel defaults.
- `frontend/src/constant/module-config/equipment.ts` — Equipment ID gets
  `explorerDefault: 'Unknown'`.
- `frontend/src/constant/module-config/professional-travel.ts` — the
  traveler field gets `explorerDefault: TRAVELER_OTHER_INTERNAL` (Explorer
  has no headcount roster to pick a real traveler from).
- `frontend/src/constant/module-config/external-cloud-and-ai.ts` — removes
  the old `explorerDefault: 0` for FTE count so it starts empty in Explorer;
  the Calculator path is unaffected (`defaultFrom: 'total_fte'` stays).
- `frontend/src/components/organisms/module/SubModuleSection.vue:195` — the
  `total_fte` default-fill condition becomes `field.defaultFrom ===
'total_fte' && validatedTotals.total_fte`, so a validated total of
  exactly `0` is treated as "nothing to pre-fill" rather than shown as a
  misleading `0`.

No test files were touched in this diff. Note:
`frontend/tests/unit/external-ai-fte-explorer-default.spec.ts` (from the
earlier #2000/#2061 commit that first set `explorerDefault: 0`) exercises
the generic `resolveExplorerFormDefaults` resolver via a synthetic field
object, not `external-cloud-and-ai.ts`'s real config — so it still passes
after this PR removed the real field's `explorerDefault`, but its docblock
description is now stale.
