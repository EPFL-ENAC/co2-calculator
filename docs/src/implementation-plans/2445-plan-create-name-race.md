---
status: draft
issue: 2445
last_updated: 2026-08-27
summary: Retry auto-generated plan names on unique-index race instead of surfacing a 409 the user cannot act on
---

# 2445 — Auto-named plan create loses the unique-index race

## Symptom

GlitchTip [CO2-CALCULATOR-DEV-9F](https://enac-it-glitchtip.epfl.ch/co2-calculator-dev/issues/320)
(stage, 2026-08-27): clicking **Démarrer un projet** produced a
`POST /project-plans/unit/456/` that blocked ~17 s and returned **409**
`"A plan with this name already exists for this unit"` — for a request that
never supplied a name.

## Root cause

Default naming is read-then-insert. `SimulatorPlanService.create_plan(name=None)`
reads the unit's committed plan names and picks the next free `new-project[-N]`;
the partial unique index `uq_carbon_projects_unit_plan_name`
(`(unit_id, name)` where `carbon_report_type = 'Simulator_Plan'`) is what
actually enforces uniqueness. A concurrent transaction holding an uncommitted
row with the same name is invisible to that read but locks the index key:
Postgres blocks the INSERT until the other transaction commits, then raises
`unique_violation`, which `_flush_guarded` maps to `ValueError` → 409.

The 17 s block matches `duplicate_plan`, which flushes the copied project row
and then builds all per-year reports in the same transaction before the route
commits — a long uncommitted window. A duplicate of a default-named plan
inserts `new-project-2`; a concurrent no-name create computes the same name,
blocks on it, and dies when the duplicate commits. `duplicate_plan`'s own
`<name>-N` suffixing has the identical race.

## Fix

In `SimulatorPlanService` (`backend/app/services/simulator_plan_service.py`),
when the name was **auto-generated** — create with `name=None`, and duplicate's
suffixing — an `IntegrityError` on flush means the computed name lost the race.
Rollback, re-read the names (the winner is now committed and visible),
recompute the next free name, retry the insert, bounded at 3 attempts. One
shared helper covers both call sites.

Behavior kept as-is:

- An explicitly user-chosen colliding name still returns 409 — there the
  conflict is real and actionable.
- No frontend change: with the backend retrying, `onStartProject` succeeds and
  the existing error path stays for genuine failures.

## Test

Regression test in `backend/tests/unit`: first flush raises `IntegrityError`,
retry recomputes from the refreshed name list and succeeds (the SQLite test
schema intentionally omits the partial indexes, so the race is simulated at the
repo boundary). A second test asserts the explicit-name collision still raises.

## Deliverables

- [ ] Shared auto-name retry in `SimulatorPlanService.create_plan` / `duplicate_plan`
- [ ] Regression tests (race retry + explicit-name 409 kept)
- [ ] Flip this plan to `delivered`
