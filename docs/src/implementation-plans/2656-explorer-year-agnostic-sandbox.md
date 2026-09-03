---
status: delivered
issue: 2656
last_updated: 2026-09-03
summary: Explorer's Simulator Explore sandbox is no longer keyed by year or refreshed on a 24h TTL. "Start an exploration" (a page mount or refresh alike) always POSTs a brand-new sandbox; the backend deletes the caller's older ones in the background right after. Factor resolution for Explore entries now always uses the latest started year (N-1, fallback N-2, else a loud error) instead of the sandbox's own year.
---

# 2656 — Explorer is not year-agnostic

## Problem

A user uploads a CSV in the Explorer while the Calculator is set to year
2025, then switches the Calculator to 2026 and opens the Explorer again —
their data is gone. It isn't deleted: the Explore sandbox was keyed by
`(unit_id, created_by, year=reference_year)` (`carbon_reports.year`, via
`uq_carbon_reports_project_year` on `(carbon_project_id, year)`), and
`reference_year` was the Calculator year the frontend happened to be on
when it called
`PUT /v1/carbon-reports/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/`
(`workspace.ts#selectSimulatorExploreCarbonReport`). Switching Calculator
year looked up a sibling row that had never existed, so
`ExploreProvisioningWorkflow.ensure()` created a fresh empty one — the 2025
row and its entries were untouched but no longer reachable from the UI.

