---
status: proposed
issue: 659
last_updated: 2026-07-07
title: "CSV upload: surface per-row validation errors with readable messages"
summary: "Turn raw pydantic ValidationError dumps into readable field-level messages, and fix the upload-card UI which currently never renders them."
---

# CSV upload: surface per-row validation errors with readable messages

## Problem

Issue body (FR): "todo: meilleur message d'erreur lorsque factor non valide (str/float) ou date non valid (l'erreur ne remonte pas dans l'interface)" — better error message when a factor value has a type mismatch (str/float) or a date is invalid, because right now the error doesn't reach the UI.

Two independent bugs, both confirmed in code:

1. **Raw pydantic dump as the error message.** Both CSV row-validation paths call `handler.validate_create(payload)` (`backend/app/services/data_ingestion/base_csv_provider.py:1278` for data-entries, `backend/app/services/data_ingestion/base_factor_csv_provider.py` `_process_row` for factors) inside a bare `except Exception`, and format it as `f"Validation error: {validation_error}"`. For a pydantic `ValidationError` this stringifies to a multi-line technical dump ("1 validation error for FactorCreate\nco2_factor\n Input should be a valid number... [type=float_parsing, input_value='abc', input_type=str]") — unreadable for an operator uploading a CSV, and not localized.

2. **The message never reaches the UI for the main upload widget.** There are two different CSV-upload surfaces in the frontend:
   - `ModuleTable.vue` (`formatRowErrors`, lines 570-598) _does_ read `payload.meta.row_errors` / `row_errors_count` and renders one line per row ("row X: reason") in a `$q.notify`.
   - The primary "Add data" / "Add factors" cards (`UploadCard.vue` + `useUploadCard.ts`, used via `UploadCardFactors.vue` and the data-management upload flow) use `getErrorDetails()` (`frontend/src/composables/useUploadCard.ts:130-143`), which only reads `job.status_message` and `meta.error` (a job-level failure key, only set when the whole job throws) — it never reads `meta.row_errors`. The tooltip in `UploadCard.vue:317-331` then dumps the raw `stats` object with `v-for="(value, key) in errorDetails.stats"`, so the `row_errors` key renders as `row_errors: [object Object],[object Object]` — Vue's default array-of-objects stringification. The actual per-row reason ("Validation error: ...") never appears anywhere in this widget. This is the upload flow issue #659 is about.

## Design

**Backend** — replace the generic `except Exception` around `validate_create()` in both row-processing loops with a `pydantic.ValidationError`-specific branch that walks `validation_error.errors()` and builds one short message per field: `f"{err['loc'][-1]}: {err['msg']} (got {err['input']!r})"`, joined with `; `. This turns the dump into e.g. `co2_factor: Input should be a valid number (got 'abc')` / `date: Input should be a valid date or datetime (got '2026-13-40')` — still pydantic's wording (no new i18n layer, no per-field custom copy — that's scope creep for a "nice to have"), but on one line and free of the `type=...` / `input_type=...` noise. Non-`ValidationError` exceptions keep the existing `f"Validation error: {validation_error}"` fallback.

**Frontend** — extract the row-error formatting already written once (`ModuleTable.vue`'s `formatRowErrors`) into a shared helper (e.g. add to `useUploadCard.ts` or a small `src/utils/rowErrors.ts`), and use it in `getErrorDetails()` so the tooltip built in `UploadCard.vue:317-331` shows real reasons instead of the raw stats dump. Concretely: `getErrorDetails` gains a `rowErrors: string[]` field (formatted `row N: reason`, capped like `MAX_DISPLAYED_ROW_ERRORS` in `ModuleTable.vue`), and `UploadCard.vue`'s tooltip renders that list instead of `v-for` over `errorDetails.stats`. Drop `row_errors`/`row_errors_count` from the raw stats dump loop so they don't double-render as `[object Object]`.

## Steps

- [ ] Backend: catch `pydantic.ValidationError` in `base_factor_csv_provider.py::_process_row`'s `validate_create` call and format a readable per-field message (see Design); keep the generic fallback for other exceptions.
- [ ] Backend: apply the same fix at `base_csv_provider.py:1278`'s `validate_create` call site (data-entry CSV path — same `float_parsing`/`date_parsing` failure modes for `factor`/`date` columns).
- [ ] Frontend: extract `formatRowErrors` (from `ModuleTable.vue`) into a shared helper reusable from `useUploadCard.ts`.
- [ ] Frontend: wire `getErrorDetails()` (`useUploadCard.ts:130-143`) to expose formatted row errors, and update `UploadCard.vue`'s error tooltip (`:317-331`) to render them instead of dumping `errorDetails.stats` (excluding `row_errors`/`row_errors_count` from that dump).
- [ ] Add/extend a backend unit test asserting a bad-float and a bad-date CSV row produce the new readable `row_errors` reason string (existing suites: `tests/unit/services/data_ingestion/test_base_factor_csv_provider.py`, `test_base_csv_provider.py`).
