---
status: proposed
issue: 2527
last_updated: 2026-09-10
title: "2527 B — can we get rid of the advisory locks?"
summary: "Ten ways to remove or shrink the factor/recalc advisory locks, ranked. The locks guard two different invariants, not one: factor read/write consistency (I1) and no double-write to data_entry_emissions (I2). I1 is a READ COMMITTED artifact — the recalc issues many factor SELECTs in one transaction and each gets its own snapshot. I2 exists only because data_entry_emissions has no unique constraint. Both have cheaper fixes than a mutex, and the top three together would delete most of the locking. Also states the case FOR the lock, which is stronger than it looks: the 0.3 s vs 3 min DELETE measurement."
---

# 2527 B — can we get rid of the advisory locks?

**This analysis is not a reason to hold #2708.** That PR narrows an
existing lock, is measured, and is correct on its own terms. Everything
below is what comes after it.

## What the locks actually guard — two invariants, not one

`tasks/_locks.py` reads as one mechanism. It is two, with different
causes and different cheapest fixes. Almost every wrong instinct about
this code comes from treating them as one thing.

### I1 — a recalc must not read factors mid-rewrite

`factor_ingest` rewrites the `factors` rows for a `(module_type_id, year)`
scope: an UPSERT stamping `last_seen_job_id`, then
`delete_stale_for_year` hard-deleting everything the upload did not
cover (`factor_repo.py:304`). `emission_recalc` reads those factors.

**Why this is possible at all: the engine runs at READ COMMITTED.**
`db.py:292` sets no `isolation_level`, so Postgres's default applies, and
under READ COMMITTED _every statement gets its own snapshot_. If the
recalc read factors in exactly one statement, this hazard would not
exist — that statement would be atomic.

It does not:

- `FactorResolver._get_maps` issues one bulk `list_by_data_entry_type`
  per `(det, year)`, memoized (`factor_resolver.py:98`).
- Strategy-B (classification-query) lookups issue **one query per
  distinct `(kind, subkind, context, year)` criteria** across the slice
  (`emission_recalculation.py:112-118`).
- `module_emission_recalc` loops dets, so `_get_maps` fires per det.

So a slice does many `SELECT`s against `factors` inside one transaction,
and a concurrent `factor_ingest` commit can land between two of them.
The workflow's own comment says so: _"The factor table is held stable for
the slice by the recalc advisory lock."_ The lock is load-bearing
**because of the isolation level and the statement count**, not because
factor consistency intrinsically needs a mutex.

### I2 — two scoped recalcs must not double-write the same module

`data_entry_emissions` has **no unique constraint**. `_locks.py` says it
outright: _"nothing else stops two identical scoped recalcs from
double-writing."_ The `_MODULE_WRITE_LOCK_CATEGORY` (1238) lock exists
solely to substitute for a constraint the schema does not have.

This is a data-integrity property enforced at runtime by a mutex. That is
the part of the design that should feel wrong, and it is the cheapest to
fix.

### The third thing, which is not an invariant

The pre-import DELETE cascade. `ingestion_tasks.py:88-93`:

> the pre-import DELETE's ON DELETE CASCADE into `data_entry_emissions`
> takes row locks on the very rows a still-running `emission_recalc` of
> the previous pipeline is rewriting. Without this lock the DELETE sits
> in a row-level lock queue mid-statement (**observed: 0.3 s vs 3 min for
> the same 9.5k-row delete**).

This is not correctness. It is the strongest _performance_ argument for
the lock, and any proposal that deletes the lock has to say what happens
to that DELETE. Several below die on it.

## The case FOR the lock

Worth stating plainly, because the instinct "locks in SQL are bad" is
right in general and partly wrong here.

**What is genuinely good about `pg_advisory_xact_lock`:**

1. **It is measured, and it made things faster, not slower.** 0.3 s vs
   3 min. The lock does not _add_ serialisation — it _relocates_ it from
   unpredictable mid-statement row-level queueing to one cheap,
   well-known gate. Removing it does not remove the contention; it
   returns it to a worse form.
