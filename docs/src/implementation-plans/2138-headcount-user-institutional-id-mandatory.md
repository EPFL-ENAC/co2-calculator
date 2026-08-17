---
status: delivered
issue: 2138
last_updated: 2026-08-17
title: "Headcount: user_institutional_id Mandatory Again"
summary: "Reverts #951's decision to make HeadCountCreate.user_institutional_id optional — success criteria changed, and it must be mandatory again at creation, backend and frontend."
---

# Headcount: `user_institutional_id` Mandatory Again

## Problem

`docs/src/implementation-plans/951-edit-rights-per-dataset-permissions.md`
made `HeadCountCreate.user_institutional_id` optional (`str | None = None`)
so a manually-added member without a known SCIPER could be filled in later.
Success criteria changed: the field must be mandatory at creation again, in
both backend and frontend.

## Change

- `backend/app/modules/headcount/data_entries.py`: `HeadCountCreate.
user_institutional_id` back to `str` (was `str | None = None`). Its
  `field_validator` is restored as `mode="after"` rather than the pre-#951
  `mode="before"` — pydantic type-checks the field first, so a `null` or
  non-string value now yields a clean 422 instead of an `AttributeError`
  from `None.strip()` (matches `validate_name`'s pattern two lines above).
  `HeadCountUpdate` is untouched — it's a partial-update DTO where every
  field is optional by design, independent of creation mandatoriness.
- `frontend/src/constant/module-config/headcount.ts`: `user_institutional_id`
  field gains `required: true` (the generic `ModuleForm.vue` required-field
  check already handles `text`-type fields via `i.required`; no dedicated UI
  code needed).
- `backend/tests/unit/modules/test_headcount_schemas.py`: moved
  `uid-missing` back to the invalid-permutation list, added `uid-none`
  there (was untested pre-#951; now pins the `mode="after"` behavior above),
  dropped the `uid-omitted` valid case added by #951.

## Not changed

- CSV ingestion and the Tableau API provider (`headcount_members_api_provider.py`)
  already skip/reject rows with a missing SCIPER upstream of
  `HeadCountCreate`, so they're unaffected.
- `isCompleteHeadcount` in `ModuleTable.vue` (row-completeness badge) checks
  a stale `row.sciper`/`row.function` key pair that predates the
  `user_institutional_id`/`sius_code` rename — pre-existing, out of scope
  here.
- `HeadCountUpdate.user_institutional_id` stays `str | None = None`, and an
  explicit `user_institutional_id: null` in a PATCH still clears it (only
  `""`/whitespace are rejected) — a partial edit can blank a field that's
  mandatory at creation. Flagging this, not fixing it here: it's a
  pre-existing gap (predates #951), and locking it down is an update-path
  design call, not part of "mandatory again at creation".
- `frontend/src/types/api/openapi.d.ts` is not regenerated: the create/update
  endpoint (`POST/PATCH .../modules/{module_id}/{submodule_id}`) takes a raw
  `item_data: dict`, not a typed body model, so `HeadCountCreate` was never
  part of the OpenAPI schema to begin with — confirmed no `HeadCountCreate`
  or `user_institutional_id`-on-headcount entry exists in the committed
  `.d.ts`. (The committed `openapi.snapshot.json`/`openapi.d.ts` pair is
  otherwise already far behind the live schema — regenerating it pulls in a
  ~1200-line unrelated diff; that staleness predates this change and is out
  of scope here.)
