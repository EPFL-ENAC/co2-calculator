---
status: delivered
issue: 2214
last_updated: 2026-08-28
title: "Centralize date input handling — format hint and validation on inline table edits"
summary: "Editing a travel date inline in the module table gave no hint of the expected format and an unclear error on a bad entry. Centralizes the mask/validation logic used by the add-entry form into frontend/src/utils/date.ts and applies it to inline table editing too, which previously had none."
---

# Centralize date input handling (#2214)

## Problem

Editing a travel date directly in the module table (e.g. after adding a
plane/train entry) gave no hint of the expected date format, and typing an
invalid one produced an unclear error. The add-entry form already masked and
validated dates, but that logic was duplicated inline in `ModuleForm.vue` and
never applied to the table's inline edit path at all.

## What shipped

PR #2256, "feat: centralize date input handling (#2214)", merged 2026-08-24
(`e0b3cf99c`).

- `frontend/src/utils/date.ts` — new shared exports: `DATE_INPUT_MASK`
  (`'####/##/##'`), `matchesDateInputFormat(val)` (regex-checks
  `YYYY/MM/DD`-shaped input, `/`, `.` or `-` separated), and
  `isValidCalendarDate(val)` (round-trips through `Date` to reject invalid
  dates like Feb 30).
- `frontend/src/i18n/common.ts` — new `date_format_placeholder` key
  (`YYYY/MM/DD` / `AAAA/MM/JJ`).
- `frontend/src/components/organisms/module/ModuleForm.vue` — dropped its
  locally-duplicated `isValidCalendarDate` and inline regex in favor of the
  shared utils, on both `getDateRules()` and a date-diff validator.
- `frontend/src/components/organisms/module/ModuleTable.vue` — the actual bug
  fix, since inline editing had no masking or validation before: adds
  `:mask="DATE_INPUT_MASK"` on date columns, a `getColumnPlaceholder()` that
  surfaces the `date_format_placeholder` hint, and validates the committed
  value against `matchesDateInputFormat`/`isValidCalendarDate` — blocking the
  commit via `setError(row, col, ...)` on a bad format or an invalid date.

No follow-up issues filed.
