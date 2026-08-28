---
status: proposed
issue: 2494
last_updated: 2026-08-28
title: "Backend-authoritative module activation for simulator report types"
summary: "Explorer showed a greyed 0 bar for back-office-deactivated modules (#2465, fixed as a frontend-only patch in #2492). Investigation found the backend has no concept of back-office activation at all for is_simulator report types, and Planner has the identical bug, unmasked. Lays out three fix options and the two decisions (staleness, merge semantics) a maintainer needs to make before implementation."
---

# 2494 — Backend-authoritative module activation for simulator report types

## Problem

[#2465](https://github.com/EPFL-ENAC/co2-calculator/issues/2465): Simulation Explorer rendered a greyed `0` bar for a category whose
module/submodule is deactivated in back-office config for the simulated year,
instead of hiding it. Fixed in [#2492](https://github.com/EPFL-ENAC/co2-calculator/pull/2492) by removing Explorer's
`enforce-module-activation="false"` opt-out — a verified, minimal, low-risk
patch (see "What shipped" below). This document is the deeper investigation
that patch surfaced, and is not itself implemented yet.

## What shipped in #2492 (context, not part of this plan)

`ModuleCarbonFootprintChart.vue`'s `enforce-module-activation` prop (default
`true`) filters `datasetSource` against `yearConfigStore`-derived activation
state via `isCategoryModuleActive` (`composables/results/useModuleCategoriesAvailability.ts`).
Explorer's two pages (`SimulationExplorePage.vue`, `SimulationExplorePrintPage.vue`)
set this to `false` with no compensating filter — the only opt-out with no
justification, since (unlike Reporting/BackofficeResultsPrint, genuine
multi-unit aggregates) Explorer is single-unit/single-year and already loads
`yearConfigStore` for the correct simulated year before the chart mounts.
Removing the opt-out was verified safe: `frontend/tests/integration/simulator-explore.spec.ts`
27/28 passing on a clean rebuild post-merge (the 1 failure,
"simulation report opens, is readable and consistent with the page", is
pre-existing on `dev`, unrelated to activation filtering, confirmed
independently on a clean baseline).

## The deeper problem this plan addresses

**The backend has no concept of back-office activation for `is_simulator`
report types at all.**

`CarbonReportModule.is_active` (`backend/app/models/carbon_report.py:154-163`)
is the _Simulator Plan_ "Active" checkbox — a per-report, per-user toggle,
documented as always `true` for Calculator/Explore modules. It is applied at
the call sites (`recompute_report_stats_many`, `recompute_report_progress`,
`carbon_report_service.py:503-511, 547-549`) as `[m for m in modules if
m.is_active]`, before `_build_report_stats` ever runs. It is semantically
unrelated to back-office (`YearConfiguration`) activation.

Inside `_build_report_stats` (`carbon_report_service.py:78-138`), the only
other activation-adjacent check is:

```python
validated_module_type_ids = {
    module.module_type_id
    for module in modules
    if is_simulator or module.status == ModuleStatus.VALIDATED
}
```

For `is_simulator=True` reports (Explore, Plan), `is_simulator` short-circuits
this — **every module type present in `modules` counts as validated,
unconditionally.** `create_all_modules_for_report` creates one
`CarbonReportModule` row per module type for every report, so a back-office
deactivated module always has a row and always lands in `validated_buckets`.
`merge_report_stats` (`backend/app/utils/report_stats.py:220-222`) then unions
`validated_buckets` across a Planner plan's per-year reports, diluting this
further.

Grepped the entire backend: **zero** references to `YearConfiguration` in
`carbon_report_service.py`, `carbon_report.py` (model/schema/API),
`carbon_report_module_service.py`, or `report_stats.py`. The report-building
path is completely disjoint from back-office activation state.

### Correction to #2465's original evidence: Planner is not protected

#2465 assumed Planner was safe because `active-categories-only="true"`
(`ProjectPlannerPage.vue`, `ProjectPlannerPrintPage.vue`) filters via
`isCategoryValidated()` → `validated_categories`. Per the above,
`validated_categories` for `is_simulator` reports is unconditional — this
filter cannot and does not distinguish a back-office-deactivated module from
an active one. **Planner has the identical bug, unmasked, not mitigated.**

### Where back-office activation actually lives

- Storage: `YearConfiguration` (`backend/app/models/year_configuration.py:37-60`),
  keyed by `(year, provider)` — not unit-scoped. `enabled` flags live in
  `config["modules"][module_key]` / `[...]["submodules"][sub_key]`
  (`schemas/year_configuration.py:359, 418`).
- Served by `GET /year-configuration/{year}` (`api/v1/year_configuration.py:578-615`),
  scoped to `(year, current_user.provider)`.
- Read by the frontend into a **single** `useYearConfigStore` ref
  (`stores/yearConfig.ts:191`, populated by `fetchConfig(year)`) — no
  per-year cache. `isModuleVisible`/`isSubmoduleVisible` (lines 500-517) read
  straight off that one ref, and fail **closed** (`?? false`) when it hasn't
  loaded the right year.

### The backend has what it needs, at any report's build time

`CarbonReport.year` is always populated, including for Explore
(`create_explore` sets `year=reference_year`). `Unit.provider` is reachable
via `CarbonReport.unit_id`. `(report.year, unit.provider)` is a well-defined
join key into `YearConfiguration` for any report, at any simulated year.

There's already a working precedent for this exact join:
`build_home_year_configuration` (`api/v1/workspace_home.py:88-112`, called
from `get_workspace_home`), which fetches `YearConfiguration` for
`(year, provider)` and ships it alongside `report.stats` — but only for the
single-report Home page, and it hands the raw config to the frontend rather
than filtering/tagging anything server-side.

One divergence to resolve deliberately: `workspace_home.py` resolves
`provider` from `current_user.provider` (the viewer). For a report-correct
join independent of viewer identity — Planner/Explorer/Reporting all view
reports that may not belong to the viewer — `Unit.provider` is the more
defensible source.

### The chart-side blocker every option must clear

`ModuleCarbonFootprintChart.vue`'s `datasetSource` computed builds
`missingPlaceholders` for every entry in the hardcoded `MAIN_RESULT_CATEGORIES`
list (lines 654-663) absent from `breakdownData.module_breakdown`
(lines 665-680, 684-703 for "additional categories"), merges them into the
dataset, and **only then** applies the `enforceModuleActivation` filter
(lines 740-753).

**This means a backend fix that simply omits an inactive module's bucket from
the stats response is a proven no-op** for this chart: any of the 8
`MAIN_RESULT_CATEGORIES` absent from `module_breakdown` gets a zero-value
placeholder re-injected regardless of _why_ it's absent — already observable
today via the unrelated `excludeModules` mechanism
(`ResultsPage.vue:158-165`, `emissionStatsAdapter.ts:203`), which drops
`research_facilities` from `stats.buckets` yet the chart re-injects it as a
placeholder anyway.

`CarbonFootPrintPerPersonChart.vue` has no equivalent placeholder logic — it
only ever renders keys present in `perPersonBreakdown`, so omitting a bucket
_would_ work for that chart specifically.

### Consumer map

| Consumer                                                                        | `enforce-module-activation` | `active-categories-only`          | Shape                                                                                         |
| ------------------------------------------------------------------------------- | --------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------- |
| `HomePage.vue`                                                                  | unset → **true**            | —                                 | Single unit/year, Calculator                                                                  |
| `ResultsPage.vue`, `ResultsPrintPage.vue`                                       | unset → **true**            | —                                 | Single unit/year, Calculator                                                                  |
| `SimulationExplorePage.vue`, `SimulationExplorePrintPage.vue`                   | **true** (fixed, #2492)     | —                                 | Single unit, single simulated year                                                            |
| `ProjectPlannerPage.vue`, `ProjectPlannerPrintPage.vue`                         | **false**                   | **true** (ineffective, see above) | Multi-year aggregate via `GET /project-plans/{id}/aggregate-stats` → `merge_report_stats`     |
| `PlannerPrintYearPage.vue`                                                      | **false**                   | **true** (ineffective)            | Nominally single-year, rendered inside a multi-page print doc sharing one store ref           |
| `ReportingPage.vue`, `ReportingPrintPage.vue`, `BackofficeResultsPrintPage.vue` | **false**                   | —                                 | Multi-unit backoffice aggregate — genuinely can't use a single-year store, documented in-code |

Net: every `is_simulator` consumer either opts out or uses an ineffective
filter. Only Calculator-report consumers get real filtering today, and only
because those pages happen to load the correct single year into the shared
store.

## Options

### (a) Read-time enrichment

Join `YearConfiguration` for `(report.year, unit.provider)` in
`CarbonReportService.get` / `get_by_unit_and_year` / `get_explore`
(`carbon_report_service.py:362-420, 274-291`) after loading the report,
inject a computed activation signal into the response. Additive — `stats` is
already an untyped `dict` (`schemas/carbon_report.py`), so nesting inside it
needs no Pydantic migration.

- **Pros**: no staleness, computed fresh per request; reuses an understood
  pattern.
- **Cons**: touches every GET path separately (single report, workspace home,
  plan aggregate-stats, backoffice reporting) unless centralized into a
  shared helper (`year_config_service.py` looks like the right home); needs a
  submodule-level bucket→submodule mapping that doesn't currently exist
  server-side, to match `isCategoryModuleActive`'s two-level check; one extra
  PK-lookup query per single-report GET.

### (b) Write-time tagging — recommended

Extend `_build_report_stats` to accept the report's `(year, provider)`-derived
`YearConfiguration.config`, compute an activation-aware bucket list alongside
`validated_buckets` at recompute time. Additive JSON field.

Because `merge_report_stats` already unions `validated_buckets` across a
plan's per-year reports, matching union/intersection logic there (see
decision 2 below) makes this flow to Planner's multi-year aggregate without
touching any frontend opt-in/opt-out prop — each per-year report already
carries its own year, so the per-report tag stays year-correct even after
merging.

- **Pros**: single computation point (the one write path shared by
  Calculator/Explore/Plan); structurally fixes Planner, not just Explorer;
  no schema migration.
- **Cons**: staleness (decision 1 below).

### (c) Omit inactive buckets entirely

The literal reading of "have the backend omit the bucket." **Proven a no-op
for the main chart alone** (see placeholder-injection above). Works for
`CarbonFootPrintPerPersonChart` and for any category outside
`MAIN_RESULT_CATEGORIES`. Only worth pursuing combined with (a) or (b) — used
alone it's strictly worse, since it removes information (a)/(b) would
otherwise use to distinguish "no data yet" from "deactivated."

Every option requires touching `ModuleCarbonFootprintChart.vue`'s
placeholder-injection block (lines 665-716) regardless of backend approach —
it's the actual gate that defeats a naive "just omit the data" fix.

## Decisions needed before implementation

1. **Staleness** (matters for (b), and for any write-time approach): nothing
   today recomputes `CarbonReport.stats` when `YearConfiguration` changes
   (confirmed no cascade in `update_year_configuration`). Explore self-heals
   via its TTL delete-and-recreate path (`EXPLORE_TTL_SECONDS`,
   `api/v1/carbon_report.py:134-143`); Calculator/Plan reports have no
   equivalent and could show stale activation state indefinitely until the
   report's own data is next edited. **Accept as a documented tradeoff, or
   add a recompute-on-config-change job (real additional scope)?**
2. **Merge semantics**: if a module was active in year 1 of a plan but
   deactivated in year 2, should `merge_report_stats`' union treat the merged
   aggregate as active (union) or inactive (intersection)?

## Recommendation

(b), accepting the staleness tradeoff as documented rather than solving it in
the same change — it's the only option that structurally fixes Planner
without new per-page frontend opt-in/opt-out props, and staleness is bounded
(only affects reports whose year config changed since last recompute, self
corrects on next edit).

## Status

Proposed. Not implemented. Filed as
[#2494](https://github.com/EPFL-ENAC/co2-calculator/issues/2494) pending a
decision on the two points above.
