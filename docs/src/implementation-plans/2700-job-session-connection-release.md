---
status: in-progress
issue: 2700
last_updated: 2026-09-09
title: "runner.py holds job_session/data_session for the whole job"
summary: "Follow-up to #2689: that issue fixed connection-pinning on the
  auth path and the SSE streams; run_job itself still opens job_session
  and data_session once and holds both for the job's full lifetime.
  Part 1 (this plan): job_session's actual gaps are narrower than they
  looked — base_provider.py already commits it on every progress
  update — so this closes claim-to-first-commit and
  last-commit-to-finish_job, no retry-semantics risk. Part 2
  (data_session, one commit for the whole batch — job 59 in #2689 was
  144k rows over ~70 min) is deferred: it needs an idempotent-resume
  design and its own reviewed plan, per guardrails on pipeline
  internals."
---

# runner.py holds job_session/data_session for the whole job (#2700)

## Where this comes from

While investigating #2528 (concurrent CSV upload move failures) and
running real-data ingestion against dev (2026-09-09), swept
`MAX_CONCURRENT_JOBS` at 1/4/27 with zero pool errors — concurrency
wasn't the bottleneck at that scale. Separately, #2689
(`2689-pgbouncer-query-wait-timeout.md`) fixed connection-pinning on the
auth dependency and both SSE streams, and named "routes that hold their
own session across slow work" and "long ingests" as still open. This
plan is that follow-up, scoped to `app/tasks/runner.py`'s two sessions.

## What's already clean (checked, not assumed)

Before scoping this, swept every other `SessionLocal()` site touching
jobs/pipelines/polling:

- `_poller.py::poll_pending_jobs` — session scoped to the DB sweep only;
  `asyncio.sleep` is outside the `async with` block.
- `_pipeline_reconciler.py` — same shape, closed before the next sweep.
- `job_stream_by_id` / `pipeline_stream_by_id` (`data_sync.py`) — both
  already open a fresh session per poll iteration and close it before
  the sleep, explicitly per #2654/#2689 (docstring: _"no pooled
  connection is held anywhere on this path"_).
- `emission_recalculation_tasks.py`'s three `helper` sessions — each
  documented "own short-lived session keeps the lock narrow," commit
  and close immediately.

Nothing else is holding a connection long. The two sessions in
`runner.py:136` are what's left.

## `job_session`: traced, not assumed

`async with SessionLocal() as job_session, SessionLocal() as data_session:`
(`runner.py:136`) opens both for the entire `run_job` call. For
`job_session`, tracing every touchpoint:

1. `get_job_by_id` (pre-claim read) — autobegins the transaction.
2. `claim_job` (`runner.py:155`) — a `begin_nested()` SAVEPOINT inside
   that same transaction, not a new one.
3. `get_job_by_id` again (post-claim re-read).
4. Handler runs (`handler(job, job_session, data_session)`,
   `runner.py:234`) — `base_provider.py:35` documents
   `self.job_session` as "for job status updates (**frequent
   commits**)" and does commit there (`base_provider.py:368`) on every
   progress report.
5. Preemption check + `job_session.rollback()` on the losing path
   (`runner.py:306`).
6. `finish_job`'s CAS UPDATE, then `job_session.commit()`
   (`runner.py:392`) — the only other explicit commit in the file.

So `job_session` is _not_ one giant held-open transaction — it's
already committing periodically by design. The real gaps are the two
windows without a commit in between: **claim → the handler's first
progress commit**, and **the handler's last progress commit →
`finish_job`'s CAS**. Neither touches row data (`job_session` never
holds anything but job-lifecycle state), so closing them carries no
retry-semantics risk — unlike `data_session`.

## Fix

Match the pattern already proven correct three times over in this
codebase (heartbeat's per-tick session, both SSE streams, the
`emission_recalculation_tasks.py` helpers): a short-lived session per
lifecycle write instead of one held open across the gap.

- Claim: open a session, `get_job_by_id` + `claim_job` + re-read +
  commit, close — before the handler starts.
- Preemption check: open a session, re-read `locked_by`, close.
- `finish_job`: open a session, CAS UPDATE, commit, close.
- Leave the handler's own frequent-commit behavior on `job_session`
  (`base_provider.py`) untouched — it already does the right thing.

`data_session` keeps its current single-session-per-job shape;
Part 2 (below) is its own follow-up.

## Regression test

`tests/unit/tasks/test_runner.py::test_run_job_commits_job_session_before_handler_starts`
— asserts `job_session.commit()` is awaited before the handler starts
(event-ordering, mirroring `test_get_current_user_releases_connection.py`'s
approach from #2689). Verified failing on the pre-fix code (reverted via
`git stash` to check), passing with the fix.

## Part 2 — `data_session` (deferred)

One commit for the entire ingest (job 59, #2689: 144k rows, ~70 min at
34 rows/s). **Row-processing itself is not the 70 minutes**: running the
same file (`purchases_common_data.csv`, 144,240 rows) locally against
real S3 + the dev DB during this investigation (2026-09-09) logged
`base_csv_provider.py`'s own row-loop profile at **2.9s and 23.2s** for
two separate runs — 180-1400x faster than job 59's 34 rows/s. Same file,
same row count. That rules out slow parsing/validation as the cause and
leaves the DB-side stalls #2689 already documented (`worker job
csv_ingest / factor_ingest` spans blocked up to 700s each,
`query_wait_timeout`) as the far more likely explanation — a fast job
stretched to 70 minutes by connection-wait time inside it. Batching
`data_session`'s commits is not a connection-hygiene nicety here; it is
very likely the actual fix for job 59's case specifically.

Fixing this means committing per `INGEST_COPY_BATCH_SIZE`
batch (50k rows) instead of once at the end — each batch validated in
memory first (already the existing shape, `base_csv_provider.py:909`),
session opened only to `COPY` that batch in, then closed.

This needs an idempotent-resume answer before any code: which batch did
a crashed job actually finish, and how does a retry skip it without
double-inserting or silently dropping rows? Touches the same
idempotency guarantees #1559's destination-exists check protects on the
file-move side. Per guardrails: **written plan reviewed by both
maintainers before code**, referencing the 310-series, #1215, #1219,
#1559, #1723. Out of scope for this PR.

## Also found, 2026-09-09 real-data run (not this plan's scope)

- Dev DB had orphaned `co2-co2-calculator-*` connections (hours old,
  pods long dead) surviving `idle_session_timeout=30min` — the GUC is
  confirmed still set correctly on the `app` role, so the backstop
  itself may not survive PgBouncer's own server-check pinging. Needs
  DBaaS input on `server_check_delay`/`server_idle_timeout`.
- `researchfacilities_common_data.csv` hit `Row processing error: tuple
index out of range` on 7/2017 real rows — unrelated code bug, not yet
  root-caused.
