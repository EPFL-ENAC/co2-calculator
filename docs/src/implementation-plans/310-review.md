---
status: in-progress
issue: 310
last_updated: 2026-05-06
title: "310 — Plan Review"
summary: "Code-grounded verification of the 310-* plan series against the actual repository state."
---

# 310 — Plan Review

Verified plans against actual code in `backend/app/models/data_ingestion.py`,
`backend/app/repositories/data_ingestion.py`, `backend/app/tasks/*`,
`backend/app/api/v1/data_sync.py`, `backend/app/models/factor.py`.

Three showstoppers, several real-but-smaller issues, and one strategic question.

---

## Showstoppers — need answers before any code is written

### 1. BackgroundTasks chaining is fragile, not "needs threading through"

Plans B (`_enqueue_stale_recalculations`), C (DAG chaining via `next_job`),
and D (chained ingest → recalc → aggregation) all assume that calling
`background_tasks.add_task(...)` **from inside a running background task**
schedules the next task. This is implementation-defined Starlette behavior,
not a documented API: BackgroundTasks runs queued tasks sequentially after
the response; adding to the list during iteration may or may not be picked
up depending on internal iteration mechanics, and the BackgroundTasks
instance is per-request and goes out of scope after its loop ends.

**This is the foundational decision for everything downstream.** Pick one
before writing more plan content on top:

- **(a)** `asyncio.create_task(run_recalculation_task(...))` from within
  the running task — tied to the same event loop, no Starlette involvement,
  but the pod can't crash mid-chain
- **(b)** Drop in-task chaining entirely; let the next job sit in
  `state=NOT_STARTED` and add a tiny poller (cron-like loop, separate thread,
  or `/sync/jobs/run-pending` endpoint) that picks them up
- **(c)** Add a real worker process that polls
  `SELECT … FOR UPDATE SKIP LOCKED`

