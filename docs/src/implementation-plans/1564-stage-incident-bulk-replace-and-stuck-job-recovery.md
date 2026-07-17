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

Note: the test file itself carried 760 intra-file `(uid, sius_code)`
duplicate rows — those still skip by design; whether the key needs a third
component is an open data question, not covered here.

## 2. Stuck-job recovery latency

The pod was SIGTERMed mid-job (readiness "connection refused" was a
_consequence_ — the likely cause is node-pressure eviction: 128Mi request
vs 512Mi limit; confirm via the pod's `lastState.terminated`). Nothing
marks a cancelled job, so the row stayed `RUNNING` until the stale sweep —
whose window was 60 min, a default from before the 310-C per-job heartbeat
existed.

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
