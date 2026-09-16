---
status: delivered
issue: 2061
last_updated: 2026-09-16
title: "Planner External AI FTE count must start empty"
summary: "In the Planner (Grant Proposal), External AI's 'Number of users (FTE)' was pre-filled with the unit's validated Headcount total leaked from the Calculator's timeline store; the Calculator-only default is now gated off in the Planner as well as the Explorer."
---

# Planner External AI FTE default (#2061)

## Problem

Last open item of umbrella issue #2061, reported non-conforming in dev: in
**Planner – Grant Proposal**, External AI, `Number of users (FTE)` was
pre-filled with the unit's FTE count instead of starting empty.

Cause: `SubModuleSection.vue` applied the `defaultFrom: 'total_fte'` rule
whenever the table was not the Explorer. The timeline store
(`stores/modules.ts`) still holds the Calculator's report from the workspace
visit, so its validated Headcount total was fetched and pre-filled into the
Planner form — a value that belongs to the Calculator report, never to a
plan year (see the `ModuleTableAccess` docblock).

## What shipped

Frontend only:

- `frontend/src/utils/module-table-access.ts` — new pure rule
  `resolveValidatedFteFormDefaults(fields, {isExplorer, isPlanner}, totalFte)`:
  returns the rounded validated total for `defaultFrom: 'total_fte'` fields in
  the Calculator only; empty in the Explorer, the Planner, and when the total
  is 0 / missing.
- `frontend/src/components/organisms/module/SubModuleSection.vue` — uses the
  rule in `formDefaults` and skips the `getValidatedTotals` fetch on mount in
  the Planner too (it was already skipped in the Explorer).
- `frontend/tests/unit/external-ai-fte-planner-default.spec.ts` — regression
  test: Calculator pre-fills, Planner/Explorer stay empty with a validated
  total loaded, 0/undefined pre-fill nothing.

Resulting matrix for External AI `fte_count`: Calculator → validated
Headcount total; Explorer → empty; Planner (Grant Proposal and prefilled) →
empty.
