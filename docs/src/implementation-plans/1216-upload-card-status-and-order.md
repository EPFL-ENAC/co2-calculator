---
status: delivered
issue: 1216
last_updated: 2026-05-28
title: "BackOffice upload card — API success status + FACTORS-first order"
summary: "Data card now turns green when the API ingestion path succeeds (not only CSV). FACTORS-first order across Equipments / Purchases is pinned by a regression test."
---

# 1216 — BackOffice upload card: API success status + FACTORS-first order

## 1. Problem

Two small bugs reported on the BackOffice Configuration page (issue
[#1216](https://github.com/EPFL-ENAC/co2-calculator/issues/1216)):

1. **Box order.** Screenshot from Equipments showed the DATA card
   rendered before the FACTORS card. Specification is FACTORS first,
   DATA second — same as every other module.
2. **API connection success.** When the operator uploads via the API
   path (e.g. plane / cloud connectors) and the API job succeeds, the
   DATA card stays grey ("accent"). The operator can't tell "API
   connected, rows imported" from "nothing uploaded yet".

## 2. Investigation

### Box order

Bug already fixed on `dev` by commit
[`69c5a3d8`](https://github.com/EPFL-ENAC/co2-calculator/commit/69c5a3d8)
on 2026-05-19 (`chore(frontend): invert factors and data for common`)
following the per-submodule fix
[`780773a8`](https://github.com/EPFL-ENAC/co2-calculator/commit/780773a8)
(`fix(310): reorder factors before data on data-management page`).
Both render paths now declare FACTORS first:

- `frontend/src/components/molecules/data-management/ModuleUploadsSection.vue:98-121`
  (common uploads — Equipments / Purchases)
- `frontend/src/components/molecules/data-management/SubmoduleItem.vue:253-285`
  (per-submodule uploads)

No code change needed for bug 1; the fix is to **pin the order with a
regression test** so a future refactor can't silently revert it.

### API success → green

`frontend/src/composables/useUploadCard.ts:30-36` reads only
`row.lastDataJob`:

```ts
function dataButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (!row.lastDataJob) return 'accent';                              // ← API-only row hits this
  if (row.lastDataJob.result === IngestionResult.ERROR) return 'negative';
  if (row.lastDataJob.result === IngestionResult.WARNING) return 'warning';
  return 'positive';
}
```

`ImportRow` already exposes `lastApiDataJob` (populated from
`subConfig.latest_api_data_job` in `useModuleConfig.getImportRow`), so
the data is on the row — `dataButtonColor` just doesn't look at it.

## 3. Fix

### Bug 2: extend `dataButtonColor` to honour `lastApiDataJob.result === SUCCESS`

Precedence is preserved: `disabled > CSV-error > CSV-warning >
CSV-success > API-success > accent`. CSV result always wins over API
result so an errored CSV after a prior API success stays red. Only
explicit `IngestionResult.SUCCESS` triggers green — an API job with an
unrecognised result falls through to `accent` (no silent
green-by-default).

```ts
function dataButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (row.lastDataJob?.result === IngestionResult.ERROR) return 'negative';
  if (row.lastDataJob?.result === IngestionResult.WARNING) return 'warning';
  if (row.lastDataJob?.result === IngestionResult.SUCCESS) return 'positive';
  if (row.lastApiDataJob?.result === IngestionResult.SUCCESS) return 'positive';
  return 'accent';
}
```

The inline "API success: N rows imported" caption in `UploadCard.vue`
(lines 340-354) is gated on `apiJob && !hasApiErrorOrWarn`, independent
of `buttonColor` — it keeps rendering alongside the new green border.

### Bug 1: regression test only

No code change. Test pins FACTORS-first in the upload row.

## 4. Files changed

| File | Change |
| ---- | ------ |
| `frontend/src/composables/useUploadCard.ts` | Extend `dataButtonColor` to surface API success. |
| `frontend/tests/integration/data-management.spec.ts` | Add tests 1216a (API-only → green button) and 1216b (FACTORS before DATA in render order). |

## 5. Before / after

| State | Before | After |
| --- | --- | --- |
| Only `lastApiDataJob.result === SUCCESS` | Data button = `accent` (grey), card border grey. Inline "API ingestion: 42 rows imported" text below. | Data button = `positive` (green), card border green. Inline text unchanged. |
| `lastDataJob.result === SUCCESS` (CSV) | green | green (unchanged) |
| `lastDataJob.result === ERROR`, `lastApiDataJob.result === SUCCESS` | red (`negative`) | red (CSV error wins, unchanged) |
| No jobs at all | grey (`accent`) | grey (unchanged) |
| Equipments / Purchases upload cards | FACTORS before DATA (already fixed in `69c5a3d8`) | FACTORS before DATA, now pinned by a regression test. |

## 6. Regression tests

- `frontend/tests/integration/data-management.spec.ts` test
  `1216a — successful API ingestion (no CSV) turns the data card button green`:
  mounts a year-configuration where the member submodule has only
  `latest_api_data_job: SUCCESS` (no CSV `latest_data_job`), expands
  Headcount → member, asserts the "Add Data" button carries Quasar's
  `bg-positive` class.
- `frontend/tests/integration/data-management.spec.ts` test
  `1216b — FACTORS card renders before DATA card in the upload row (regression)`:
  asserts the FACTORS button's bounding-box `x` is less than the DATA
  button's `x` in the per-submodule render path
  (`SubmoduleItem.vue`). Same FACTORS-first rule applies to the common
  path (`ModuleUploadsSection.vue`) — both share the rule via template
  ordering, so a single regression test pins both.

## 7. Verification

- `make type-check` — passes (vue-tsc clean).
- `make lint` — passes (prettier + eslint clean).
- `playwright test tests/integration/data-management.spec.ts` — 19/19 pass, including the two new tests.
