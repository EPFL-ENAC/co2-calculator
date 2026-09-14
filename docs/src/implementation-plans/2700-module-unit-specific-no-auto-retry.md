---
status: in-progress
issue: 2700
last_updated: 2026-09-09
title: "MODULE_UNIT_SPECIFIC jobs must not auto-retry after a crash"
summary: "Part 2 of #2700, corrected: data_session already commits per
  INGEST_COPY_BATCH_SIZE batch (since 2026-06-10) — there is no
  held-open-for-70-minutes transaction to fix. What batching exposed
  instead: MODULE_UNIT_SPECIFIC uploads are append-only with no
  delete-before-insert and almost no DB uniqueness constraints, so the
  stale-job sweep resetting a crashed job to NOT_STARTED for reclaim can
  re-run the row loop over rows a dead attempt already committed,
  duplicating them. Fix: MODULE_UNIT_SPECIFIC jobs never auto-retry —
  a stale one goes straight to FINISHED+ERROR with a status message
  telling the operator to verify and clean up before re-uploading.
  Manual recovery (POST /jobs/{id}/recover) is blocked the same way.
  Accepted by the maintainer: manual row cleanup is the correct
  resolution, not automated dedup."
---

# MODULE_UNIT_SPECIFIC jobs must not auto-retry after a crash (#2700 Part 2)

## Correction to the original #2700 scope

The plan that shipped Part 1 (`2700-job-session-connection-release.md`)
carried over #2689's framing of "one commit for the whole ingest — job
59, 144k rows, ~70 min." That's not what the code does.
`_process_batch` (`base_csv_provider.py:1481-1535`) already commits
`data_session` after every `INGEST_COPY_BATCH_SIZE` batch (default
50,000 rows, `config.py:565`), and has since `aade48bf1b` (2026-06-10) —
months before #2689. Verified directly: nothing between one batch's
commit and the next batch's `COPY` touches `data_session` — row
resolve/validate/enrich is pure Python, the only DB touch inside
`_process_batch` itself is a per-batch year-cache lookup that's a no-op
once warm. There is no connection held open mid-upload left to release;
that part of the original ask is already done by the existing batching.

## What batching already exposed

Committing per batch means a crash between batches leaves **durably
committed partial data** under a job that isn't FINISHED. Whether a
later retry over that job is safe depends entirely on whether the
handler's own inserts are idempotent — and that's asymmetric:

- **`MODULE_PER_YEAR`** (bulk, no `carbon_report_module_id` pinned):
  `_delete_existing_entries_for_module_per_year`
  (`base_csv_provider.py:731-789`) deletes the whole year/type slice
  before the row loop, on every attempt. A from-scratch retry after a
  partial commit is correct by construction — it deletes whatever the
  dead attempt left, then reinserts the complete file. Wasteful, not
  wrong.
- **`MODULE_UNIT_SPECIFIC`** (single-report upload, `carbon_report_module_id`
  pinned): append-only, **no delete step, ever**
  (`base_csv_provider.py:746`, confirmed in code — the delete branch's
  condition never matches this entity type). `data_entries` has exactly
  one DB uniqueness constraint, `uq_member_role_per_module`
  (`models/data_entry.py:165-183`), scoped to `data_entry_type=member`
  only. Every other type — purchases, equipment, travel, buildings,
  process emissions — has none. A retry after a partial commit
  re-`COPY`s every row the dead attempt already wrote, duplicated,
  silently.

The path that makes this reachable: `sweep_stuck_running_jobs`
(`repositories/data_ingestion.py:1203-1279`) resets any stale-RUNNING
job with `attempts < max_attempts` straight to `NOT_STARTED` for the
next `claim_job` to pick up — no entity-type awareness at all. A pod
crash (or, per the maintainer, DB-pool exhaustion under load — no
observed case of a plain crash) mid-batch-loop on a `MODULE_UNIT_SPECIFIC`
job is exactly this scenario.

