---
status: delivered
issue: 2236
last_updated: 2026-08-28
title: "Explorer: show placeholders for missing additional categories"
summary: "Toggling 'additional categories' on in the Explorer chart hid columns for categories absent from the backend response instead of showing them greyed out. Mirrors the existing main-category placeholder logic to fill in missing additional (headcount/buildings) categories too."
---

# Explorer additional-categories placeholders (#2236)

## Problem

On the Explorer page, toggling the "additional categories" checkbox on made
the chart's columns for that category disappear instead of showing, when the
backend response simply had no data for a given category (module untouched).

## What shipped

PR #2331, "fix: show placeholders for additional categories missing from the
backend response", branch `fix/2236`, merged 2026-08-25 (`ac4c1e3ee`).

`frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue` — in
the `datasetSource` computed property (+24 lines): when the additional
toggle is on, builds the set of additional category keys already present in
`breakdownData.additional_breakdown`, and for every key in
`ADDITIONAL_HEADCOUNT_CATEGORIES` / `ADDITIONAL_BUILDINGS_CATEGORIES` not
already present, pushes a placeholder entry (`__validated: false`) so it
renders greyed out instead of vanishing. This mirrors the pre-existing
`MAIN_RESULT_CATEGORIES` placeholder logic just above it in the same file,
now applied to the additional-categories breakdown too.

No dedicated test file was added in this PR.

## Note: mechanism partly reworked since

Commit `18f877fa8` (#2443, "grey home chart icons by access not status",
2026-08-28) later removed the `__hasStats` field from this same placeholder
object as part of switching the greying logic from a status flag to an
access-based check. The `__validated: false` line and the core "fill in
missing additional-category placeholders" logic from #2236 are unaffected by
that follow-up.
