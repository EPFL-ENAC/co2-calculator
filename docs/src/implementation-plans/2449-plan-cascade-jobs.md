---
status: delivered
issue: 2449
last_updated: 2026-08-28
summary: Measured stage traces show the planner cascades are fast today — monitoring hygiene and a cheap fan-out trim ship now; the purge job is specified but deferred behind explicit triggers
---

# 2449 — Plan cascades vs the < 1 s request budget

## Mandate (maintainer, 2026-08-28)

Requests above 10 s trip alerting; the budget is **under 1 s** per request.
The #2445 audit flagged plan DELETE, shrink-PATCH/grant-off and
duplicate/grow-PATCH as violators by static analysis. **Before deciding,
traces were pulled — and they overturn part of that.**

## Measured evidence (stage Tempo, 7 days to 2026-08-28)

Caveat first: Tempo's _trace_ durations are page-session lengths (the
frontend joins a visit's requests and its job polling into one trace — a
"40-minute PATCH" is a 60 ms PATCH plus 40 minutes of polling). Only
**server-span** durations mean anything.

| Route                | Samples | Measured server span                                                     | Statements |
| -------------------- | ------- | ------------------------------------------------------------------------ | ---------- |
| plan create          | many    | 20–65 ms                                                                 | ~7         |
| duplicate            | 4       | **90–100 ms**                                                            | 33         |
| PATCH grow range     | ~10     | 30–230 ms (worst: multi-year, 90 stmts)                                  | 11–90      |
| PATCH reference-year | many    | 30 ms                                                                    | 11         |
| DELETE plan          | 7       | **20–220 ms** (incl. one with a real `DELETE FROM data_entries`, 100 ms) | 7–22       |

The sweep that settles it — every server span **> 5 s in 7 days**, all
routes, whole backend:

```
82.2 s  POST /project-plans/unit/{unit_id}/   ← incident create #0 (#2445)
41.5 s  POST /project-plans/unit/{unit_id}/   ← incident create #1
17.3 s  POST /project-plans/unit/{unit_id}/   ← incident create #2
```

Nothing else — except `GET /sync/pipelines/{id}/stream` spans (6–170 s),
which are SSE streams, long-lived **by design**. Conclusions:

1. **The alerting pain had exactly one cause — the name-index lock wait —
   and it is already fixed** (#2446, merged; reaches stage with the next
   dev → stage release).
2. Duplicate, grow-PATCH, delete and shrink are all measured an order of
   magnitude under budget on today's data.
3. The audit's ~200k-entry delete scare is a _ceiling_ extrapolation
   (calculator-scale unit × 10-year prefill). No real plan is near it; the
   structural point (deletion cost is unbounded in data volume) stays true.
4. The remaining >10 s "requests" in monitoring are the SSE stream — noise
   in any request-latency alert.

## Tracks (revised by evidence)

### Track M — monitoring hygiene · verified already in place

Checked rather than assumed: the stage collector transform from #1402
already classes `…/stream$` spans and metric datapoints as
`route_class="stream"` (verified on a live stream span from 2026-08-27,
`route_class=stream`), and every latency alert selects
`route_class="api"` — so SSE streams are excluded from latency alerting
today. **No change needed** in `openshift-app-config`. The stream spans in
this plan's >5 s sweep appeared only because the TraceQL query did not
filter by class. Consequently the only api-class requests above 10 s in
recent history were the #2445 lock waits, now fixed. Remaining hygiene item
rides on #2487: the explore/calculator existence probes' expected 404s
disappear with the PUT singletons.

### Track B — fan-out trim · ship now, cheap

Duplicate/grow statements are dominated by avoidable chatter: a
`session.refresh` per module (8 SELECTs per report) plus one per report, in
`CarbonReportModuleService.create_all_modules_for_report` /
`carbon_report_repo.create`. Bulk-insert the 8 module rows and drop the
refreshes (`RETURNING` provides the ids): a 10-year+grant grow goes from
~200 statements to ~40, keeping the route comfortably under budget even at
wide ranges. Statement-count regression test caps it.

### Track A — `simulator_plan_purge` job · **deferred behind triggers**

Design retained below for when it fires; not implemented now, because no
measured request comes within 4× of the budget. Implement when **either**:

- any plan DELETE / shrink-PATCH server span above **1 s** is observed
  (the >5 s alert sweep above is the watch — rerunning it is one TraceQL
  query), or
- plans start prefilling at calculator scale (≥ ~50k entries per plan).

Retained design (unchanged from the first draft): nullable `deleted_at` on
`carbon_projects` + `carbon_reports`, read paths filter it; DELETE marks +
enqueues `simulator_plan_purge` on the existing `DataIngestionJob` runner
and returns **202 + job id**; shrink/grant-off mark their reports and
enqueue the same job; the handler purges entries in ~5k-row batches with
per-batch commits; deletion is visible as an in-progress pipeline job and a
failed purge is a stuck job for the existing recovery tooling. No new state
machine, no reset mechanism.

## Out of scope (separate follow-ups)

- Grant `reference-percentage` PATCH (per-entry emission loop, no
  `FactorResolver` cache) — flagged by static analysis; measure it the same
  way before planning.
- Explorer TTL refresh as a proper job (today an unmanaged
  `BackgroundTasks`).
- Login `unit_users` delete-and-reinsert; year-config CSV stored 3×.

## Tests

- Track B: statement-count assertion on report creation (SQLAlchemy event
  hook counts executed statements; cap asserted).
- Track A (when triggered): purge-job idempotency + chunking tests as
  specified in the first draft.

## Deliverables

- [x] Track M: verified — stream already excluded via `route_class` (#1402);
      no config change
- [x] Track B: per-object refresh chatter dropped in report/module
      creation, statement-count regression test
- [ ] Track A: **not now** — triggers documented above; revisit on evidence
- [x] Flip to `delivered` on merge
