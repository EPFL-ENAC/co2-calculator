---
status: delivered
issue: 2318
last_updated: 2026-08-28
title: "Headcount FTE fields capped at one decimal place"
summary: "FTE fields in the Headcount module accepted up to 16 decimal places. Adds a generic maxDecimals config option to module fields, set to 1 on both Headcount FTE fields, enforced on the add-entry form and on inline table editing."
---

# Headcount FTE max decimals (#2318)

## Problem

In the Headcount module, the member and student FTE fields accepted values
with up to 16 decimal places, when the product intent is one decimal place
(e.g. `0.5`).

## What shipped

PR #2329, "feat: add maxDecimals validation and support (#2318)", merged
2026-08-25 (`d49b3919f`).

- `frontend/src/constant/moduleConfig.ts` — new optional `maxDecimals?:
number` on the field config type.
- `frontend/src/constant/module-config/headcount.ts` — `maxDecimals: 1` on
  both the `member` and `student` FTE field configs.
- `frontend/src/components/organisms/module/ModuleForm.vue` — validation
  branch: rejects a typed value whose fractional part exceeds `maxDecimals`,
  via `$t('validation_max_decimals', { count: i.maxDecimals })`.
- `frontend/src/components/organisms/module/ModuleTable.vue` — same check
  threaded into inline table editing: a Quasar input `rules` entry plus the
  same decimal-length check in the numeric parser used when committing a
  cell edit.
- `frontend/src/i18n/common.ts` — new `validation_max_decimals` key (EN/FR).

`maxDecimals` is a generic field option, not Headcount-specific, so any
future module field can opt in the same way.

## Since shipped

Two later, separately-tracked fixes reshaped this code without changing its
behavior:

- Refs #2473 — `ModuleTable.vue`'s `getNumericRules()` (the `q-input` rules
  builder for `min`/`max`/`maxDecimals`) was extracted to
  `frontend/src/utils/numeric-rules.ts` so it's unit-testable without
  mounting the component; `frontend/tests/unit/numeric-rules.spec.ts` now
  covers the `maxDecimals` case, which had no test at original ship time.
- Refs #2472 — `validation_max_decimals` was hard-coded singular ("decimal
  place") despite being parameterized; rewritten as a vue-i18n plural-pipe
  message (`{count} decimal place | {count} decimal places`), and the
  interpolation param renamed `max` → `count` at all three call sites.

No follow-up issues filed against #2318 itself.