## What we're not doing, and why

Building an idempotent-resume mechanism for `MODULE_UNIT_SPECIFIC`
(content-based dedup keys, a persisted batch checkpoint, `ON CONFLICT`
handling per data-entry type) is real design work with its own risk —
manufacturing a natural key for rows that don't have one is exactly the
kind of thing #1559's clean destination-exists check _can't_ generalize
to. **Maintainer decision: don't build it.** A human deletes the
partial rows and re-uploads. Raised to product ownership already;
accepted as correct for this spec. The engineering job here is making
sure that's what actually happens — loudly — instead of the system
quietly corrupting the report with duplicates.

## Fix

**1. `sweep_stuck_running_jobs`** — `MODULE_UNIT_SPECIFIC` never lands in
the "recovered → NOT_STARTED" bucket, regardless of `attempts` remaining.
It always goes to "abandoned → FINISHED+ERROR", with a `status_message`
that says what happened and what to do:

> "Job stopped mid-run (pod lost / crashed) and cannot be safely
> retried automatically — this upload has no duplicate protection.
> Verify data_entries for this report against the source file before
> re-uploading; delete any rows this job may have already written."

**2. `POST /jobs/{id}/recover`** (`data_sync.py:2161-2225`) — the manual
recovery path has the identical footgun (resets to `NOT_STARTED`,
`attempts=0`, same append-only handler runs again). Block it for
`MODULE_UNIT_SPECIFIC` with a `409` carrying the same explanation;
`scope_row.entity_type` is already fetched here for the permission
check, so this is one added branch, not a new query.

**3. Leave `claim_job` untouched.** Once a `MODULE_UNIT_SPECIFIC` job
can no longer reach `NOT_STARTED` via either path above, `claim_job`
never sees it again — nothing to guard there.

**4. The "abandoned batches never get recalculated" gap (found during
Part 2 research) stays unfixed, deliberately.** Today, once a
`MODULE_UNIT_SPECIFIC` job is abandoned, whatever it committed sits
un-recalculated forever. After this fix that's _more_ likely to be the
outcome, not less — but it's the correct outcome: the maintainer's
resolution path is delete-then-re-upload, and a fresh re-upload chains
its own recalc over the (now clean) data. Building recalc-for-orphaned-
partial-data would be effort spent making duplicated data more usable,
backwards from the actual fix.

## Regression tests

`tests/unit/repositories/test_sweep_stuck_running_jobs.py` (existing —
extend): a stale `MODULE_UNIT_SPECIFIC` job with `attempts=0,
max_attempts=3` (plenty of retries left) must land in the abandoned
bucket, not recovered. Fails on current code (goes to `NOT_STARTED`).

`tests/unit/api/test_recover_job.py` (existing — extend, or new if it
doesn't cover entity_type): `POST /jobs/{id}/recover` on a stale
`MODULE_UNIT_SPECIFIC` job returns 409 with the duplicate-risk message,
not a reset job. Fails on current code (recovers normally).

## Explicitly out of scope

- Batch-size tuning (`INGEST_COPY_BATCH_SIZE=50,000` vs. `310-overview.md`'s
  original 1k-5k recommendation) — no evidence either number is causing
  a problem; not touched here.
- Any dedup/idempotent-insert mechanism for `MODULE_UNIT_SPECIFIC` —
  explicitly rejected above.
- The pre-row-loop setup phase (`_resolve_carbon_report_modules`,
  `base_csv_provider.py:899`) uses `flush()` not `commit()`, so it's
  folded into the first batch's transaction rather than committing on
  its own. Noticed while verifying the "anything left to relieve"
  question above; separate from this fix and not addressed here — flag
  for a future pass if a `MODULE_PER_YEAR` file spanning many
  not-yet-provisioned units turns out to make that phase slow enough to
  matter (it self-heals on retry either way, unlike the problem this
  plan fixes).
