---
status: in-progress
issue: 2449
last_updated: 2026-08-28
summary: Move the plan deletion cascade to a user-visible pipeline job and bring duplicate/grow-PATCH under the 1 s request budget
---

# 2449 — Plan cascades out of the request transaction

## Mandate (maintainer, 2026-08-28)

Requests above 10 s trip alerting; the budget is **under 1 s per request**.
The #2445 audit measured three violators on the planner write path:

| Path                                                       | Today                                                                 | Target                         |
| ---------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------ |
| `DELETE /project-plans/{plan_id}`                          | up to ~200k entries + 0.4–1M emission rows deleted in one transaction | 202 in ms + purge job          |
| `PATCH /{plan_id}` shrink range / grant off                | same cascade for the removed years, in-request                        | ms + purge job                 |
| `PATCH /{plan_id}` grow range, `POST /{plan_id}/duplicate` | ~200 statements (per-module `session.refresh`)                        | tens of statements, in-request |

Everything runs on the **existing `DataIngestionJob` runner** (#2050
pattern). No new state machine, no reset mechanism.

## Track A — `simulator_plan_purge` job (delete, shrink, grant-off)

One job type covers all three, because they are the same operation at
different scopes: destroy a set of reports (and, for plan deletion, the
project row afterwards).

**Schema** (generated via `make db-revision`): nullable `deleted_at`
timestamp on `carbon_projects` **and** `carbon_reports`. Marking is the
route's cheap write; purging is the job's work. Every read path filters
`deleted_at IS NULL` (plan lists, `list_plan_years`, workspace home,
aggregate-stats, policy lookups) — a marked row is invisible immediately,
so the UI never shows zombie years while the purge runs.

**Routes**:

- `DELETE /{plan_id}` → policy `delete`, set `deleted_at` on the project and
  all its reports, enqueue `simulator_plan_purge` (`config: {plan_id}`),
  commit → **202** `{job_id}`. (Breaking response-code change, 204 → 202:
  frontend `deletePlan` adjusts; no backward compatibility.)
- `PATCH` shrink / grant-off → `_sync_year_reports` stops calling
  `report_service.delete`; it sets `deleted_at` on the out-of-range (or
  grant) reports and returns their ids; the route enqueues the purge job
  (`config: {plan_id, report_ids}`) the same way `_enqueue_prefill` works,
  and the response carries the job id alongside the existing
  `prefill_job_id`.

**Job handler** (registered like `simulator_plan_prefill`): idempotent and
chunked — per report: delete `data_entries` in id-batches (~5k per DELETE,
one commit per batch; emissions go with them via FK cascade), then modules,
then the report row; finally the project row when `deleted_at` is set on it
and no reports remain. Re-run safe: everything is keyed off marked rows;
missing rows mean that step is already done. Locks live for one batch, not
one plan.

**User-facing** (maintainer requirement — deletion shows as an in-progress
pipeline job): the plan disappears from the table immediately
(`deleted_at` filter); the purge job is visible in the pipelines/jobs
monitoring like any sync job, and a failed purge is a stuck job handled by
the existing recovery tooling (`/sync/jobs/{id}/recover`), not a
half-deleted plan on screen.

## Track B — trim the create fan-out (duplicate, grow-PATCH)

The ~200 statements are mostly avoidable chatter: a `session.refresh` per
module (8 SELECTs per report) plus one per report. Fix in
`CarbonReportModuleService.create_all_modules_for_report` and
`carbon_report_repo.create`: bulk-insert the 8 module rows in one statement,
drop the per-object refreshes (the caller needs ids, which `RETURNING`
provides). Expected: 11-report grow ≈ 30–40 statements, well under budget
locally (< 300 ms target, ~4× on stage still under 1 s).

Escalation only if stage measurements still exceed 1 s: move report
creation into the prefill job itself (the job already exists and the UI
already polls it). Not built preemptively.

## Explicitly out of scope (separate follow-ups)

- Grant `reference-percentage` PATCH (per-entry emission loop) — same job
  treatment plus batch `FactorResolver`, its own plan.
- Explorer TTL refresh as a job (today an unmanaged `BackgroundTasks`).
- Login `unit_users` delete-and-reinsert; year-config CSV stored 3×.

## Tests

- Purge job: unit tests on the handler — chunked deletion completes, re-run
  after simulated mid-purge crash finishes cleanly, project row only goes
  when its reports are gone.
- Routes: DELETE returns 202 + job id and the plan vanishes from list
  endpoints; shrink-PATCH marks reports and enqueues; regression that no
  entry deletion happens in-request.
- Track B: statement-count assertion on report creation (create one report,
  count executed statements via SQLAlchemy event hook, cap it).
- Frontend (Playwright CT): plans table handles 202 delete + row gone.

## Deliverables

- [ ] Migration: `deleted_at` on `carbon_projects` + `carbon_reports`
- [ ] Read-path filters for `deleted_at`
- [ ] `simulator_plan_purge` handler (chunked, idempotent) + registration
- [ ] DELETE route → mark + enqueue + 202; frontend `deletePlan` update
- [ ] `_sync_year_reports` shrink/grant-off → mark + enqueue
- [ ] Bulk module insert, refreshes dropped
- [ ] Tests per section above
- [ ] Flip to `delivered` on merge
