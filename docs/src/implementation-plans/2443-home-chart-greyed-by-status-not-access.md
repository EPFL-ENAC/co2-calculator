---
status: delivered
issue: 2443
last_updated: 2026-08-28
title: "Home chart module icons greyed by access, not status or data"
summary: "The Home chart's icon axis greyed modules out based on validation status and data presence (a validated module with no stats bucket rendered greyed as 'not validated', and any module stayed greyed until it had data). Reworked the rule: visible ⇔ activated in the backoffice, greyed ⇔ the user lacks view/edit access; module status and stats presence have no influence. Frontend-only."
---

# Home chart icons greyed by access, not status/data (#2443)

## Problem

On the Home page, module icons under the emission-breakdown chart were greyed
out as "not validated" even when the module WAS validated, and modules stayed
greyed until they had computed stats. Reported for Process Emissions but
module-wide.

## Decided behavior

- **Visible in chart** ⇔ module activated in the backoffice year config.
- **Greyed out** ⇔ the user's role lacks view/edit access to the module — in
  practice only standard users, on everything except their own-scoped modules
  (professional travel, external cloud & AI).
- **Status (not started / in progress / validated) and data presence never
  grey or hide an icon.**

Scope decisions confirmed with the maintainer:

- Bars stay validated-only (an unvalidated category's bar is zeroed and its
  tooltip keeps "Validate {module} to see results") — untouched.
- The Results page keeps its deliberate validated-only display — untouched.
- HomePage's `hasValidatedData` empty-state gate stays — untouched.

## Root cause

`frontend/src/composables/useModuleAvailability.ts` — `isModuleFullyAvailable`
required `hasStats` (data presence) and EDIT permission besides backoffice
activation. A validated module with no stats bucket has its key in
`validated_categories` but no `module_breakdown` row, so it fell into the
chart's grey placeholder branch; VIEW-only users were greyed everywhere.

## Change (frontend only)

- `frontend/src/composables/useModuleAvailability.ts`: dropped the `hasStats`
  parameter; the rule is now `isModuleVisible(module) &&
canUserAccessModule(module)` (VIEW or EDIT, matches unit- and own-scoped
  keys).
- `frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue`:
  icon-axis `enabled` no longer feeds `__hasStats` in (the marker was removed
  as dead — the icon axis was its only consumer). Validated-only bar zeroing,
  the unvalidated tooltip, and `enforceModuleActivation` filtering are
  unchanged.
- Regression tests: `frontend/tests/integration/home-module-visibility.spec.ts`
  on the reworked scenario in
  `frontend/tests/integration/setup/home-module-visibility-mocks.ts` (that
  mock existed but no spec consumed it; its dead import in
  `backoffice-config.spec.ts` was removed). The scenario pins all four rules:
  validated-without-stats clickable (#2443), not-started clickable,
  no-access greyed even when validated with stats, backoffice-disabled hidden.
  Verified to fail without the fix.