Separately, `resolve_factor_year()` (`app/utils/factor_year.py`) fell
through to `report.year` for Explore reports (their `reference_year` column
is always `None`, and their project type isn't `SIMULATOR_PLAN`), so
entries in an Explore sandbox opened under year 2026 priced against 2026
factors — a year that has no published factor set. There is no data for an
arbitrary future/current year, so this was always a wrong answer; the
per-year keying just made it visible as "my data vanished" instead of
"my numbers are wrong."

### The old flow (removed by this change)

```
GET/PUT /v1/carbon-reports/simulator/explore/unit/{unit_id}/reference-year/{reference_year}/
                    │
                    ▼
   lookup CarbonReport WHERE
     project.type = SIMULATOR_EXPLORE
     project.unit_id    = unit_id
     project.created_by = current_user.id
     report.year         = reference_year   ◄── keyed by year (root cause)
                    │
        ┌───────────┴────────────┐
     not found                 found
        │                         │
   GET → 404, FE retries PUT   age = now − last_updated
   PUT → create_explore()        │
   (fresh, empty, done —   ┌─────┴─────┐
    nothing stale to check) age ≤ TTL   age > TTL (24h)
                            (24h)       or last_updated=None
                             │             │
                          return       return the STALE report
                          as-is        immediately (never blocks)
                          (no bg task)  + BackgroundTasks.add_task:
                                          async with SessionLocal():
                                            service.delete(old_report_id)
                                            service.create_explore(...) # same key
                                            commit()
```

Two problems with this shape, beyond the year-keying bug: creation and
staleness cleanup were the same endpoint deciding both (a GET could
trigger a delete+recreate as a side effect of a read), and the 24h TTL
meant a sandbox nobody asked to keep could still silently persist for
up to a day.

## Decision

**"Start an exploration" always creates. No more existence check, no
TTL — create and delete are two separate, explicit steps.**

```
POST /v1/carbon-reports/simulator/explore/unit/{unit_id}/
                    │
                    ▼
   ExploreProvisioningWorkflow.create()
     → CarbonReportService.create_explore(unit_id, created_by)
         always inserts a NEW CarbonProject + CarbonReport + modules
         (no reuse, no "does this exist" branch, no race to guard —
          nothing else can conflict with a project that was never shared)
     → commit()
                    │
                    ▼
        response sent to the caller (the new, empty sandbox)
                    │
                    ▼  (background, after the response)
   BackgroundTasks: _cleanup_old_explore_background(unit_id, created_by, keep_project_id)
     → delete every Explore project for (unit_id, created_by)
       with id < keep_project_id — cascades to its report + modules + entries
     → commit()

GET /v1/carbon-reports/simulator/explore/unit/{unit_id}/
     → read-only: the newest surviving sandbox, or 404. No side effects,
       ever — no create-fallback, no cleanup, no staleness check.
```

A page mount or a refresh both call POST unconditionally
(`SimulationExplorePage.vue#onMounted` → `selectSimulatorExploreCarbonReport`
→ `postExploreCarbonReport`): **refreshing the Explorer loses the working
sandbox and starts a new one, by design.** There is no "resume where I left
off" — that was the accidental (and buggy) behavior of the old GET-404-PUT
idempotency, never a stated goal.

**Cleanup targets `id < keep_project_id`, not `id != keep_project_id`.**
Two near-simultaneous "start exploration" calls (a double-click, two tabs)
each create their own project and each schedule a cleanup naming their own
project as the one to keep. Deleting "everything else" would let each
cleanup delete the other's fresh project — depending on timing, both could
end up deleted. Deleting only what's _older_ than the kept project means
each cleanup only ever removes projects that existed before it started;
neither can touch a project created after it. Worst case from a real race
is two survivors, not zero — self-heals on the next "start exploration."

**No more unique index on `(unit_id, created_by)` for Explore projects.**
It existed (#2293) to keep one sandbox per user; #2656 replaces "one
sandbox, refreshed in place" with "many created over time, only the newest
kept," so a user can transiently have more than one row between a create
and its cleanup. Migration `095d98bc390c` drops
`uq_carbon_projects_unit_explore_creator`. No data migration needed — a
pre-#2656 project (one project, several reports, one per year it was
opened under, since it _was_ unique per creator) self-collapses the first
time its owner starts a new exploration: `create_explore` always makes a
fresh project, and cleanup then deletes every older project for that
`(unit, created_by)`, that grandfathered one and all its reports included.

**Factors always resolve from the latest started year, never the
sandbox's own year.** New branch in `resolve_factor_year()` for
`carbon_report_type == SIMULATOR_EXPLORE`
(`app/utils/factor_year.py#_resolve_explore_factor_year`):

```python
for candidate in (this_year - 1, this_year - 2):
    if await is_year_started(session, candidate, user.provider):
        return candidate
raise ValueError(f"No published factors for {this_year - 1} or {this_year - 2}")
```

reusing `is_year_started` (`app/services/year_config_service.py`), the same
primitive the taxonomy endpoints already gate on. `user` is the Explore
project's creator, loaded by `project.created_by` — `resolve_factor_year`
otherwise only ever sees the report, not the requesting user. The raise is
an uncaught `ValueError` (no global exception mapping for it exists in this
codebase) — it surfaces as a loud 500 naming both years checked, not a
silent default. A friendlier 4xx mapping is a possible follow-up, out of
scope here: it would touch the shared exception handling across every
`resolve_factor_year` caller (Calculator, Plan, Explore, professional
travel), not just this one.

## Migration (`095d98bc390c`)

Drops `uq_carbon_projects_unit_explore_creator` only. `ix_classification_translations_label_trgm`
in the autogenerate diff was unrelated drift (a pg_trgm index not tracked
in SQLModel metadata) — pruned per the standing rule.

## Touch points

- `app/api/v1/carbon_report.py` — GET drops `reference_year`, returns
  read-only; PUT → POST (`create_simulator_explore_carbon_report`), no
  more `_refresh_explore_background`/`_schedule_explore_refresh_if_stale`,
  replaced by `_cleanup_old_explore_background`.
- `app/workflows/explore_provisioning.py` — `ensure()` → `create()`.
- `app/services/carbon_report_service.py` — `get_explore`/`create_explore`
  drop `reference_year`; `_get_explore_project` removed (no more
  get-or-create); new `delete_old_explore`.
- `app/repositories/carbon_report_repo.py` — `get_explore_by_unit_and_reference_year`
  → `get_latest_explore_by_unit` (orders by project id, then report id, to
  break ties on grandfathered multi-report projects) + new
  `list_explore_by_unit_older_than`.
- `app/models/carbon_project.py` — drops the per-creator unique index.
- `app/core/config.py` — `EXPLORE_TTL_SECONDS` removed.
- Frontend: `api/carbon_reports.ts` (`putExploreCarbonReport` →
  `postExploreCarbonReport`), `constant/carbon-project.ts`
  (`carbonReportLookupPath`'s explorer branch drops the year segment;
  `resolveCarbonReportId`'s callers keep passing a year for their own cache
  key — it's just never forwarded to the URL for the explorer case),
  `stores/workspace.ts`. `openapi.d.ts` regenerated.

## Tests

- `tests/unit/services/test_carbon_report_service.py` — `create_explore`
  always makes a fresh sandbox; `get_explore` returns the newest;
  `delete_old_explore` keeps only the kept project and leaves
  newer-than-keep creates untouched (the race case above). Removed the
  now-impossible "does not cross years" and IntegrityError-race tests (no
  unique constraint left to race on).
- `tests/unit/workflows/test_explore_provisioning.py` — `create()` always
  creates and commits, never checks for an existing sandbox.
- `tests/unit/v1/test_carbon_report.py` — GET is read-only with no
  background task; POST always creates and schedules cleanup with the new
  project's id.
- `tests/unit/utils/test_factor_year.py` — Explore resolves to
  `this_year - 1` when started, falls back to `this_year - 2`, raises
  naming both years when neither is, and ignores the report's own year
  throughout.
