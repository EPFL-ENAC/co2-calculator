---
status: proposed
issue: 1403
last_updated: 2026-07-07
title: "BackOffice Configuration — integration test suite for Cahier de recette"
summary: "Automate the manual QA checklist for year init, module/sub-module activation, uploads, and pipeline tracking."
---

# 1403 — BackOffice Configuration integration test suite

## Problem

This is a manual QA checklist with no automated coverage — each item below
should become an integration test. The checklist comes from the reporter's
Cahier de recette (test-acceptance spreadsheet) and spans backoffice access
control, year initialization, per-module/per-sub-module activation and
upload behavior, and the Pipeline Operations view. None of it currently has
regression coverage; a manual pass is the only signal today, so it silently
rots as the backoffice config UI changes.

## Design

#1403 is a tracker/epic. Its individual bug items are separately tracked
issues (#1204, #1415, #1433, #1463, #1491, #1523, #1545, #1558, and others
filed as sub-issues) — each fix ships in its own PR, against its own issue.
**This plan's scope is only the integration test suite** that encodes the
checklist below as automated tests; it does not re-fix any sub-issue, and it
must not silently paper over an unfixed sub-issue with a skipped/xfail test
— unresolved items get an explicit `pytest.mark.skip(reason="#issue")` /
`test.fixme` pointing at the blocking issue, not a deleted assertion.

Test placement follows existing suites:

- **Backend** (`backend/tests/integration/`, new `backoffice/` package,
  mirroring `data_ingestion/` and `v1/`): permission gating, year-creation
  bounds, Accred sync trigger, module/sub-module activation persistence,
  factor/reference upload validation pipeline (per data-description doc +
  #1415/#1545), "Incomplete" status computation. Backend is source of
  truth for status/validation logic, so these are the load-bearing checks —
  API-level, not UI-level, wherever the behavior is backend-computed.
- **Frontend** (`frontend/tests/integration/`, new `backoffice-config.spec.ts`
  - `pipeline-operations.spec.ts`, alongside `data-management.spec.ts`):
    Playwright specs for what's genuinely UI-only — greyed-out
    module/sub-module rendering for a regular user, button disabled/enabled
    state + informative message, upload step-by-step progress feedback,
    factor-box green state, download-arrow retrieval, Pipeline Operations
    view progress tracking. Use `setup/` mocks pattern already established
    (`data-management-mocks.ts`) rather than hitting a live backend.
- **Access control** (`Calco2.backoffice.admin` gate) belongs with the
  existing permission suites: `backend/tests/unit/utils/test_permissions.py`
  / `backend/tests/integration/v1/test_permission_scope_e2e.py` and
  `frontend/tests/unit/permission.spec.ts` — extend, don't fork a new file,
  per "reuse existing patterns."

No new test framework, no new CI job — reuse `uv run pytest` and
`npx playwright test` / existing `rtk playwright test` wiring.

## Steps

- [ ] **Access**
  - [ ] Backend: non-`Calco2.backoffice.admin` role gets 403 on config-tab
        endpoints (extend `test_permission_scope_e2e.py` or `test_backoffice.py`)
  - [ ] Frontend: config tab route hidden/blocked for a user without the
        permission (extend `permission.spec.ts`)
- [ ] **Year initialization**
  - [ ] Year creation rejected for year < 2025 or > current year (backend)
  - [ ] Creating year 2025 triggers Accred unit sync; confirmation surfaces
        once complete (backend job assertion + frontend confirmation message)
  - [ ] All modules show "Incomplete" on config homepage with no data
        uploaded (frontend)
  - [ ] "Ouvrir l'année pour les utilisateurs" disabled + informative
        message while incomplete; enabled only once every module is fully
        loaded (frontend, backend status computation)
- [ ] **Common module behavior** (parametrize across modules where the
      backend behavior is generic; one representative module for
      UI-rendering specs)
  - [ ] Module deactivation greys out module in calculator for a regular
        user (frontend)
  - [ ] Re-activating a module preserves previously uploaded data (backend)
  - [ ] Sub-module deactivation greys/blocks it in calculator (frontend)
  - [ ] Saisie (form) deactivation/reactivation per sub-module reflected in
        calculator (frontend)
  - [ ] Uncertainty field renders correct options (frontend)
  - [ ] Threshold field rejects negative values, accepts positive
        int/decimal (frontend form validation + backend if also enforced
        server-side)
  - [ ] Uploading a factor file → green box, no error (frontend + backend
        upload endpoint)
  - [ ] Download arrow retrieves the last uploaded file (frontend/backend)
  - [ ] "Incomplete" tag persists at sub-module/module level until all
        required files (factors, references where applicable) uploaded
        (backend status computation, primary; frontend rendering)
  - [ ] "Incomplete" tag clears once upload complete (same, inverse case)
  - [ ] Upload shows interactive step-by-step progress feedback (frontend)
  - [ ] Data validation pipeline matches data-description doc + #1415,
        also covers #1545 (backend, `backend/tests/integration/backoffice/`)
  - [ ] After full upload of all (sub)modules, "Ouvrir l'année pour les
        utilisateurs" becomes active (backend status + frontend gating,
        end-to-end)
- [ ] **Pipeline Operations view**
  - [ ] View correctly tracks upload progress for all modules (frontend,
        `pipeline-operations.spec.ts`, reusing patterns from
        `pipeline-diagnostic-tooltip.spec.ts`)
- [ ] Wire new backend package into `backend/tests/integration/__init__.py`
      discovery if required; confirm `uv run pytest` and
      `rtk playwright test` both pick up the new specs
- [ ] Link each test back to its sub-issue in a comment where the test
      guards a specific fix (#1204, #1415, #1433, #1463, #1491, #1523,
      #1545, #1558) so a skipped/xfail test is traceable to the blocking
      issue