Option (b) is the cleanest with what we have. Option (a) is what we
_implicitly_ relied on already (existing `run_module_recalculation_task`
doesn't chain anywhere). Option (c) is what the reflexion doc actually
advocated.

### 2. `is_current` concurrency hole is bigger than Plan A claims to fix

Today's flow:

```
POST /recalculate-emissions/...    →   create job (state=NOT_STARTED, is_current=False)
                                   →   commit
                                   →   background_tasks.add_task(...)
[later, in BG task]                →   update_ingestion_job(state=RUNNING)
                                   →   mark_job_as_current(job)   ← is_current=True only here
```

Two operators clicking the same button simultaneously create **two**
`NOT_STARTED, is_current=False` rows. The partial unique index
`ix_data_ingestion_jobs_is_current_unique` (only enforces uniqueness
`WHERE is_current=true`) does not trip because neither row is current yet.
Both BG tasks then run; first one to call `mark_job_as_current` "wins" —
but the loser keeps running too.

Plan A's `claim_job` only sets `state=RUNNING`. It does **not** set
`is_current=True`. The race window between job creation and claim stays
wide open. Two pods can both successfully `claim_job` against two different
`job_id` values for the same `(module, det, year)` and both proceed.

**Fix**: `claim_job` must atomically set both `state=RUNNING` AND
`is_current=TRUE`, and integrate the unset-previous-current logic from
`mark_job_as_current`. The unique index then trips on the second claimer's
UPDATE, and only one survives. Plan A as written needs revision.

### 3. Factor classification ordering is a footgun, not a design

Plan B claims "classification JSON structure per handler is already
stable… `::text` cast is therefore stable." Verified: `factors.classification`
is `Column(JSON)` (factor.py:25), not JSONB. Postgres `JSON` preserves
insertion order verbatim from the original text; `::text` reflects whatever
order Python's `json.dumps` produced.

Today this works because Python dicts since 3.7 preserve insertion order
and every handler happens to insert keys consistently. The first PR that
builds a classification dict differently — e.g.
`{"sub_class": "X", "class": "Y"}` instead of
`{"class": "Y", "sub_class": "X"}` — silently creates a duplicate row.
The unique index will allow the dup because the text representation
differs.

**Fix options** (Plan B should pick one):

- Migrate `classification` to `JSONB` — Postgres sorts keys alphabetically,
  `::text` becomes deterministic regardless of insertion order
- Add a generated column
  `classification_key TEXT GENERATED ALWAYS AS (...) STORED` and index that
- Add a normalize helper in code and trust convention — but document loudly
  that any new caller must use it

JSONB migration is the smallest change that eliminates the class of bug
entirely.

---

## Smaller issues to fold into plan revisions

### Plan A

- **"Remove existing state=RUNNING line in tasks"** is wrong for
  `run_sync_task` (the provider sets state, not the task body) but right for
  `run_recalculation_task` (line 58-63) and `run_module_recalculation_task`
  (line 172-176). Plan needs to specify per-task what changes.
- `max_attempts` and `run_after` are added but no logic uses them.
  Be honest these are scaffolding for future retry logic, not active.
- The recovery 30-min timeout is a magic number — make it a settings
  constant.
- Recovery doesn't reset `attempts`, so a job recovered after exceeding
  `max_attempts` will fail to claim again. Probably want recovery to also
  decrement or reset `attempts`.

### Plan B

- `mark_job_as_current` already handles `data_entry_type_id IS NULL`
  (lines 184-189 of repo). Plan B's NULL fix is needed **only** for
  `module_type_id IS NULL`. Tighten the wording.
- `_enqueue_stale_recalculations` becomes throwaway code once Plan C lands
  (replaced by `next_job` payload). Acknowledge this so we don't
  over-invest.
- Missing: **factors that exist in DB but aren't in the new CSV** are
  silently kept. Today's `bulk_delete + insert` removes them. Need a
  "delete-not-in-set" step or accept stale rows. This is a real semantic
  regression not addressed in the plan.
- `EntityType` uses `SAEnum(..., native_enum=True)` — adding
  `GLOBAL_PER_YEAR=1` requires
  `ALTER TYPE entity_type_enum ADD VALUE 'GLOBAL_PER_YEAR'`. Plan B doesn't
  mention this migration step.

### Plan C

- `runner.py` calls `get_handler(job.job_type)` after claim — but jobs
  created before Plan C lands have `job_type=NULL`. Need a fallback or a
  backfill migration. Currently the plan assumes all jobs have `job_type`.
- `next_job` is singular but factor ingest fans out to N recalcs (one per
  stale type). Either `next_jobs: list` or fan-out happens at the handler
  level; plan needs to choose.
- `started_at` vs `locked_at` semantics aren't disambiguated:
  - `locked_at`: updates on every claim/retry
  - `started_at`: stays at first claim (for total-duration tracking)
  - Plan C says "set together" — that's wrong on retry. Specify both
    clearly.
- `pipeline_id` lifecycle is unspecified across A→B→C. Define: **endpoint**
  generates the UUID for multi-step flows and stores in the first job;
  downstream jobs inherit via `next_job` payload.

### Plan D

- **N aggregation jobs problem**: factor ingest fans out to N recalcs, each
  chains to aggregation = N aggregation jobs for one module. Need dedup
  ("skip if already queued for this module/year") or a coalesce mechanism.
- "Frontend shows spinner instead of 0 emissions" is hand-wavy. Today the
  UI shows `carbon_reports.stats` aggregated values. After CSV upload these
  are _stale_, not zero. The async path means stale → eventually correct.
  Spec the actual UX (show "Recalculating..." badge? show stale + warning?
  block module view?).
- The "manual data entry stays inline" carve-out **violates the
  one-writer-per-table rule** the plan claims to enforce. Both manual
  workflow and `emission_recalc` job write `data_entry_emissions`.
  Acknowledge this explicitly.
- Migration story: how do we ship D? Provider-by-provider? Big-bang?
  Plan doesn't specify.

### Overview

- "Atomic `claim_job()` method using FOR UPDATE SKIP LOCKED" is wrong.
  Plan A actually uses conditional UPDATE WHERE locked_by IS NULL. These
  are different patterns — SKIP LOCKED is for queue scanning, conditional
  UPDATE is for known-id claims. The conditional UPDATE is the right
  pattern; the overview text just needs fixing.
- "Plans A and B can be implemented in parallel" — actually B uses
  `job_type`, `pipeline_id`, `attempts` from A. They can ship in one PR but
  B can't start until A's migration is at least drafted.

---

## What we missed entirely

### Concurrency testing strategy

Plan A's test list
(`test_data_ingestion_repo.py — claim_job success/duplicate/wrong-state`)
is unit tests with mocked DB. They won't exercise the actual
atomic-UPDATE-with-WHERE race. We need an integration test that fires two
concurrent `claim_job` calls against a real Postgres and asserts exactly
one wins. Without this, we ship pod-safety code without proving it works
under contention.

### Plan D should probably be deferred, not pre-committed

The reflexion doc framed "one writer per table" as the principled
root-cause fix. But A's `claim+is_current` and B's auto-recalc may close
80% of the actual bug surface. Plan D is the most disruptive (frontend UX,
batching, table-ownership refactor across all providers, aggregation job
dedup) and deserves real production data on whether the remaining
concurrency pain is worth that cost. The overview presents it as
certain-to-ship; better to call it "deferred — measure first."

### Worker-poll loop is absent

The reflexion doc explicitly mentioned `SELECT … FOR UPDATE SKIP LOCKED`
workers. Our plans assume BackgroundTasks forever. With `run_after` and
`attempts` added to the model (Plan A), we have the data shape for a real
queue but no consumer. If we ever want retry-with-backoff or scheduled
jobs, we need a poller. Worth at least a sentence in the overview about
why we're deferring this.

### Batching

Reflexion doc: 1k–5k row batches for CSV, 50–200 entry batches for
emissions. None of A/B/C/D delivers this. As data volume grows,
single-transaction iterations will hold long locks. Should be at least
mentioned as Plan D scope or a separate plan.

---

## Recommended next step

1. Make the **chaining decision** (showstopper #1) — picks (a)/(b)/(c)
2. Revise **Plan A** to address showstopper #2 (is_current atomic) and
   the Plan-A smaller items
3. Revise **Plan B** to address showstopper #3 (JSONB migration) and
   the missing-classification-rows semantic
4. Decide whether **Plan D** ships at all or gets deferred
5. Revise **Plan C** to align with the chaining decision and clarify
   `pipeline_id` / `job_type` lifecycle
