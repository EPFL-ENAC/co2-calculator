---
title: "Issue 2146 — Lock (sub)module activation once the year is open"
status: delivered
issue: 2146
last_updated: 2026-08-25
summary: "Freeze the module/submodule activation toggles in the back-office Configuration page once a year is open to users (is_started), per the 24-08 decision (Option 2). Frontend-only enforcement; allowing mid-year (de)activation again (Option 1) is deferred to post-delivery."
---

# Issue 2146 — Lock (sub)module activation once the year is open

## Context

The results/stats code was written before the "deactivate submodules" feature
existed and assumes the set of active (sub)modules is fixed for a reporting
year. (De)activating a submodule mid-year can therefore produce discrepancies
between stats and results.

**Decision (24-08):** Option 2 — disable, in the frontend, the ability to
(de)activate submodules **and** modules once a year is open to users. Option 1
(reviewing all stats implications so mid-year deactivation becomes safe) is
shifted to a post-delivery enhancement.

## Gate

`year_configuration.is_started` — the flag flipped by the **Open year for
users** button (#857/#1108), read from `useYearConfigStore().config`. Before
the year is opened, the back-office operator can still configure activation
freely; after opening, the activation state is frozen.

## Changes (frontend only)

- `frontend/src/components/molecules/data-management/ModuleConfigSection.vue`
  — module activation `q-toggle` gets `:disable="activationLocked"` where
  `activationLocked = !!yearConfigStore.config?.is_started`, plus an
  explanatory `q-tooltip` on a wrapping `div` (the tooltip must sit on an
  enabled ancestor to fire over a disabled toggle).
- `frontend/src/components/molecules/data-management/SubmoduleItem.vue` —
  same treatment for the submodule activation `q-toggle`.
- `frontend/src/i18n/backoffice_data_management.ts` — new shared key
  `data_management_activation_locked_year_open` (en + fr).

## Deliberately out of scope

- The **Deactivate input form** / **Deactivate CSV upload** checkboxes and the
  threshold input stay editable after opening: they gate how data gets in, not
  which submodules participate in stats/results, and back-office legitimately
  adjusts them mid-year.
- No backend enforcement — the decision explicitly scopes this to the
  frontend. The `PATCH /year-configuration/{year}` endpoint still accepts
  activation changes (admin-only surface).
- Option 1 (safe mid-year deactivation) — post-delivery enhancement, tracked
  in #2146.
