---
status: delivered
issue: 2651
last_updated: 2026-09-03
summary: Planner reports without a reference year no longer resolve their factor year from "the unit's latest Calculator report year" — an ungated tier that could silently land on the current, unpublished year. Removed in favor of the N-1/N-2 fallback #2656 already gave Explore, matching #2631's accepted spec exactly (reference year, then N-1, then N-2). Also fixes a second, still-live gap the first round of frontend wiring missed — ModuleTable's own taxonomy-tree fetch (kind/subkind labels) and the Explorer print page's taxonomy batch fetch both still requested the report's own year.
---

# 2651 — Planner/Explorer requested the wrong year for taxonomy

## Problem

Part 1 of #2651: a Planner section with no reference year set (and, before
#2656/#2657's addendum, no Calculator report either) resolved its factor
year to `yearData.year` — the section's own, often far-future, planning
year — and passed that straight into the taxonomy/options endpoints. #2657's
addendum (see
[`2656-explorer-year-agnostic-sandbox.md`](2656-explorer-year-agnostic-sandbox.md#addendum-2026-09-03-the-resolved-factor-year-wasnt-reaching-the-ui))
fixed the _exposure_ problem — `resolve_factor_year()`'s result now reaches
the frontend as `factor_year` on both `CarbonReportRead` and
`SimulatorPlanYearRead` — and gave Plan reports a fallback tail once
`reference_year` and "the unit's latest Calculator report year" were both
exhausted.

That second tier was the bug, found by live-testing right after merge: for
a unit whose Calculator is on the _current_ year (2026, opened simply by
using the Calculator this year — not necessarily a year with published
factors), a Plan section with no reference year resolved to **2026**, not
N-1 (2025):

```
GET /project-plans/{id}/years   →  {"reference_year": null, "factor_year": 2026}
```

`get_latest_calculator_year(unit_id)` (`CarbonProjectRepository`) returns
`MAX(CarbonReport.year)` for the unit's Calculator reports, **unconditionally**
— it never checked `is_year_started`. A Calculator report is created for
whatever year the workspace happens to be on; that year can itself have no
published factors, exactly the case #2656 exists to avoid. The tier was
legacy behavior that predates #2656/#2651 and was carried forward
unquestioned in the addendum, on top of the new N-1/N-2 tail rather than
replacing it.

It also isn't in the accepted spec. #2631's "Proposed solution n2" (cited
verbatim by the maintainer): _"Project Planner: Factors come from reference
year, fallback to year n-1 (n being current year at date of usage), fallback
n-2."_ Two tiers, not three — no "unit's latest Calculator year" step at
all.

## Decision

**Removed the tier. `resolve_factor_year()`'s `SIMULATOR_PLAN` branch is now
exactly `reference_year → N-1/N-2`, merged into the same branch as
`SIMULATOR_EXPLORE`** (`app/utils/factor_year.py`):

```python
if report.reference_year is not None:
    return report.reference_year
if report.carbon_project_id is not None:
    project = await session.get(CarbonProject, report.carbon_project_id)
    if project is not None:
        if project.carbon_report_type in (
            CarbonReportType.SIMULATOR_PLAN,
            CarbonReportType.SIMULATOR_EXPLORE,
        ):
            return await _resolve_latest_started_year(session, project.created_by)
return report.year
```

Considered gating the tier with `is_year_started` instead of deleting it (so
a unit's real, _confirmed_ historical Calculator year would still be
preferred over a more-recent-but-less-"anchored" N-1). Rejected: not in the
accepted spec, adds a branch nobody asked for, and every case it would help
is already served at least as well by N-1/N-2 — a confirmed Calculator year
is never fresher than the latest confirmed year, only sometimes older.
Simplicity won.

**Dead field cleanup, entailed by the same removal.** `SimulatorPlanRead.default_factor_year`
existed solely to expose this tier's result to the frontend as a _plan-level_
hint (`get_plan`/`list_plans`/`create_plan`/`duplicate_plan`/`_read_with_creator`,
`app/services/simulator_plan_service.py`) — the frontend prop that consumed it
(`PlannerYearSection.vue`'s `defaultFactorYear`) was already deleted in the
#2656/#2651 addendum once the per-year `factor_year` field replaced it. With
the tier gone, the field's own semantics ("the default factor year of plan
years without a reference year") ceases to be true, and nothing reads it —
confirmed via full-repo grep (frontend and tests) before removal, not
assumed. Removed the field, its five populate-sites, and the now-fully-unused
`CarbonProjectRepository.get_latest_calculator_year` repo method.

## Verification

Live-tested against report `40825` (unit 613, plan `11286`, unit's
Calculator on 2026): cleared `reference_year` — `factor_year` was `2026`
before this fix, `2025` (N-1) after, confirmed via `GET
/project-plans/11286/years`.

## Touch points

- `app/utils/factor_year.py` — `SIMULATOR_PLAN`/`SIMULATOR_EXPLORE` merged
  into one branch; docstring corrected (Calculator-year tier never existed
  in the accepted spec).
- `app/services/simulator_plan_service.py` — `_to_read` and its five call
  sites (`list_plans`, `get_plan`, `create_plan`, `duplicate_plan`,
  `_read_with_creator`) drop `default_factor_year`.
- `app/schemas/simulator_plan.py` — `SimulatorPlanRead.default_factor_year`
  removed.
- `app/repositories/carbon_project_repo.py` — `get_latest_calculator_year`
  removed (no remaining caller).
- Frontend: `stores/simulatorPlans.ts`'s `SimulatorPlan.default_factor_year`
  removed. `openapi.d.ts` regenerated.

## Tests

- `tests/unit/utils/test_factor_year.py` — replaced the test pinning the
  old (buggy) "Calculator year wins" behavior with two regression pins for
  the live-found bug: a Plan with no reference year ignores the unit's
  Calculator report year even when that year is the _current_,
  unstarted one (the exact repro), and even when it's an older, _started_
  one (proving the tier isn't gated back in by accident, it's gone).
- `tests/unit/services/test_simulator_plan_service.py`,
  `tests/unit/v1/test_carbon_report.py` — full suite re-run, unaffected
  (neither test file asserted on `default_factor_year` by name; grepped
  before removal to confirm).

## Addendum: two frontend call sites the earlier round missed

Live-tested again after the backend fix above: `GET
/taxonomies/module/buildings/building?year=2051` still fired for report
40823 — whose `factor_year` was correctly `2025` by then. The earlier
#2656/#2651 frontend pass fixed every consumer of
`useEquipmentClassOptions` (the form/inline-select dropdowns), but two more
call sites independently fetch the taxonomy tree and both still used the
raw report year:

- **`ModuleTable.vue`** — `getSubmoduleTaxonomy`, called from three
  near-identical spots (initial expand, locale switch, on-mount-if-already-
  expanded) to resolve kind/subkind _labels_ for the table's own rows
  (distinct from the form's dropdown options). All three passed
  `String(props.year)`. Extracted into one `fetchTaxonomyIfNeeded()` helper
  — DRYs up the duplication and fixes all three at once — using
  `props.factorYear`, skipped entirely when `null` (same as every other
  factorYear consumer).
- **`useSimulationExplorePrintData.ts`** — the Explorer print page's batched
  taxonomy fetch (`getSubmoduleTaxonomiesBatch`) used `workspaceStore.selectedYear`
  directly. Now reads `workspaceStore.selectedCarbonReport?.factor_year`,
  populated by `initWorkspaceFromRoute()` (which runs first and calls
  `selectSimulatorExploreCarbonReport`) before `fetchAllData()` uses it.

Checked and confirmed unaffected: `TaxonomyBatchHarness.vue` /
`TaxonomyLangHarness.vue` (existing component tests) call
`getSubmoduleTaxonomy`/`getSubmoduleTaxonomiesBatch` directly against the
store, bypassing `ModuleTable.vue` entirely — neither test's coverage
touches the changed call sites. `useProjectPlannerPrintData.ts` (Planner's
own print page) was checked too and doesn't independently fetch the
taxonomy tree — no equivalent gap there.

## Addendum: the generic by-id GET also left `factor_year` null

Also spotted live: `GET /carbon-reports/{id}` — a route no frontend code
path actually calls, but the one general-purpose "fetch this report" GET
the API exposes — never populated `factor_year` either, unlike the
dedicated Explore GET/POST. `_explore_report_read` was Explore-specific in
name only (nothing in its body is), so renamed to `_carbon_report_read` and
reused here too. Report 40834 (`reference_year: null`) went from
`factor_year: null` to the correctly-resolved `2025`.

## Out of scope

Part 2 of #2651 (taxonomy subkind nodes not deduplicated,
`get_taxonomy_with_etag`) is a separate, unrelated bug — not touched here.
