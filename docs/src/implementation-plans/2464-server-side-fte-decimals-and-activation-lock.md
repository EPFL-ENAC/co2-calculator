---
status: delivered
issue: 2464
last_updated: 2026-09-24
summary: "Two frontend-only guardrails (#2318 FTE one-decimal cap, #2146 activation lock on an open year) had no backend twin, so a direct PATCH, an HR import or a stale tab bypassed them. Both now enforced server-side, with regression tests."
---

# Server-side FTE decimals and activation lock (#2464)

## Problem

- The Headcount form caps FTE at one decimal (#2318), but the DTO validators
  only checked `0 ≤ fte ≤ 1` and the HR import stored `float(raw)` unrounded.
  An imported `0.753` was valid server-side and unsubmittable in the edit form.
- The Configurator greys the activation toggles out once `is_started` is true
  (#2146), but `PATCH /year-configuration/{year}` never read the stored flag.

## Shipped

- `backend/app/modules/headcount/data_entries.py`: `FTE_DECIMALS` reads the
  existing `module_input_decimals(headcount)` constant (the same value the
  frontend's `maxDecimals` is generated from). All four `validate_fte`
  validators reject more decimals than that.
- `headcount_members_api_provider.py`: the HR feed is rounded to
  `FTE_DECIMALS` at transform time — rounding rather than rejecting, because
  the source legitimately carries more precision than the module models.
- `backend/app/api/v1/year_configuration.py`: the PATCH answers 409 when the
  stored year `is_started` and the payload touches a module or submodule
  `enabled` key. Other keys (uncertainty, thresholds, inputs/csv
  deactivation) stay editable, matching the #2146 decision.
- Random seed generator rounds FTE to one decimal.
- Frontend untouched: it already derives the lock from `is_started`; the
  backend is now the one that enforces it.

## Tests

- `tests/unit/modules/test_headcount_schemas.py`: two-decimal FTE rejected on
  member/student create and update.
- `tests/unit/services/data_ingestion/test_headcount_members_api_provider.py`:
  `0.753` → `0.8` at transform.
- `tests/integration/backoffice/test_module_activation.py`: module and
  submodule `enabled` PATCH on a started year → 409 and config unchanged;
  `uncertainty_tag` PATCH still 200.

## Follow-up (2026-09-24): the rejected row was invisible on the module page

Validation testing uploaded a member CSV with `fte=0.888` from the module
page: the row was skipped as designed, but the toast read "CSV sync
completed" with no reason. The job stream, the pipeline console and the
back-office upload card all showed the warning; only the module-page
notifier missed it.

Every ingestion provider persists row errors under `meta.stats.row_errors`
and strips `row_errors` from the meta root, while `ModuleTable.vue` read
`payload.meta.row_errors` off the SSE payload — always `undefined`, so
`formatRowErrorLines` returned no lines and the success branch fired.

- `frontend/src/utils/rowErrors.ts`: `formatJobRowErrors(meta, t)` reads the
  `stats` block and returns the caption and count; the module page uses it.
- `JobUpdatePayload.meta` no longer declares `row_errors` at the root.
- `frontend/tests/unit/csv-row-errors-sse.spec.ts`: a backend-shaped partial
  import yields a caption with the row and reason, a clean one yields none.