2. **Crash-safe for free.** It is released when the transaction ends —
   commit, rollback, connection drop, pod OOM-kill. No lease expiry, no
   heartbeat, no clock skew, no stuck-lock runbook entry. Every
   application-level alternative (a FIFO lease, a Redis lock, a
   `claimed_by` column) has to re-solve this, and most get it subtly
   wrong.
3. **Deadlock-free by construction.** Fixed acquisition order — factor
   gate first, module second — documented and asserted.
4. **Free.** No table, no WAL, no disk. It lives in shared memory.
5. **Observable.** `pg_locks` shows exactly who holds and who waits.
6. **Already narrowed.** #2708's shared-mode split means two units'
   uploads of the same module and year now run concurrently. Most of the
   over-serialisation the instinct objects to is what that PR removes.

**Where the instinct is right:**

1. 🔴 **The hold time is the entire handler transaction.** Acquired
   before `_run_ingest`, released when the runner commits — seconds to
   minutes for a large CSV. The _guarantee_ needs the lock only across
   the factor reads. This is a choice, not a property of advisory locks,
   and it is the single biggest defect.
2. 🔴 **A blocked worker holds a DB connection doing nothing.** With
   `MAX_CONCURRENT_JOBS` per pod and a DBaaS PgBouncer server pool
   around 35, lock waits convert directly into connection pressure —
   the exact failure mode of the 2026-08-31 exhaustion incident (#2566)
   and the PgBouncer work (#2689). This is the strongest anti-lock
   argument and it is specific to this deployment.
3. **It is invisible to the job metrics.** Time spent waiting on the
   lock lands inside `started_at → finished_at`, i.e. it is reported as
   _work_, not _queue_. Task 0's queue-vs-work split therefore
   mis-attributes it, and the load-test numbers hide it.
4. **Correctness by convention.** Nothing forces a future writer to take
   the lock. A constraint cannot be forgotten; a mutex can.

## The ten options, ranked

Scored on three axes, 0–5 each, 15 total:

- **Correct** — does it actually preserve the invariant it targets?
- **Small** — inverse blast radius; 5 is a few lines, 0 is a rewrite.
- **Gain** — how much real concurrency it unlocks.

|   # | Option                                                         | Targets     | Correct | Small | Gain | **Score** |
| --: | -------------------------------------------------------------- | ----------- | ------: | ----: | ---: | --------: |
|   1 | Hold the lock only across the factor reads                     | I1          |       5 |     4 |    5 |    **14** |
|   2 | Add the missing unique constraint on `data_entry_emissions`    | I2          |       5 |     4 |    4 |    **13** |
|   3 | `REPEATABLE READ` for the recalc transaction                   | I1          |       4 |     5 |    4 |    **13** |
|   4 | Serve Strategy-B from the bulk map — one factor read per slice | I1          |       5 |     3 |    4 |    **12** |
|   5 | Soft-delete factors (`retired_at`) instead of hard DELETE      | DELETE      |       4 |     4 |    4 |    **12** |
|   6 | Append-only, generation-stamped factors                        | I1 + DELETE |       5 |     2 |    5 |    **12** |
|   7 | Shadow table + pointer swap for factor loads                   | I1 + DELETE |       4 |     2 |    5 |    **11** |
|   8 | `SERIALIZABLE` + retry                                         | I1 + I2     |       4 |     4 |    2 |    **10** |
|   9 | Optimistic staleness stamp + recompute sweep                   | I1          |       2 |     3 |    5 |    **10** |
|  10 | FIFO / partitioned queue, one consumer per scope               | I1 + I2     |       4 |     2 |    1 |     **7** |

### 1. Hold the lock only across the factor reads — 14

Today the lock is `pg_advisory_xact_lock`, released at commit, so it
spans the whole ingest. Switch to a session-scoped
`pg_advisory_lock`/`pg_advisory_unlock` (or a nested transaction) taken
immediately before the factor load and released immediately after.
Compute and write with no lock held.

Hold time drops from _minutes_ to _milliseconds_, with the same
guarantee. Best win per line changed in the whole list. Requires the
factor reads to be gathered up front — which is option 4, so these two
belong together.

Caveat: `pg_advisory_unlock` must run in a `finally`; session-scoped
locks do **not** auto-release on rollback, only on disconnect. That
gives back some of the crash-safety in the "case for" section above, so
it needs to be written carefully once, in `_locks.py`, not per caller.

### 2. Add the missing unique constraint — 13

`data_entry_emissions` should already have one; the module lock is
standing in for it. Candidate natural key:
`(data_entry_id, emission_type_id, scope)`.

Deletes `_MODULE_WRITE_LOCK_CATEGORY` outright, and turns a double-write
from a silent duplicate into a loud failure — or an idempotent
`ON CONFLICT DO UPDATE`, which is what the recalc actually wants.

Prerequisite: verify the key holds in current data and dedupe first. It
is a migration, not an architecture change.

### 3. `REPEATABLE READ` for the recalc transaction — 13

`session.connection(execution_options={"isolation_level": "REPEATABLE READ"})`
on the recalc's data session. One snapshot for every factor `SELECT` in
the transaction, so I1 cannot occur regardless of statement count. This
is the root-cause fix and it is one line.

Two honest caveats:

- It does **not** fix the FK CASCADE. A recalc that computed against a
  factor a committed writer then deleted will fail at write time on the
  FK — fail-loud, which the guardrails prefer, but it needs a retry
  path.
- It does nothing for I2.

### 4. Serve Strategy-B from the bulk map — 12

If every factor a slice needs comes from **one** `SELECT`, READ COMMITTED
already makes that read atomic and I1 disappears with no isolation change
and no lock. Strategy A already works this way; Strategy-B's
classification queries are the only reason there are many reads.

Doubles as a query-count win on the path #2527 is already attacking, and
it is the enabler for option 1.

Cost: reimplementing classification matching in Python over the loaded
set. Non-trivial, and it must match the SQL semantics exactly or it
silently prices things differently — the failure class this repo cares
most about.

### 5. Soft-delete factors — 12

Replace `delete_stale_for_year`'s hard DELETE with a `retired_at` stamp.
No DELETE, therefore no `ON DELETE CASCADE` into
`data_entry_emissions`, therefore **the 3-minute row-lock queue that
motivated the lock stops existing.**

Also historically correct for a carbon calculator: emissions keep
pointing at the factor they were actually computed with, which is what
GHG Protocol restatement expects. Readers add `WHERE retired_at IS NULL`.

Cost: every factor read gains a predicate (a partial index covers it),
and a retention policy is needed eventually.

### 6. Append-only, generation-stamped factors — 12

The strongest answer, and the most work. `last_seen_job_id` is already a
monotonic generation marker — lean on it. A factor upload inserts a new
generation instead of UPDATEing rows in place; readers pin the
generation current when their job started.

I1 becomes structurally impossible: a reader never sees a partial set,
at any isolation level, with any number of statements. Combined with
option 5 there is nothing left for the factor gate to protect, and it
can be deleted.

Cost: schema, every factor reader, a retention policy, and the UPSERT
becomes an INSERT. This is a quarter, not an afternoon.

### 7. Shadow table + pointer swap — 11

Load into `factors_staging`, flip a `current_generation` pointer in one
tiny transaction. Readers resolve through the pointer. The write becomes
instantaneous from a reader's perspective.

Blocked by `data_entry_emissions.primary_factor_id`'s FK to `factors.id`
— you cannot FK to a view, and swapping tables under an FK is not
something to do on a live system. Would need option 6's model anyway, at
which point 6 is the better version of this idea.

### 8. `SERIALIZABLE` + retry — 10

Catches both invariants: read-write conflicts abort with `40001` and the
job retries.

Poor fit for _this_ workload. SSI's predicate locks over a multi-thousand
-row ingest produce false-positive aborts, and retrying a 5k-row ingest is
expensive. Plausible for the short recalc transaction alone; a bad idea
for the ingest path.

### 9. Optimistic staleness stamp + sweep — 10

Stamp emissions with the factor generation they used; a background sweep
recomputes anything stale. Zero locks, fully parallel.

Rejected on posture, not mechanics: it deliberately publishes numbers
known to be possibly-stale for a window, and relies on a sweep to
converge. That is exactly the _"silent wrong totals"_ failure this
codebase's guardrails name first. Listed because it is a legitimate
architecture, not because it fits here.

### 10. FIFO / partitioned queue, one consumer per scope — 7

The instinct behind the question, so it deserves a straight answer: **it
is still a lock, and a worse one.**

Routing every job for a `(module_type, year)` to a single consumer
serialises _strictly more_ than today — #2708 already lets two units'
uploads of the same scope run concurrently, and a single-consumer
partition would take that back. It also re-introduces everything
`pg_advisory_xact_lock` gives free: lease expiry, crashed-worker
detection, rebalancing, clock skew.

A connection **pool** is orthogonal — it bounds resource usage and
enforces no invariant at all.

The one real advantage: wait time becomes _visible_ as queue time in the
job metrics instead of hiding inside work time (con 3 above). That is a
genuine observability gain, and it can be had far more cheaply by
recording lock-wait duration around the acquire call.

## The implementation plan

**The ranking above is not the sequence.** Two things make a naive
"do 1, then 2, then 3" wrong:

- **Options 3, 4 and 1+4 are alternative routes to the same outcome**, not
  successive steps. Each independently makes I1 safe. Doing all three is
  doing the same job three times.
- **Most of them are gated on a number nobody has** — the actual lock
  wait. Building against an assumed cost is what produced the retracted
  21.9 s claim and the 310-f mis-diagnosis.

So the plan is four phases, and two of them may end with "do nothing".

### Phase 0 — measure, and verify the key. Blocks everything else.

- [ ] **P0.1 — instrument the lock wait.** `perf_counter` around the
      `execute` in `acquire_factor_recalc_lock`; log duration, mode
      (shared/exclusive), scope, handler. An afternoon.
- [ ] **P0.2 — run the load test** on dev **after #2708 is deployed** —
      `make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20` — and read
      the wait distribution. #2708's narrowing may already have taken most
      of it.
- [ ] **P0.3 — verify the uniqueness key.** Read-only; the query is below.

P0.3's query, kept out of the list because a code block nested in a task
item is not stable under `prettier`:

```sql
SELECT data_entry_id, emission_type_id, scope, count(*)
FROM data_entry_emissions
GROUP BY 1, 2, 3 HAVING count(*) > 1 LIMIT 20;
```

Empty → Phase 1 is a clean migration. Non-empty → **I2 has already been
violated in production**, and Phase 1 becomes an incident rather than a
cleanup. That is the single result most likely to change this plan.

**Gate:** if P0.2 shows the post-#2708 wait is negligible, Phases 2 and 3
are **not implemented**. Phase 1 still ships — it is correctness, not
performance.

### Phase 1 — the unique constraint. Unconditional.

Option 2. Ships whatever the measurement says, because a mutex standing
in for a schema constraint is wrong independently of being slow.

- [ ] **P1.1** — dedupe whatever P0.3 found, if anything.
- [ ] **P1.2** — migration adding the unique constraint on
      `(data_entry_id, emission_type_id, scope)` (key confirmed by P0.3).
- [ ] **P1.3** — make the recalc write idempotent against it —
      `ON CONFLICT DO UPDATE` is what `bulk_replace_for_entries` actually
      wants.
- [ ] **P1.4** — **delete `_MODULE_WRITE_LOCK_CATEGORY`** and the
      `carbon_report_module_id` branch of `acquire_factor_recalc_lock`.
      Half the locking goes with it.
- [ ] **P1.5** — regression test: two concurrent identical scoped
      recalcs produce one row set, not two. This is the test that would
      have caught I2 without a lock.

### Phase 2 — make I1 safe without a long-held lock. Pick ONE route.

Gated on P0.2. If it runs, choose a single route — cheapest first:

| Route  | What                                                                            | Cost                                          | Risk                                                               |
| ------ | ------------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| **2a** | Option 3 — `REPEATABLE READ` on the recalc's data session                       | one line                                      | FK-cascade failures need a retry path                              |
| **2b** | Option 4 — serve Strategy-B from the bulk map, one factor read per slice        | reimplement classification matching in Python | must match SQL semantics exactly or it silently prices differently |
| **2c** | Option 1+4 — gather the reads, then hold a session-scoped lock across only them | 2b plus lock plumbing                         | `pg_advisory_unlock` in a `finally`; no auto-release on rollback   |

Try **2a** first: one line, and it is the root-cause fix. Fall through to
2b only if the retry path proves worse than the reimplementation — 2b is
also a query-count win, so it is not wasted either way. 2c only if both
2a and 2b are rejected, since it is the only one that keeps a lock.

- [ ] **P2.1** — implement the chosen route.
- [ ] **P2.2** — test that a factor rewrite committed mid-recalc produces
      either correct numbers or a loud failure, never half-loaded values.
- [ ] **P2.3** — if I1 no longer needs it, **delete the factor gate for
      the recalc path** and re-measure.

### Phase 3 — the DELETE cascade. Separate trigger.

Option 5, soft-delete. Do **not** fold this into Phase 2: it addresses
the 0.3 s vs 3 min row-lock queue, which is a different problem from
either invariant, and Phase 2 may leave it untouched.

**Trigger:** implement when Phase 2 has removed the factor gate _and_ a
re-measurement shows the pre-import DELETE queueing again. Until the gate
is gone, the DELETE is not contending, so there is nothing to fix.

- [ ] **P3.1** — `retired_at` on `factors`, partial index, readers filter.
- [ ] **P3.2** — `delete_stale_for_year` stamps instead of deleting.
- [ ] **P3.3** — retention policy for retired rows.

### Shelf — with explicit triggers, so nobody re-proposes them

| Option                           | Status                                                                                                                                                                                                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6 — append-only factors          | **Not now.** The endgame if factor history becomes a requirement in its own right — GHG restatement is the likely forcing function. A quarter, not an afternoon. Phase 3 delivers most of its practical benefit for a fraction of the cost.               |
| 7 — shadow table + swap          | **Blocked.** `primary_factor_id`'s FK to `factors.id` makes it unworkable without option 6's model first, at which point 6 is the better version.                                                                                                         |
| 8 — `SERIALIZABLE`               | **Rejected for the ingest path.** SSI predicate locks over a multi-thousand-row transaction abort on false positives, and retrying a 5k-row ingest is expensive. Reconsider only for the short recalc, and only if 2a's retry path is being built anyway. |
| 9 — optimistic staleness + sweep | **Rejected on posture.** Publishes knowingly-stale numbers for a window. That is the silent-wrong-totals failure the guardrails name first.                                                                                                               |
| 10 — FIFO / partitioned queue    | **Rejected.** Still a lock, serialises strictly more than #2708 already does, and re-introduces lease expiry and crashed-worker detection. Its one merit — visible wait time — is P0.1, at a fraction of the cost.                                        |

### What this adds up to

If Phase 0 says the wait is negligible: **one migration** (Phase 1), and
half the locking is gone on correctness grounds alone.

If it says otherwise: Phase 1 plus **one line** (2a), and the factor gate
goes too.

Neither outcome is an architecture rewrite, which is the point.

## What has not been verified

- **Whether `(data_entry_id, emission_type_id, scope)` is actually unique
  in production data.** Option 2 depends on it; nobody has run the count.
- **Whether the recalc's FK-cascade failure under option 3 is retried**
  or just errors the job.
- **The real lock-wait time.** Con 3 means it is not in the job metrics
  today. Logging the duration around `acquire_factor_recalc_lock` would
  size the whole problem before any of this is built, and is an
  afternoon's work.
