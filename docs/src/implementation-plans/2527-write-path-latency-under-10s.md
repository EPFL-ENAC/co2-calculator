---
status: in-progress
issue: 2527
last_updated: 2026-08-30
title: "2527 items 1-3 — the three write paths over the 10 s alert bucket"
summary: "JobLatencySLOBreach fires on a 10 s bucket; uploads, plan prefill and plan mutations sit above it under load. Per-path verdict from the code: uploads and prefill are queue-plus-CPU, not per-row SQL; plan PATCH/DELETE round trips were already trimmed by #2449 Track B, so its residual is cascade data volume — which fires #2449's own deferred trigger for Track A. One correctness fix (module-scoped emission_recalc children are silently dropped by EMISSION_RECALC_DEDUP) must land before any baseline, because it flatters today's upload numbers."
---

# 2527 items 1-3 — the three write paths over the 10 s alert bucket

## Mandate

`JobLatencySLOBreach` alerts on a 10 s bucket. The maintainer's call
(#2529 §3): move the code, not the threshold. Measured on the dev DB with
the #2295 dataset (600 units, ~8.4M entries):

| Path                              | Measured (#2529)                                     |
| --------------------------------- | ---------------------------------------------------- |
| CSV upload -> ingested (FLOW)     | 2.2 s median local / 8 s dev; max 63 s @5, 184 s @20 |
| Simulator-plan prefill (FLOW)     | median **42 s**, max 153 s @40                       |
| Plan PATCH / DELETE (synchronous) | PATCH 2.0 s med, DELETE 2.4 s med, **p95 14 s @40**  |

Scope: items 1-3 only. Items 4-10 and the `kg_co2eq` denormalization are
separate plans.

## Verdicts — and the one measurement that confirms each

Static reading has been confidently wrong in this exact subsystem before
([310-f](310-f-ingestion-per-row-efficiency.md): the first cut guessed
line-level suspects, the profiler showed 97% of the time in an unrelated
per-row factor-key scan). So each verdict below is a **hypothesis with a
named discriminator**, and Task 0 runs them before any code changes.

| Path         | Dominant cost (hypothesis)                                                                   | Code evidence                                                                                                                        | Confirming measurement                                                |
| ------------ | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| CSV upload   | **(a) queue + lock serialization**, then (c) CPU. Not per-row SQL.                           | 3 sequential job hops per upload; per-pod `MAX_CONCURRENT_JOBS=4`; one unit-agnostic advisory lock per `(module_type_id, year)`      | `created_at -> started_at` vs `started_at -> finished_at` per job row |
| Prefill      | **(c) heavy per-entry CPU inside one serialized job**, queue second. Not per-row SQL.        | one job prefills every plan year sequentially; every entry of every year re-priced through `prepare_create`; SQL already batched     | same job-timestamp split + the `Recalc profile` log line              |
| PATCH/DELETE | **(c) cascade DB work proportional to prefilled entry volume.** Round trips already trimmed. | #2449 measured 7-22 statements and 20-220 ms on stage-sized plans; the same statement count against a prefilled 5-year plan is 2.4 s | DELETE an empty plan vs a prefilled one, same code path               |

### Why "not per-row round trips" for uploads and prefill

- The CSV row loop does no per-row SQL: factors are in-memory, module ids
  come from an in-memory map, years from `_year_cache`, member uniqueness
  is seeded in one bulk query
  (`base_csv_provider.py:953-967`, `:1185-1353`). 310-f re-measured it at
  0.17 ms/row after the memo fix.
- The recalc workflow resolves factors once per slice, memoizes
  Strategy-B lookups, and writes in one batched `bulk_replace_for_entries`
  (`workflows/emission_recalculation.py:107-125`, `:227-246`).
- Prefill copies with `bulk_insert_returning_ids` and re-prices with the
  same batched path (`simulator_plan_service.py:861-888`, `:890-930`).

The remaining per-entry cost is Python CPU (Pydantic validate +
`prepare_create`), on a pod that requests **1 CPU and also serves HTTP**
(`helm/values.yaml`, backend deployment). That is why parallelism makes
the tail explode while the median stays flat.

## Task 0 — measure before changing anything

Instruments already exist; nothing new is needed.

- [ ] Run `make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20` and
      `PERF_CLASSES=PlanUser PERF_USERS=40` against dev, then split queue
      from work over the job rows of that window:

      ```sql
          SELECT job_type,
                 count(*),
                 percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY extract(epoch FROM started_at - created_at)) AS queue_p50,
                 percentile_cont(0.5) WITHIN GROUP (
                   ORDER BY extract(epoch FROM finished_at - started_at)) AS work_p50,
                 percentile_cont(0.95) WITHIN GROUP (
                   ORDER BY extract(epoch FROM finished_at - created_at)) AS total_p95
          FROM data_ingestion_jobs
          WHERE created_at > now() - interval '1 hour'
          GROUP BY job_type ORDER BY total_p95 DESC;
          ```

- [ ] Read the `Row-loop profile` and `Recalc profile` lines from the same
      run (`base_csv_provider._log_row_loop_profile`,
      `emission_recalculation.py:263-274`) — they already break per-entry
      time into validate / prepare / remainder.
- [ ] DELETE discriminator: time `DELETE /v1/project-plans/{id}` for a
      plan with no prefilled years and for a prefilled 5-year plan on the
      perf dataset. Scales with entries -> cascade; scales with report
      count -> round trips (and then Phase D changes).
- [ ] Record all three in this plan before writing code. **If a
      hypothesis is wrong, the matching phase below is rewritten, not
      implemented.**

## Phase A — the dedup drop (correctness; blocks the baseline)

`EMISSION_RECALC_DEDUP` scopes on `(module_type_id, data_entry_type_id,
year)` across all active rows fleet-wide (`tasks/_chain.py:146-150`,
index `uq_emission_recalc_active`). When #1219 introduced it (2026-05-19)
recalc children were whole-slice, so the "an earlier pipeline already owns
that recalc" reasoning held: the owning job covered our rows too.

On 2026-06-12 (`a6dd48692`, "x100 data-entry emissions") the child gained
a module scope — `config.carbon_report_module_ids`, pinned from the
parent's own module (`tasks/ingestion_tasks.py:557-572`,
`emission_recalculation_tasks.py:365-378`). The dedup key did not follow.

Consequence: two uploads to the **same `(module, det, year)` but different
units**, overlapping in time, produce one recalc scoped to the first
unit's module. The second upload's child is skipped, its
`expected_recalc` is 0, its pipeline reports done, and its freshly
ingested rows never get `data_entry_emissions` rows — a silent wrong
total, the failure mode the guardrails single out. At 20 parallel
uploaders over a handful of module/year combos this is the common case,
not the corner case.

Two consequences for this plan:

1. It is a correctness bug, and it ships first.
2. **Today's upload FLOW numbers are flattered by dropped work.** Fixing
   it will make measured upload times go up before the rest of Phase B
   brings them down. Any baseline taken before this lands is not
   comparable.

- [ ] Narrow the dedup to what it was meant to collapse: whole-slice
      recalcs. Add `AND (meta -> 'config' -> 'carbon_report_module_ids')
    IS NULL` to the `uq_emission_recalc_active` partial-index predicate
      (generated migration, `make db-revision`), and pass
      `dedup_config=None` for module-scoped chains. Scoped recalcs touch
      disjoint row sets — they never needed collapsing.
- [ ] Regression test (pytest, Postgres fixture — SQLite cannot express
      the partial index): two module-scoped `csv_ingest` parents for the
      same `(module, det, year)` and different modules both chain a live
      child; two unscoped parents still collapse to one.
- [ ] Check for existing damage on dev/stage: entries in the perf window
      with no `data_entry_emissions` row for a FINISHED pipeline. Repair
      by re-running the module-scoped recalc, not by widening a query.

## Phase B — CSV upload -> ingested

### B1. Stop serializing unrelated units on the factor lock

`acquire_factor_recalc_lock` keys on `(module_type_id, year)` only
(`tasks/_locks.py:38-44`). Three handlers take it exclusively:
`factor_ingest` (writer), `csv_ingest` / `api_ingest`
(`ingestion_tasks.py:73`, `:109`), and `emission_recalc`
(`emission_recalculation_tasks.py:330`). So a unit's 200-row upload waits
head-to-tail behind every other unit's upload of the same module and
year, and behind their recalc children.

Hold window is file-size dependent: `pg_advisory_xact_lock` releases at
the transaction end, and `_process_batch` commits `data_session` at
`base_csv_provider.py:1548`. Files under `INGEST_COPY_BATCH_SIZE`
(50 000 rows) hit that commit only at finalize, so they hold the lock for
essentially the whole ingest; larger files release it mid-parse.

The invariant to preserve is only _factor writes vs factor reads_. Two
data ingests into different modules of different units do not conflict on
factors at all; the pre-import DELETE cascade they do conflict on is
per-`carbon_report_module`, not per-module-type.

- [ ] Split the lock: `factor_ingest` and unscoped `emission_recalc` keep
      `pg_advisory_xact_lock(cat, module_type, year)` (exclusive);
      `csv_ingest` / `api_ingest` and module-scoped `emission_recalc` take
      `pg_advisory_xact_lock_shared` on that key **plus** an exclusive
      lock on a `carbon_report_module_id`-derived key.
- [ ] Test with the Postgres fixture: a factor ingest still excludes a
      concurrent recalc for its scope; two data ingests into different
      modules run concurrently.

### B2. Job hops and where the work runs

One upload is three sequential jobs — `csv_ingest` -> `emission_recalc`
(one per det) -> `aggregation` — each paying a semaphore wait, a claim,
and (with inline dispatch off) up to `POLLER_INTERVAL_SECONDS`. Nothing
here is wrong; it is simply three queue entries per upload on 4 slots per
process (`runner.py:135`, `config.py:488`).

- [ ] Size the queue against the budget, not upward by reflex — see
      [Concurrency budget](#concurrency-and-connection-budget). #2529
      measured ingestion **DB-CPU-bound at 3.7 cores for 20 parallel
      uploads**: more concurrent ingest jobs buy nothing and cost
      connections.
- [ ] Chunked ingest jobs (#2449's original idea, issue #2527 item 1's
      lever) stay **deferred** until Task 0 shows a single `csv_ingest`
      work time above the bucket on its own. Splitting a job that is
      already fast into chunks that queue behind each other makes the
      tail worse.

## Phase C — simulator-plan prefill

One PATCH enqueues **one** job for every year of the range
(`api/v1/simulator_plan.py:49-86`), and the handler walks them
sequentially: per report, empty + copy every reference-scoped module, then
re-price every entry of the report (`simulator_plan_service.py:420-458`).
The docstring records 21.9 s on dev for a single year of a ~5k-entry
module. A 5-year PlanUser flow is that, five times, in one job holding one
of four slots.

- [ ] **C1 — copy without a Python round trip.** `prefill_module_from_
    reference` reads every source row into memory, rebuilds a dict per
      row and bulk-inserts it back (`:729-761`). Replace with one
      `INSERT INTO data_entries (...) SELECT ...` per (module, plan year),
      building the JSON `data` server-side (`data || jsonb_build_object(
    'percentage_of_reference_year', 100, 'source_data_entry_id', id)`).
      Rows stop crossing the wire; the delete-then-insert shape and its
      idempotency are unchanged.
- [ ] **C2 — do not re-price what was copied at 100%** (measurement-gated,
      biggest win if it holds). `resolve_factor_year`
      (`utils/factor_year.py:11-37`) returns the reference year for a plan
      year and its own year for the reference Calculator report — the same
      year — so a 100% snapshot copy has the same inputs as its source.
      Where that holds, `data_entry_emissions` can be copied set-based
      from the source entries instead of recomputed. Covered set is
      **prefilled percentage-based types only**: plain-copy modules
      recompute from row data, headcount aggregates many member rows into
      one grid row, derived types are generated. Gate: a test that
      computes both ways on a fixture and asserts identical rows. If it
      does not hold exactly, drop C2 — no approximations.
- [ ] **C3 — one job per report only if C1/C2 miss the gate.** More
      parallel jobs cost connections and DB CPU; splitting is the fallback
      lever, not the first one.

## Phase D — plan PATCH / DELETE

[#2449](2449-plan-cascade-jobs.md) (delivered 2026-08-28) already
measured this path on stage and already shipped the round-trip trim
(Track B: bulk module insert, refresh chatter dropped). Its Track A —
`deleted_at` + 202 + `simulator_plan_purge` — was **deferred behind an
explicit trigger**:

> Implement when either: any plan DELETE / shrink-PATCH server span above
> **1 s** is observed, or plans start prefilling at calculator scale.

#2529 observed 2.4 s median and 14 s p95. **The trigger has fired.** So
path 3 is not a new design; it is 2449 Track A, implemented as written.

- [ ] Confirm with Task 0's empty-vs-prefilled discriminator that the cost
      is cascade volume (expected), not statement count (which would mean
      Track B regressed).
- [ ] Implement 2449 Track A verbatim: nullable `deleted_at` on
      `carbon_projects` + `carbon_reports`, read paths filter it, DELETE
      marks + enqueues `simulator_plan_purge` and returns **202 + job
      id**, shrink-PATCH and grant-off mark their reports and enqueue the
      same job, handler purges in ~5k-row batches with per-batch commits.
      No new state machine.
- [ ] Frontend: DELETE stops being 204. The plan disappears from the list
      because the list filters `deleted_at` — no polling UI needed for the
      common case; the job id is there for the pipeline view. Both locale
      files updated if any string changes.
- [ ] Purge-job idempotency test: re-running the handler after a partial
      purge converges (the batches are `DELETE ... WHERE` over rows that
      may already be gone).
- [ ] Statement-count assertion for PATCH, reusing the existing ratchet
      pattern from `test_headcount_post_statement_budget_pg.py`
      ([2050](2050-write-path-statement-budget.md)) — this is #2527 item
      6 applied to the path it was written for.

## Concurrency and connection budget

Per pod, one uvicorn process (`WORKERS=1` in `backend/Dockerfile`), so:

- Hard cap per pod = `DB_POOL_SIZE + DB_MAX_OVERFLOW` = 10 + 10 = **20**
  connections.
- Each running job holds ~2 (runner `job_session` + handler
  `data_session`), plus a short-lived heartbeat session per tick.
- `MAX_CONCURRENT_JOBS=4` -> 8-12 connections for jobs, 8-12 left for
  HTTP. At 2 replicas: 40 connections peak.
- The perf suite runs `--workers 4` locally, so local numbers are 4
  semaphores and 4 pools per host — 80 connections, 16 concurrent jobs.
  Local and dev concurrency are not comparable; say which you measured.

Levers, in order of preference:

- [ ] **Move jobs off the API pods**: `worker.enabled=true` already exists
      (`helm/values.yaml:251-269`, #2050 Track B) — 2 CPU requested, no
      HTTP neighbours, and the API pods stop losing their single core to
      recalc CPU. **Trap: `replicaCount: 1` gives 1 x 4 = 4 concurrent
      jobs, down from today's 2 x 4 = 8.** Ship it with
      `replicaCount: 2` (8 slots, 16-24 connections, unchanged
      fleet-wide) or raise `MAX_CONCURRENT_JOBS` on the worker only.
- [ ] Raise `MAX_CONCURRENT_JOBS` only if Task 0 shows queue wait
      dominating **and** the DB is not at the 3.7-core ceiling. Each +1 is
      ~2 connections per worker pod.
- [ ] Do not raise `POLLER_BATCH_LIMIT`; the in-flight guard
      (`_poller.py:38-66`) already stops re-dispatch pile-ups, and queued
      tasks holding no connection is the design.

## Acceptance gate

Same command in, same row out — the FLOW medians (#2529 §1 is the
reference baseline):

```bash
make perf-load PERF_CLASSES=PlanUser      PERF_USERS=40
make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20
```

- `FLOW plan lifecycle` median **< 10 s** (from 42 s), p95 under the
  15 s prefill SLO of #2529 §3.
- `FLOW csv upload e2e` median **< 10 s** on dev, and the max at 20
  parallel uploaders under the 60 s/file SLO (from 184 s).
- Read endpoints not regressed: `PERF_CLASSES=ExplorerReadUser
PERF_USERS=50` worst-endpoint p95 no worse than the #2529 baseline —
  the worker split and lock changes move load around, so this is the
  guard that they did not move it onto the request path.
- Both runs after Phase A, and Phase A's own before/after is reported
  separately so the correctness fix's cost is visible rather than netted
  out.

## Invariants this plan must not break

- **Idempotent pipelines.** Every handler here can be re-run after a
  stale-job sweep ([1559](1559-ingestion-idempotent-tmp-to-processing-move.md),
  [1219](1219-stuck-jobs-and-pipeline-progress.md)): prefill empties
  before rebuilding, the purge job deletes by predicate, the set-based
  copy keeps the delete-then-insert shape.
- **No silent fallbacks.** Phase A exists because a dedup skip became one.
  A dropped recalc must be a loud error or a real queued job, never an
  empty emissions set behind a green badge.
- **Route -> service -> repo, commit in the route; workflows own their
  own commits.** Note the existing exception this plan inherits rather
  than introduces: `_process_batch` commits `data_session` mid-handler
  (`base_csv_provider.py:1548`), which both breaks that contract and ends
  the advisory-lock transaction early. Any chunked-ingest follow-up must
  deal with it; this plan only documents it.
- **No backward-compat dual paths.** The 202 DELETE replaces the 204 in
  the same PR as the frontend change.

## Open questions for the maintainer

1. Phase A first, as written? It fixes a silent-wrong-numbers bug but
   makes the upload FLOW numbers worse before Phase B improves them.
2. Worker split (`worker.enabled=true`, `replicaCount: 2`) — ops change,
   needs your call and a dev deploy before the gate run is meaningful.
3. C2 (copying emissions for 100% snapshot rows) is the difference
   between "prefill is 3x faster" and "prefill is 10x faster", and it is
   the only item here that could be subtly wrong. Worth the equivalence
   test, or leave prefill re-pricing everything?
