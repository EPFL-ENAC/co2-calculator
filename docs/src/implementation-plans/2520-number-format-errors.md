---
status: delivered
issue: 2520
last_updated: 2026-09-11
title: "Streamline number formatting errors"
summary: "Equipment usage-hours fields now go through the same dot-decimal format check as every other numeric field, in the form and in the inline table, instead of coercing a comma value to NaN or forwarding it to the backend."
---

# 2520 — Streamline number formatting errors

## Problem

Typing `1,5` in a numeric field produced two different outcomes:

- Process Emissions quantity (any generic `type: 'number'` field): the form
  shows "Use a dot (.) not a comma (,)" under the field.
- Equipment active/standby usage hours: the field shows `NaN`.

`ModuleForm.validateField` special-cases the two usage-hours fields for the
weekly-sum check and returned before the generic number-format block, storing
`Number("1,5")` (NaN) into the form. `ModuleTable.commitInline` had the same
short-circuit: a non-numeric usage value skipped the format and bounds checks
and was sent to the backend as a raw string, surfacing a backend error instead
of the friendly message.

## Change

- `ModuleForm.vue`: the generic number checks (comma, format, min/max, whole
  number, max decimals) move into `numberFormatError(field, value)`. The
  generic path and the usage-hours branch both call it; the usage branch runs
  it before the weekly-sum check, so the comma message wins and nothing is
  coerced while the value is invalid.
- `ModuleTable.vue`: `commitInline` runs the shared numeric branch for usage
  fields too (comma, format, min 0 / max 168 from the column config, max
  decimals), then applies the weekly-sum check on the parsed number through
  `validateUsageSum`. An emptied usage cell still saves 0, as before.
- The two usage-hours fields carry `integer: true` (new top-level flag on
  `ModuleField`, same shape as `conditionalBounds.byValue[].integer`). The form
  reads it through `getBounds` and the table through the column, so `12.5`
  shows "Must be a whole number" in both places instead of the backend's
  `int_from_float` 400.

## Verification

- Equipment form: type `1,5` in active usage, blur or submit: the dot message
  shows, the field keeps `1,5`, nothing is submitted; `12.5` shows the
  whole-number message; `40` submits.
- Equipment table inline usage cell: `1,5` shows the dot message, `200` the
  "at most 168" message, `12.5` the whole-number message, none of them
  PATCHes; `40` PATCHes once. Verified 2026-09-11 with Playwright against the
  local stack.
- Process Emissions quantity: unchanged.
- `make lint`, `make type-check`.
