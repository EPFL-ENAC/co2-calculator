---
status: delivered
issue: 2778
last_updated: 2026-11-10
summary: "GET on a plan now returns its unfinished simulator_plan_prefill job id, and the Project Planner waits on it after a reload exactly as after the PATCH: banner shown, project info and year sections locked with `inert` until the job ends. The lock matters for data: the prefill empties and rebuilds every reference-scoped module, so edits made during the window are lost or end up mixed with copied rows."
---

# #2778 — Planner reload during the year prefill unlocks unfilled years

## Problem

Creating plan years, or changing a reference year, queues a
`simulator_plan_prefill` job (plan #2050 Track F4). Only the PATCH response
carried its id, so only the tab that sent the PATCH knew about the job. After
a reload, `GET /project-plans/{id}` returned `prefill_job_id: null`, the
"prefill running" banner disappeared and the half-built sections could be
edited.

`prefillRunning` drove the banner only, so even without a reload there was no
lock: after a reference-year change the section stayed editable while its job
ran.

## Can the prefill overwrite edits made in that window? Yes

The job (`SimulatorPlanService.prefill_reports`) runs as one transaction that
the runner commits at the end. For each report it:

1. deletes **every** entry of each reference-scoped module, whoever wrote it.
   `DataEntryRepository.bulk_delete_by_modules` filters on the module id
   only. It is called from `_clear_module_entries`,
   `prefill_module_from_reference`, `prefill_headcount_from_reference` and
   `prefill_equipment_global`;
2. copies the reference year back in;
3. recomputes the emissions and stats of the whole report.

| Edit made while the job runs                                                            | Outcome                                                                                                                                                                                      |
| --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Row added or edited in a reference-scoped module **before** the job deletes that module | Lost, with no error                                                                                                                                                                          |
| Row added **after** that delete, before the job commits                                 | Kept, mixed in with the copied rows                                                                                                                                                          |
| Equipment mode or percentage                                                            | Lost: `prefill_equipment_global` empties the module and rewrites it in global mode at 0%                                                                                                     |
| Row in a module outside the reference scope                                             | Kept; its emissions are recomputed                                                                                                                                                           |
| Active checkbox, grant budgets                                                          | Kept: they live on the module and report rows, which the job does not delete                                                                                                                 |
| Second reference-year change                                                            | Queues a second job. Each job reads the report's reference year when it runs, so both rebuild from the latest value. Whether two jobs on one report can run at the same time was not checked |

So the lock protects data, not only the stats the issue reported as wrong.

The job always ends. A crashed job is retried by the poller's sweep, then
marked FINISHED with an error once its attempts run out
(`sweep_stuck_running_jobs`). With the defaults
(`STALE_JOB_TIMEOUT_MINUTES = 5`, `max_attempts = 3`), a job whose pod keeps
dying holds the lock for about 15 minutes at worst. A job that fails normally
ends at once with an error.

## What shipped

### Backend

- `DataIngestionRepository.get_unfinished_prefill_job_id(plan_id)`: the
  newest `simulator_plan_prefill` job whose state is not FINISHED. "Unfinished"
  is the exact opposite of `finished` in the prefill status route. `meta` is
  plain JSON and the tests run on SQLite, so the plan is matched in Python, as
  the status route does.
- `GET /project-plans/{plan_id}` sets `prefill_job_id` from it. No migration,
  no new endpoint, no new field.

### Frontend

- `simulatorPlans.resumePrefill(planId, jobId)` keeps `prefillRunning` set
  while it polls the job, then GETs the plan again and keeps polling while a
  job is still reported, since an older job can outlive the newest one. It
  then refetches the years and the aggregate stats.
- `ProjectPlannerPage.vue` calls it first in `onMounted`, so the lock is on
  before the sections render. The project-info box and the `.year-sections`
  wrapper carry `:inert="plansStore.prefillRunning"`, the pattern of
  `DataManagementPage.vue`. `inert` blocks clicks, focus and keyboard, so
  `PlannerYearSection.vue` is untouched. The same gate locks the
  reference-year-change path.

### Tests

- `backend/tests/unit/v1/test_simulator_plan_prefill_job_id.py`: GET returns
  a NOT_STARTED or RUNNING job, ignores a FINISHED one, and ignores another
  plan's job.
- `frontend/tests/integration/planner-prefill-reload.spec.ts`: banner and
  `inert` lock are shown, survive `page.reload()`, then clear once the mocked
  job finishes, and the years are refetched.

## Not done

- **The lock is in the browser only.** A tab that loaded the plan before the
  job started, or a direct API call, can still write during the prefill. A
  server-side 409 on entry writes would close that; it touches every
  data-entry write route.
- `prefillRunning` is one flag for the whole store. Leaving plan A
  mid-prefill and opening plan B shows A's lock on B until A's job ends, and
  `resumePrefill` keeps polling after the page unmounts, then refetches A's
  years into the shared store. The single flag predates the fix.
