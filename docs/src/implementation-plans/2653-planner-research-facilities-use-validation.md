---
status: delivered
issue: 2653
last_updated: 2026-09-11
title: "Planner research facilities: validate the planned use inline instead of surfacing the raw backend error"
summary: "A planned use above 100 for a %-metered platform reached the backend, which rejected it with a pydantic ValueError the grid displayed verbatim. The Planner grid now validates each row against the same per-unit bounds table the Calculator form and the backend use, shows the standard 'Must be at most 100' message under the field, and never sends the invalid value."
---

# Planner research facilities: inline use validation (#2653)

## Symptom

In a Project Grant, adding a research-facility platform whose metric is `%`
and typing a planned use above 100 raised the red toast
"Invalid item_data for creation: 1 validation error for
ResearchFacilitiesCommonHandlerCreate … use must be at most 100 when the
unit is '%' …" plus "Could not save the platform use". The user asked for a
plain "the maximum is 100%" message; the maintainer's call was to validate
on the frontend side.

## Root cause

`PlannerResearchFacilityRows.vue` saved on blur with no `:rules` on the
use input. The Calculator form already mirrors the backend `use_bounds()`
table through the `conditionalBounds` config on the `use` field
(`module-config/research-facilities.ts`, #2007), but the Planner grid
bypassed `ModuleForm` and therefore that mirror. The backend's
`validate_use_within_unit_bounds` was the only guard, and its message is an
internal one.

## Fix

- `frontend/src/constant/module-config/research-facilities.ts`: the two
  identical `conditionalBounds` literals become one exported `USE_BOUNDS`
  constant, so the Planner reads the same table as the Calculator form.
- `frontend/src/utils/numeric-rules.ts`: `getNumericRules` accepts
  `integer: true` and emits the existing `validation_must_be_whole_number`
  message, matching what `ModuleForm.getBounds` enforces.
- `frontend/src/utils/researchFacilityRows.ts`:
  `researchFacilityUseRules(metric, bounds, t)` builds the q-input rules for
  one row from its metric: `min 0`, the unit's `max` when it has one,
  whole numbers for housings.
- `frontend/src/components/organisms/planner/PlannerResearchFacilityRows.vue`:
  each row's input carries `:rules="rulesFor(row)"` (memoised per metric),
  and `persist()` returns before any request when a rule fails. The inline
  message is the shared `validation_must_be_at_most` ("Must be at most 100"
  / "Doit être au plus 100"), the same wording the Calculator form shows.

No backend change: the server-side check stays as the fail-closed guard.

## Tests

`frontend/tests/unit/researchFacilityRows.spec.ts` gains four cases on
`researchFacilityUseRules`: 150 % refused / 100 % accepted, a negative use
refused, a unit without a ceiling (CHF) accepting 20000, and housings
requiring whole numbers.
