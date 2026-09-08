---
status: delivered
issue: 2464
last_updated: 2026-09-08
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
