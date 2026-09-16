---
status: delivered
issue: 2818
last_updated: 2026-09-16
summary: Module page and header fit laptop-sized viewports instead of clipping at 1320px.
---

# 2818 — Layout breaks on smaller screens

## Symptom

On a 13"–14" laptop (viewport ≤ ~1400px wide) every card on a module page
(`/…/buildings`, `/…/purchases`, …) was cut off on the right: the module
description ended mid-sentence, the chart's longest bar and axis labels ran
under the pane edge, and the cards touched the sidebar border with no gutter.
The header title `CO₂ Calculator` was also truncated with an ellipsis once the
right-hand toolbar items took their space.

## Root cause

- `ModuleNavigation.vue` set `width: $layout-page-width` (1320px). The module
  page wrapped its content in a `display: grid` with no explicit column, so the
  single auto track grew to the widest item's minimum contribution — that fixed
  1320px — and every sibling card (`width: 100%` of the track) followed. The
  content pane is `overflow-x` clipped, so the excess was hidden, not scrolled.
- The module page used its own `.module-page` wrapper instead of the shared
  `.page-grid` layout class, so it had no horizontal page padding.
- `Co2Header.vue` placed a `<q-space />` after `<q-toolbar-title>`. Both grow
  with flex-basis 0, so the title only got half of the free space and clipped
  at ~1100px.
- Once a submodule section was expanded, its data table (up to ~1280px of
  columns on Buildings, Equipment and Travel) drove the same failure through
  two more auto-sized grid columns: `.page-grid` used a bare `1fr` (minimum
  `auto`, so the track never shrinks below the table) and the submodule list
  in `ModuleTableSection.vue` had no column definition at all.

## Fix

- `ModuleNavigation`: `width: 100%; max-width: $layout-page-width`.
- `ModulePage`: use the shared `.page-grid` class (same 48px vertical padding
  and 24px row gap as before, plus the 16px horizontal gutter every other page
  has) and drop the local `.module-page` styles.
- `Co2Header`: remove the redundant `<q-space />`; the toolbar title already
  flexes into all free space and keeps the right-hand items right-aligned.
- `.page-grid` and `.module-table-section__submodules`: column is
  `minmax(0, 1fr)`, so the cards stay at the pane width and a wide table
  scrolls horizontally inside Quasar's own `.q-table__middle` scroll container
  instead of widening the page.

## Regression test

`frontend/tests/integration/small-screen-layout.spec.ts` renders a module page
at 1024×768 through the research-facilities mocks and asserts no horizontal
overflow in the content pane (collapsed and with every section expanded), no
card wider than the pane, a ≥16px gutter to the sidebar, and an untruncated
header title.

Verified live on every module page with all sections expanded at 1024×768,
1152×720, 1280×800, 1366×768 and 1440×900.

## Out of scope

The module sidebar keeps its fixed 20rem width; it already collapses manually.
Auto-collapsing it below a breakpoint is a separate UX decision.
