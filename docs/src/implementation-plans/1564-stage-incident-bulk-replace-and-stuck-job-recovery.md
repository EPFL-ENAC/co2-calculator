---
status: delivered
issue: 1564
last_updated: 2026-07-17
title: "Stage incident follow-ups: cross-source bulk replace + stuck-job recovery"
summary: "Headcount CSV upload after an API sync mass-skipped 8465 rows as DUPLICATE_INSTITUTIONAL_ID (bulk sources didn't replace each other), and a pod SIGTERM mid-recalc left the aggregation invisible for the 60-min stale window. Delivers cross-source full replace, 5-min heartbeat-based stale recovery, queue-time visibility, and a manual Recover button."
---

# Stage incident follow-ups (2026-07-17)

## Incident

Testing #1564 on stage: a headcount CSV upload after an API sync inserted
20 of 8485 rows (8465 skipped `DUPLICATE_INSTITUTIONAL_ID`), then the
chained `emission_recalc` was killed 60s in by a pod SIGTERM and sat
`RUNNING` with no recovery in sight.

Three root causes, one per section below.

## 1. Cross-source bulk replace

The per-year replace delete was scoped to `source=CSV_MODULE_PER_YEAR`
only, while the `(user_institutional_id, sius_code)` uniqueness check has
no source filter — so API-synced rows (`EXTERNAL_INTEGRATION`) survived
the delete and collided with every CSV row.

**Decision (maintainer):** a bulk per-year ingest (CSV _or_ API) is a
complete yearly export and replaces all machine-owned bulk sources.

- `BULK_PER_YEAR_SOURCES` (`models/data_entry.py`): CSV per-year, API
  per-year, external integration. Manual + unit-specific always preserved.
- `bulk_delete_by_source_year` takes `sources: list[int]`; both callers
  (`base_csv_provider`, `base_tableau_api_provider`) pass the constant.
- Tests: unit (both providers) + pg integration seed an API row and prove
  it's replaced.

**Follow-up (same incident, second layer):** the replace DELETE keys on
the denormalized `data_entries.year`, but the API providers built their
entries **without** `year`/`unit_id` — so the cross-source delete matched
zero API rows and re-uploads still mass-collided. The stamp now lives
centrally in `DataEntryService.fill_denormalized_scope` (called by
create / bulk_create / bulk_copy — post-review altitude fix, replacing
the initial per-provider stamping), so no write path can omit it; manual
entries are stamped too. Migration `8eeff0a9fa26` backfills existing
NULL rows from each entry's carbon report. The data card also treats an API sync as existing data
(re-upload label + same ERROR/WARNING/SUCCESS color mapping as CSV, with
CSV precedence — a WARNING sync previously rendered as red "Add Data").

**Follow-up (performance):** the row loop ran ONE uniqueness SELECT per
row — at stage latencies an 8.5k-row parse dropped to 14 rows/s (~10
min), the same N+1 shape COPY batching had already removed on the write
side. The in-memory duplicate set is now seeded with all existing
`(module, uid, sius_code)` member tuples in one bulk query
(`get_member_role_keys`), gated to headcount ingests; the per-row check
is a set lookup. The manual-entry path keeps its single-row
`check_member_role_unique`.

**Deferred (schema change on validated data — proposal for the lead):**
DB-enforced member-role uniqueness as defense-in-depth: a partial unique
index on `(carbon_report_module_id, data->>'user_institutional_id',
data->>'sius_code') WHERE data_entry_type_id = <member>`, with the bulk
path COPYing into a staging table and `INSERT … ON CONFLICT DO NOTHING`.
Only variant airtight under concurrent writers; today the per-year
advisory locks already serialize bulk ingests, so this is belt-and-braces.
Costs: staging-table refactor of the COPY path and loss of per-row
"Row N: DUPLICATE" reporting.

Note: the test file itself carried 760 intra-file `(uid, sius_code)`
duplicate rows — those still skip by design; whether the key needs a third
component is an open data question, not covered here.

## 2. Stuck-job recovery latency

The pod was SIGTERMed mid-job. **Root cause confirmed by probe-latency
measurement on stage:** the recalc loop yielded the event loop only every
1000 entries, so `/healthz` (a no-op endpoint) couldn't get a slot within
the kubelet's 2s probe timeout during pure-CPU stretches — three straight
liveness failures at 20s period killed the pod exactly 60s after
`Recalc member/2025` started. (Memory was fine: 798Mi of 1000Mi.
Readiness "connection refused" events were the restart gap, not the
cause.) Nothing marks a cancelled job, so the row stayed `RUNNING` until
the stale sweep — whose window was 60 min, a default from before the
310-C per-job heartbeat existed.

**Fix (event-loop starvation):** both CPU loops now yield on wall time
(~50ms) instead of entry count — recalc (`emission_recalculation.py`,
was every 1000 entries) and CSV row loop (`base_csv_provider.py`, was
every 100 rows). Recalc progress reporting also went time-based (every
2s, was every 5000 entries) with a terminal N/N update, and the job
status line carries rate + ETA. **Ops action (cluster config, not this
repo):** stage's probe overrides set `timeoutSeconds: 2` — raise to 5
(the chart default) for liveness and readiness.

- `STALE_JOB_TIMEOUT_MINUTES` 60 → **5** (config default, helm,
  .env.example): heartbeats every 75s, dead-pod recovery ≤ ~6 min. The
  window bounds _crash-recovery latency_, not job runtime — stale
  docstrings claiming otherwise rewritten (`sweep_stuck_running_jobs`,
  `_heartbeat_loop`).
- Not 2 min: the same window is the live runner's self-abort threshold on
  heartbeat failures; 5 min tolerates transient DB outages.

**Deferred (needs plan + both maintainers):** shutdown handler in
`run_job` releasing claimed jobs on CancelledError (near-instant recovery
after graceful kills); dedicated worker Deployment so long jobs stop
sharing lifecycle with HTTP pods; memory request raised toward real usage.

## 3. Operator visibility

- Jobs table gains `created_at` (migration `7bfda0d45f14`); the ops
  console shows `queued Xs` (created→started) next to the run duration —
  a sub-second aggregation that waited 20s no longer reads as "<1s total".
- `PipelineJobListEntry.is_stale` derived server-side (same predicate as
  the sweep); the console renders a stale badge + **Recover** button
  wiring the pre-existing `POST /jobs/{id}/recover`. Deliberately _not_ a
  new persisted job state — staleness is derived, not stored.
