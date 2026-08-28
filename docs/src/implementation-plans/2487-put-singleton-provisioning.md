---
status: delivered
issue: 2487
last_updated: 2026-08-28
summary: Replace the explorer's GET-404-POST provisioning pair with one idempotent PUT (a new ExploreProvisioningWorkflow, ADR-014's first workflow); delete the lazy Calculator-project get-or-create from CarbonReportService.create/bulk_upsert and provision it explicitly in unit_sync
---

# 2487 — PUT singletons for explore/calculator provisioning

## Problem

`frontend/src/stores/workspace.ts` provisioned the Simulator Explore
sandbox with a client-orchestrated GET → catch 404 → POST pair: two round
trips, the backend's "does this exist" decision left to frontend control
flow, and — because two tabs or a double-click both see 404 and both
POST — the exact race #2483/#2484 had to SAVEPOINT-guard. Separately,
`CarbonReportService.create`/`bulk_upsert` lazily created the unit's
Calculator `carbon_projects` row as a side effect of creating a report — a
write the caller never asked for, with nobody owning the project row's
lifecycle (ADR-014's "hidden side-effect write").

ADR-014 ([`014-backend-layering-workflows.md`](../architecture-decision-records/014-backend-layering-workflows.md))
names this issue as its first real consumer: existence is an explicit
workflow step, never a branch discovered mid-request, and crossing
aggregates (CarbonProject, CarbonReport, CarbonReportModule) belongs in a
workflow, not smeared across a one-aggregate service.

## Decision

**Explore — one idempotent PUT, backed by a new workflow.**
`PUT /v1/carbon-reports/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/`
replaces the old POST at the same path; the frontend calls it
unconditionally. `ExploreProvisioningWorkflow.ensure()` is the one place
that decides "does this exist" — it calls `CarbonReportService.get_explore`
(read) then, if missing, `CarbonReportService.create_explore` (the
existing #2483-guarded project+report+modules create) and owns the commit
itself (workflows commit, services/repos never do). `create_explore` and
`get_explore` are left as they were — already correctly cross-aggregate and
covered by 15+ existing tests; the workflow is the new explicit "existence"
step ADR-014 asks for, not a rewrite of already-guarded internals. Always
returns 200 (create vs. return-existing isn't distinguished — nothing
downstream reads the status code differently, and a `was_created` flag
would be unused plumbing).

**The GET route stays, unchanged in shape.** `resolveCarbonReportId` in
`frontend/src/stores/modules.ts` is a genuine read-only consumer (no create
fallback) hit on cache-miss from `ModuleTable`/`ModuleCharts`/
`HeadcountMemberSelect`/print composables. "No backward-compat" targets the
GET-404-**POST** _provisioning_ pair specifically — only POST is deleted.
Its TTL-refresh-scheduling logic (`_refresh_explore_background`, unchanged)
is now shared with PUT via one extracted helper
(`_schedule_explore_refresh_if_stale`) so staleness is defined once; PUT
needed it too because it now runs on every explore-page mount, the same
position the old GET-first flow occupied.

**Path unchanged: `/simulator/explore/...`, not the issue's shorthand
`/explore/...`.** Mirrors the existing GET/POST path exactly — renaming it
would be unrelated churn with no functional benefit, and "mirror, don't
invent" favors matching the established segment.

**Calculator project — provisioned explicitly in `unit_sync`, not lazily.**
`CarbonReportService.create`/`bulk_upsert` no longer self-provision a
missing Calculator project. `create()` still resolves a `None
carbon_project_id` (the `POST /carbon-reports/` shape most callers use),
but read-only now — `_get_project` only, no `_create_project` fallback — and
raises `ValueError` naming the unit and the remedy ("run unit sync") when
none exists. `bulk_upsert()` now requires every item's `carbon_project_id`
already resolved and raises if not. New
`CarbonReportService.ensure_calculator_projects(unit_ids) -> dict[int, int]`
is the explicit provisioning step, reusing the existing #2483
SAVEPOINT-guarded `_get_project`/`_create_project`; `unit_sync_handler`
(`app/tasks/unit_sync_tasks.py`) calls it once per sync run, before
building the year's `CarbonReportCreate` batch, at the
"create_carbon_reports" phase where per-unit-year setup already happens.
This is a
single-aggregate operation (`CarbonProject` only) staying inside
`CarbonReportService` — no workflow forced onto a single INSERT, per
ADR-014's own scope guidance. `year_configuration.py` (year-config
creation) does **not** provision projects itself: it only fires the
`unit_sync` job, which is where units actually become known.

**Accepted trade, flagged for the maintainer:** a genuinely new unit whose
Calculator report is created (or CSV-ingested,
`base_csv_provider.py:MODULE_PER_YEAR`) _before_ any `unit_sync` run for it
now fails loudly (`ValueError` → job ERROR / 500) instead of silently
self-provisioning. Every production caller was audited
(`workspace_home.py` is read-only and already 404s;
`base_tableau_api_provider.py` is read-only by its own comment; only
`base_csv_provider.py`'s per-row fallback and `POST /carbon-reports/` call
`create` with no project). This matches "no silent fallbacks," but is a real
behavior change worth the maintainer's eyes if it surfaces in practice.

## Scoped out

- **Splitting `CarbonProject` handling out of `CarbonReportService`** into
  its own one-aggregate service. ADR-014: existing service webs migrate
  opportunistically, not in a big-bang refactor.
- **A Postgres-testcontainer concurrency test for the PUT.** The #2483
  SAVEPOINT guards already have unit coverage for this exact race
  (`test_create_explore_project_race_returns_winner`,
  `test_create_explore_report_race_returns_winner`); the PUT route doesn't
  change that data-layer belt, so a new integration test would exercise
  the same guard a second time.
- **`repo.bulk_upsert`'s `ON CONFLICT DO NOTHING` returning only inserted
  rows`** and **`seed_helper.get_carbon_report_module_id`** (confirmed zero
  callers). Both pre-existing, unrelated to this issue.
- **Regenerating `frontend/src/types/api/openapi.d.ts`.** Nothing
  statically imports the explore path's generated types (only
  `connectors.ts`/`auth.ts` use this file); regenerating needs a live
  backend this change doesn't require standing up.

## Test

Backend (`uv run pytest tests/unit`):

- `tests/unit/workflows/test_explore_provisioning.py` (new) —
  `ExploreProvisioningWorkflow.ensure`: returns the existing report without
  creating or committing; creates + commits when missing.
- `tests/unit/v1/test_carbon_report.py` — replaced the POST route tests
  with PUT route tests: creates when missing, returns existing without
  recreating, schedules background refresh when stale (mirrors the GET
  route's existing three TTL tests).
- `tests/unit/services/test_carbon_report_service.py` — new:
  `ensure_calculator_projects` creates one project per unit and is
  idempotent; `bulk_upsert` passes resolved ids through and raises on a
  missing one; `create` raises when no Calculator project exists. Existing
  tests that relied on `create()`'s removed lazy-provision now provision
  the project explicitly first (local `_calculator_report` helper); the
  statement-budget regression (#2449 Track B) updated for the now-smaller
  in-request project work.
- `tests/unit/tasks/test_handler_registrations.py` — `unit_sync_handler`
  tests mock the new `ensure_calculator_projects` call.
- `tests/unit/services/test_simulator_plan_service.py`,
  `test_simulator_plan_reference_year_perf.py`, and the PG integration test
  `tests/integration/services/data_ingestion/test_simulator_plan_prefill_job_pg.py`
  — their Calculator-report test helpers now provision the project
  explicitly first (same pattern).

Frontend: `frontend/tests/unit/request-dedup.spec.ts`'s
`explore-seed-cache` scenario needed no change — its route mock matches
the URL regardless of HTTP method, and the success path was already one
request before this change (GET only; a POST fallback only fired on a
miss). Verified by inspection; a dedicated component test for the PUT
call itself was not added — `putExploreCarbonReport` is a two-line pass-
through over `carbonReportLookupPath` + `api.put`, already exercised
end-to-end by that spec's `explore-seed-cache` scenario and by
`SimulationExplorePage`'s own Playwright coverage.

## Deliverables

- [x] `PUT /carbon-reports/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/`
      backed by `ExploreProvisioningWorkflow`; old POST route deleted
- [x] `frontend/src/api/carbon_reports.ts` (new) + `workspace.ts`'s
      `selectSimulatorExploreCarbonReport` calls it unconditionally, no
      404 branch
- [x] `CarbonReportService.create`/`bulk_upsert` lazy project creation
      removed; `ensure_calculator_projects` added and called from
      `unit_sync_handler`
- [x] Regression tests (workflow, PUT route, service fail-hard paths,
      unit_sync wiring) + test fallout fixed across 5 files
- [x] Flip to `delivered` on merge
