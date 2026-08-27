---
status: delivered
issue: 2316
last_updated: 2026-08-27
summary: Simulator Exploration PDF export now shows additional estimated categories in the unit chart, matching the on-screen graph and the headline total.
---

# 2316 — Simulator PDF export missing additional categories

## Problem

In Simulator Exploration, the on-screen results chart has a
"Show additional estimated categories" checkbox that reveals the additional
buckets (commuting, food, waste). The PDF export opens
`SimulationExplorePrintPage.vue` as a separate route, where
`ModuleCarbonFootprintChart` was rendered without the `view-additional-data`
prop. The chart's internal toggle defaults to off and its checkbox is hidden in
print mode (`v-if="!isPrintMode"`), so the exported chart could never show the
additional categories — while the headline total on the same page still
included them (24 t total, empty chart).

## Fix

Pass `:view-additional-data="true"` to `ModuleCarbonFootprintChart` in
`frontend/src/pages/app/SimulationExplorePrintPage.vue`, mirroring what
`ProjectPlannerPrintPage.vue` already does: print always shows the additional
categories, consistent with the total shown above the chart.
