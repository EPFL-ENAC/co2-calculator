---
status: delivered
issue: 2787
last_updated: 2026-11-10
title: "Issue 2787 — Block opening a year while a module is incomplete"
summary: "PATCH /year-configuration/{year} set is_started=true without reading the #1215 incomplete flag, so a stale tab or a direct call could open a year with missing mandatory factors. Opening (PATCH, and POST with is_started) now answers 409 naming the incomplete modules; closing stays allowed. The configurator lists the blocking modules under the greyed-out button."
---

# Issue 2787 — Block opening a year while a module is incomplete

## Problem

The backend computes `incomplete` per module (`_enrich_config_with_incomplete_flags`,
#1215), but `update_year_configuration` flipped `is_started` without reading
it. The frontend button was disabled through `anyModuleIncomplete`, so only
a stale tab or a direct PATCH could open an incomplete year, and the UI
never said which modules blocked it.

The reporters have not yet chosen between "block" and "warn and allow".
This ships "block".

## What shipped

Backend, `backend/app/api/v1/year_configuration.py`:

- `_incomplete_module_names(config, job_lookup)` enriches a copy of the
  config with the latest jobs and the incomplete flags, and returns the
  `ModuleTypeEnum` names of incomplete modules, by id. Disabled modules are
  never incomplete.
- `_raise_if_year_incomplete(db, year, config)` raises 409 with a string
  detail (`Cannot open the year, incomplete modules: headcount, ...`). A
  string, because `frontend/src/api/http.ts` toasts string details only.
- `update_year_configuration` calls it on the closed → open transition
  only, against the config merged with the patch. Closing, and PATCHes on
  an already-open year, are untouched.
- `create_year_configuration` calls it when the payload asks for
  `is_started: true`. The frontend never sends that on create.
- Out of scope: `backend/app/seed/bootstrap_years.py` sets `is_started`
  directly after uploading everything. It is a seed script, not an API path.

Frontend:

- The open-year button moved from `DataManagementPage.vue` into
  `components/molecules/data-management/OpenYearButton.vue` (refactor-only
  commit; `data-testid="open-year-for-users-btn"` kept).
- `yearConfigStore.incompleteModules` lists the modules whose backend
  `incomplete` flag is set, in `MODULES_LIST` order. `anyModuleIncomplete`
  derives from it, still OR'd with the frontend-only reduction-objectives
  rule.
- Under the disabled button, a visible list names the incomplete modules
  (`data_management_open_year_blocked_modules`, en + fr). When only reduction
  objectives block, the list is empty and the existing tooltip explains.

## Tests

- `backend/tests/integration/backoffice/test_open_year_incomplete.py`:
  opening an incomplete year → 409 and `is_started` stays false (the
  regression test); complete year → 200; closing an incomplete open year →
  200; POST with `is_started: true` → 409.
- `frontend/tests/unit/open-year-button.spec.ts`: an incomplete module
  disables the button and is listed; a complete year enables it with no list.
