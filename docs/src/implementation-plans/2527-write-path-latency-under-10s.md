---
status: in-progress
issue: 2527
last_updated: 2026-09-10
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
  (Since C1 the copy is one `INSERT ... SELECT` and only the headcount
  aggregation still goes through `bulk_insert_returning_ids`.)

The remaining per-entry cost is Python CPU (Pydantic validate +
`prepare_create`), on a pod that requests **1 CPU and also serves HTTP**
(`helm/values.yaml`, backend deployment). That is why parallelism makes
the tail explode while the median stays flat.

## Task 0 — measure before changing anything

Instruments already exist; nothing new is needed.

- [ ] Run `make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20` and
      `PERF_CLASSES=PlanUser PERF_USERS=40` against dev, then split queue
      from work over the job rows of that window (query below).
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

Queue vs work, per job type, over the run window:

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
GROUP BY job_type
ORDER BY total_p95 DESC;
```

## Phase A — the dedup drop (correctness; blocks the baseline) — shipped in #2541

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
      recalcs. Extend the `uq_emission_recalc_active` partial-index
      predicate with a "no module scope in `meta.config`" clause,
      and pass `dedup_config=None` for module-scoped chains. The index is
      declared in model metadata
      (`models/data_ingestion.py:407-424`), so `make db-revision`
      autogenerates the change — no hand-authored migration. Scoped
      recalcs touch disjoint row sets — they never needed collapsing.
- [ ] Regression test (pytest, Postgres fixture — SQLite cannot express
      the partial index): two module-scoped `csv_ingest` parents for the
      same `(module, det, year)` and different modules both chain a live
      child; two unscoped parents still collapse to one.
- [ ] Check for existing damage on dev/stage: entries in the perf window
      with no `data_entry_emissions` row for a FINISHED pipeline. Repair
      by re-running the module-scoped recalc, not by widening a query.

## Phase B — CSV upload -> ingested

> **Follow-on: can the locks go away entirely?**
> B1 narrows the factor gate; it does not question whether a gate is the
> right mechanism. That question is answered separately in
> `2527-b-lock-architecture-options.md` (PR #2718 — deliberately a draft
> until its Phase 0 measurement exists; the link goes in when it lands)
> — ten options ranked and phased. Its two findings that matter here: the
> "half-loaded factors" hazard exists **only because the engine runs at
> READ COMMITTED** and the recalc reads factors in many statements; and
> the per-module write lock exists **only because `data_entry_emissions`
> has no unique constraint**. Neither is intrinsic. Nothing there is a
> reason to undo B1.

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

- [x] Split the lock: `factor_ingest` and unscoped `emission_recalc` keep
      `pg_advisory_xact_lock(cat, module_type, year)` (exclusive);
      `csv_ingest` / `api_ingest` and module-scoped `emission_recalc` take
      `pg_advisory_xact_lock_shared` on that key **plus** an exclusive
      lock on a `carbon_report_module_id`-derived key.
- [x] Test with the Postgres fixture: a factor ingest still excludes a
      concurrent recalc for its scope; two data ingests into different
      modules run concurrently.

Delivered as `acquire_factor_recalc_lock(..., carbon_report_module_id=…)`
(`tasks/_locks.py`). The module lock gets its own category (1238) because
its keys are raw `carbon_report_module` ids and would otherwise collide
with a packed `(module_type, year)` key. Every caller acquires factor gate
first, module second, so no pair can deadlock.

**Divergence from the bullet: `api_ingest` keeps the exclusive gate.** The
bullet grouped it with `csv_ingest` on the premise that a data ingest's
delete is per-`carbon_report_module`. That is true of a unit-specific CSV
upload — which does no fleet-wide delete at all
(`base_csv_provider.py:888-906` gates the delete on `MODULE_PER_YEAR`) —
but false for an API feed: it is a complete yearly export, and
`_delete_existing_api_entries` deletes by `(year, det, source)` across
every unit's module (`base_tableau_api_provider.py:909-940`). No single
module bounds its writes, so it cannot share the gate even if its config
carries a pin. Pinned by
`test_api_ingest_handler_never_narrows_the_lock`.

Notes on the delivered shape, where it goes beyond the bullet:

- **Ambiguity fails towards exclusive.** A job whose pin is not exactly
  one int keeps the old exclusive gate and logs. Over-serialising is
  slow; a lock that doesn't cover the rows we rewrite writes duplicate
  `data_entry_emissions`, and no constraint would catch it.
- **The `emission_recalc` scope is parsed before the lock**, so the lock
  key and the workflow's `carbon_report_module_ids` come from one read —
  they cannot drift apart. Same for the ingest side, where
  `_pinned_module_id` now feeds both the lock and the recalc child's
  config.
- **`module_emission_recalc` stays exclusive**: it rewrites whole
  `(det, year)` slices, so no single module bounds its writes.
- **`MODULE_PER_YEAR` uploads stay exclusive**: they resolve a module per
  unit from the CSV and `_delete_existing_entries_for_module_per_year`
  deletes across all of them
  (`base_csv_provider.py:888-906`), so they have no single pin.
- Safe only while module-scoped recalc children dedup on their own key
  (Phase A's `EMISSION_RECALC_SCOPED_DEDUP`); the pairing is pinned by
  `tests/unit/tasks/test_scoped_dedup_ordering.py`, which still passes.

Conflict matrix, asserted in
`tests/integration/services/data_ingestion/test_factor_lock_scoping_pg.py`
against a real Postgres (modes read out of `pg_locks`; blocking asserted
via `lock_timeout` → 55P03, so a regression fails instead of hanging):

| holder                      | waiter                    | blocks | why                                       |
| --------------------------- | ------------------------- | ------ | ----------------------------------------- |
| `factor_ingest` (exclusive) | scoped recalc             | yes    | the invariant: factor writes vs reads     |
| per-year ingest (exclusive) | scoped ingest             | yes    | its DELETE spans every unit's module      |
| scoped ingest, module 101   | scoped recalc, module 101 | yes    | same rows: DELETE cascade vs rewrite      |
| scoped ingest, module 101   | scoped recalc, module 102 | **no** | disjoint rows — the serialization is gone |

Both directions were mutation-checked: making the module lock shared
fails three of those tests, and ignoring the pin entirely (pre-B1
behaviour) fails the disjoint-modules one.

The `(1238, crm)` lock inherits the gate's existing early release:
`_process_batch` commits `data_session` at `base_csv_provider.py:1548`, so
a file over `INGEST_COPY_BATCH_SIZE` drops both locks mid-parse. Not new —
the single exclusive lock behaved identically, and the
[invariants](#invariants-this-plan-must-not-break) section already
documents the mid-handler commit as inherited.

**Not measured:** the 63 s @5 / 184 s @20 tail itself. Reproducing it
needs the dev DB and the #2295 dataset (Task 0 / the acceptance gate);
what is demonstrated here is that the serialization causing it is gone at
the lock level. The FLOW numbers stay open until the gate run.

### B2. Job hops and where the work runs

One upload is three sequential jobs — `csv_ingest` -> `emission_recalc`
(one per det) -> `aggregation` — each paying a semaphore wait, a claim,
and (with inline dispatch off) up to `POLLER_INTERVAL_SECONDS`. Nothing
here is wrong; it is simply three queue entries per upload on 4 slots per
process (`runner.py:135`, `config.py:488`).

- [x] Size the queue against the budget, not upward by reflex — see
      [Concurrency budget](#concurrency-and-connection-budget). #2529
      measured ingestion **DB-CPU-bound at 3.7 cores for 20 parallel
      uploads**: more concurrent ingest jobs buy nothing and cost
      connections.
- [x] Chunked ingest jobs (#2449's original idea, issue #2527 item 1's
      lever) stay **deferred** until Task 0 shows a single `csv_ingest`
      work time above the bucket on its own. Splitting a job that is
      already fast into chunks that queue behind each other makes the
      tail worse.

**Outcome: no numeric change, deliberately.** `MAX_CONCURRENT_JOBS` stays
4 (`config.py:514`), `POLLER_BATCH_LIMIT` stays 100, and the Helm chart is
untouched. The plan gates a raise on Task 0 showing queue wait dominating
**and** the DB below the 3.7-core ceiling; Task 0 needs the dev DB and the
#2295 dataset and has not been run, and #2529 already says the DB is the
ceiling at 20 parallel uploads. Raising slots there would spend
connections (~2 per job per pod, against a 20-connection hard cap per pod)
to queue more work at a saturated DB.

B1 is the change that actually lifts this path's concurrency: the slots
were never the binding constraint while every upload of a module and year
queued on one exclusive lock. Re-measure with Task 0 after B1 is deployed
before touching any of these numbers.

The worker split (`worker.enabled=true`, `replicaCount: 2`) remains open
question 2 for the maintainer — an ops change, out of scope for this PR.

## Phase C — simulator-plan prefill

One PATCH enqueues **one** job for every year of the range
(`api/v1/simulator_plan.py:49-86`), and the handler walks them
sequentially: per report, empty + copy every reference-scoped module, then
re-price every entry of the report (`simulator_plan_service.py:420-458`).
The docstring recorded 21.9 s on dev for a single year of a ~5k-entry
module. **That figure never measured this job** — see "What 21.9 s
actually was" below. A 5-year PlanUser flow is this handler, five times,
in one job holding one of four slots.

- [x] **C1 — copy without a Python round trip.** _Delivered._
      `prefill_module_from_reference` read every source row into memory,
      rebuilt a dict per row and bulk-inserted it back (`:729-761`). It is
      now one `DataEntryRepository.copy_module_entries` — a single
      `INSERT INTO data_entries (...) SELECT ... FROM data_entries` per
      (module, plan year), with the JSON `data` built server-side. Rows no
      longer cross the wire; the delete-then-insert shape and its
      idempotency are unchanged. See "C1 as delivered" below.
- [x] **C2 — do not re-price what was copied.** _Dropped: the gate fails._
      See "Why C2 was dropped" below.
- [ ] **C3 — one job per report only if C1/C2 miss the gate.** More
      parallel jobs cost connections and DB CPU; splitting is the fallback
      lever, not the first one. Still deferred: C1 landed and C2 is out,
      so the next prefill measurement decides whether this is needed.
- [x] **C4 — emit the 0% rows instead of deriving them.** _Dropped: the
      gate fails._ C2's successor idea, killed by its own pre-committed
      measurement. See "Why the 0%-short-circuit is not worth building".

### C1 as delivered

Two deliberate divergences from the bullet as written:

- The percentage is **0, not 100**. Prefill has always copied at
  `percentage_of_reference_year = 0` (`simulator_plan_service.py:759`) —
  the baseline the user then raises. Writing 100 would have silently
  re-priced every prefilled module of every plan. The plan's `100` was
  illustrative, not a reading of the code.
- One `created_at` / `updated_at` for the whole batch, instead of a
  per-row `datetime.now(UTC)`.

The reference-link JSON expression is dialect-keyed —
`jsonb_build_object` on Postgres, `json_object` inside `json_patch` on the
SQLite unit harness — and raises on any other dialect rather than falling
back to a copy without the link.

### Why C2 was dropped

The premise is right about `kg_co2eq`: at 0% (or any percentage)
`_get_percentage_override_kg` really does just re-read the source's
persisted per-leaf sums, scale them, and carry the source's
`primary_factor_id`. Those columns, plus `scope`, are reproducible from a
join on `source_data_entry_id`.

**`meta` is not.** `prepare_create` writes `factors_used`,
`percentage_of_reference_year`, `reference_year` and then spreads `ctx`,
and `ctx` holds two things that exist nowhere in the copied row:

- `primary_factor_id`, from `FactorResolver.resolve`'s classification
  lookup;
- every key the module handler's `pre_compute` adds. Measured on a
  prefilled buildings row: `meta.room_surface_square_meter = 42.0`, a
  `BuildingRoom` reference lookup — while the plan entry's own `data` holds
  only `building_name`, `room_name`, `room_type`,
  `room_allocation_ratio` and the two reference-link keys.

Reproducing either in SQL means reimplementing the factor resolver and
every handler's `pre_compute` a second time, in a second language.

Reconstructing `meta` from the **source's** persisted `meta` instead was
considered and rejected: it silently diverges when the source has no
emission rows yet, when `_pick_emission_type_id` picks a factor's deeper
type so the join key differs from the plan row's `emission_type.value`,
when several factors produced several source rows for one leaf, and on the
per-factor `quantity` / `quantity_unit` keys that would have to be
stripped by name. Each is an approximation, which this plan's own gate
forbids — so C2 is dropped and C1 ships alone.

### C1 measured, local only

Prefill of one module, `prefill_module_from_reference` alone (not the
recalc that follows it), median of 3 runs:

| Harness                       |    N | Statements before | after | Wall before | after      |
| ----------------------------- | ---: | ----------------: | ----: | ----------: | ---------- |
| Postgres 16 (docker, psycopg) | 2000 |                 7 | **5** |      181 ms | **39 ms**  |
| Postgres 16 (docker, psycopg) | 5000 |                10 | **5** |      404 ms | **110 ms** |
| SQLite in-memory (unit suite) | 2000 |              2005 | **5** |      400 ms | **9 ms**   |

The SELECT that pulled every source row into Python is gone in all three.
SQLite's statement count is a harness artefact — its
`bulk_insert_returning_ids` fallback writes one INSERT per row — so only
the vanished round trip and the shape transfer from that row.

This is one step of one job on a laptop; the prefill job also runs
`_recalculate_report_emissions` over the whole report, which C1 does not
touch. That whole-job profile is the next section. The 42 s FLOW median
and the Phase C acceptance gate still stand unmeasured.

### C0 — the whole job, profiled (2026-09-10)

Run against `origin/dev` (`191065d59`) — i.e. **before** C1 — on local
Docker Postgres: one report, one plan year, one populated module type
(`process_emissions`). Two reps per N, both shown.

|    N |        total |      copy | recompute |  commit | SQL statements |
| ---: | -----------: | --------: | --------: | ------: | -------------: |
|  100 |  99 / 104 ms |   55 / 64 |   39 / 33 |   2 / 1 |             56 |
| 1000 | 237 / 193 ms | 116 / 100 |  116 / 88 |   1 / 1 |             56 |
| 5000 | 822 / 818 ms | 399 / 407 | 415 / 403 | 38 / 38 |             60 |

Plus one `COPY ... FROM STDIN` per report that a `before_cursor_execute`
listener cannot see — `bulk_copy` runs on the raw psycopg cursor.

**Wall time is linear in N (~0.148 ms/entry above a ~60 ms floor);
statement count is flat.** 56 → 60 only because SQLAlchemy's
`insertmanyvalues` pages at 1000 rows, so 5000 rows becomes five INSERTs.
No N+1 remains in this job — the same conclusion #2050 §F0's local rig
reached from the recalc side.

Where the 822 ms goes at N=5000:

|        ms |  share | calls | call                                                |
| --------: | -----: | ----: | --------------------------------------------------- |
| 309 / 351 | 38-41% |     1 | `DataEntryRepository.bulk_insert_returning_ids`     |
| 103 / 108 |    13% |     5 | ↳ `psycopg._queries._query2pg_nocache`              |
| 117 / 117 |    14% |     1 | `DataEntryEmissionService.bulk_replace_for_entries` |
| 108 / 107 |    13% |     1 | ↳ `bulk_copy` (the untraced COPY)                   |
|   87 / 95 |    11% |     1 | `prefetch_percentage_override_cache`                |
|  72 / 102 |  9-12% |  5000 | `prepare_create`                                    |
|   40 / 40 |     5% |  5000 | `DataEntryResponse.model_validate`                  |
|   34 / 35 |     4% |     2 | `recompute_stats_many`                              |
|   33 / 33 |     4% |     1 | `list_by_carbon_report`                             |

The dominant call is the copy's bulk insert — and **13% of the whole job
is psycopg rewriting `%s` → `$n` across five 295 kB SQL strings**. psycopg
deliberately bypasses its statement cache above
`MAX_CACHED_STATEMENT_LENGTH`, naming ORM-generated multi-row
`INSERT ... VALUES` as the reason. Being client CPU, it does not improve
on a faster database. #2050 wrote this INSERT off as "row volume, not
overhead"; a third of it was overhead.

**C1 deletes exactly that.** The four copy-side rows — the bulk insert,
its psycopg rewriting, `model_validate`, `list_by_carbon_report` — are
gone for every module but headcount, which aggregates many member rows
into a handful of grid rows in Python.

Post-C1 this shape is **~557 ms at N=5000 — derived from two
measurements, not measured.** T0's copy phase (399/407 ms) and the "C1
measured" table above (404 ms) are the same step seen from two rigs, and
that table puts it at **110 ms** after C1. So 110 + ~409 (recompute) + 38
(commit). The recompute is then ~73% of the job, and it is what remains.
Converting that from derived to measured means re-running the T0 rig on
this branch; nobody has.

**Not covered by this profile:** no dev DB, no network, no job runner. One
report, one year (a 10-year plan multiplies it; #2050 measured 660
statements for 10 years × 4 modules). One populated module type, though
the rig does walk all ~11. Strategy-A factor lookup only — Strategy B
(headcount, travel, building) issues classification queries keyed by
`factor_query_cache`, i.e. O(distinct classifications), and is the highest
-value remaining lead if a statement-count problem is still suspected. One
`Factor` row and one emission leaf per entry; equipment may be multi-leaf.

### What 21.9 s actually was

`simulator_plan_tasks.py` claimed the job was "measured at 21.9s on dev".
It was not. The number is a single dev APM trace (`954e5976…c3e298`) of
`PATCH /v1/project-plans/{plan_id}/years/{year}`, recorded in
[#2050](2050-backend-compute-performance.md) §F0 — the **synchronous
request**, which §F4 later moved off the request path. §F0's own
decomposition: 21885.3 ms wall, 241 DB spans, 2776.5 ms of traced DB time,
and an 18486 ms contiguous gap with no traced DB activity that §F0
explicitly declines to apportion between Python compute and the untraced
`COPY`. §F6 then wrote "on dev that job is the 21.9 s", and the docstring
hardened that inference into a measurement. Corrected in this PR.

The honest statement: **the prefill job has never been measured on dev** —
only locally, here and in #2050 §F6 (1148 ms for 10 plan years × 4 module
types).

Extrapolating, not measuring: 60 statements + 1 COPY regardless of N means
dev round-trip latency adds a _fixed_ cost, not one that grows with the
module. At this campaign's 14 ms/statement that is ~0.85 s — a figure
drawn from small statements, so it understates five 295 kB INSERTs and a
5000-row COPY, whose cost is bytes and server work, and overstates the ~55
small ones. A ~4× slower dev DB puts a single 5000-entry year at roughly
**1.5-3 s**. A statement-count model structurally cannot reach 21.9 s
here, because the count does not grow with N at all.

### Why the 0%-short-circuit is not worth building

C2's successor: every prefilled row lands at
`percentage_of_reference_year = 0` (`simulator_plan_service.py:759`) and
the derivation ends in `prev_kg * (percentage / 100.0)`, so every freshly
prefilled row is **zero by arithmetic**, whatever its source, factors or
reference year. Emit those rows directly instead of deriving them.

True, and still not worth building. C0 was run as a pre-committed gate —
_if the derivation is not the dominant cost, stop and re-target_ — and the
idea fails on arithmetic, not taste. Post-C1 the job is ~557 ms at N=5000
(derived above) and the recompute is ~73% of it, but the short-circuit
cannot touch most of that:

|     ms | stays, and why                                                                                            |
| -----: | --------------------------------------------------------------------------------------------------------- |
|    108 | `bulk_copy` — the zero rows still get written                                                             |
|  87-95 | `prefetch_percentage_override_cache` — the short-circuit **needs** it, for `primary_factor_id`            |
|     34 | `recompute_stats_many` — runs for every module regardless (#2706)                                         |
| 72-102 | `prepare_create` — the **only** line it cuts, and only the leaf-sum slice; it still builds a row per leaf |

Ceiling: a fraction of ~100 ms on a ~557 ms job — under 18% optimistically
— in exchange for a special case inside the emission derivation. Multi-leaf
modules do not rescue it: leaf count scales the COPY and the row
construction alongside the arithmetic that would be removed, so the ratio
barely moves.

Two findings from the attempt are worth keeping:

- **Emit zeros, never skip rows.** A missing emission row is not a zero
  one. The listing shows `kg_co2eq: null` (LEFT join, no coalesce at
  `:1770`), the kg sort puts NULLs elsewhere (no coalesce at `:1565`),
  `get_stats_pair_many` omits the module entirely, and the row's
  `primary_factor` goes blank (`min(primary_factor_id)` at `:1446`).
- **`primary_factor_id` is not legacy.** 3.46 M of 9.83 M emission rows
  carry it and it drives the factor shown per table row; `data_entries`
  has no factor column at all, so the emission row is its only carrier.

Also settled while measuring: `prefetch_percentage_override_cache` really
does batch — 2 statements, not one per row. An earlier claim of "5,000
source lookups" was wrong.

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
3. ~~C2 (copying emissions for 100% snapshot rows)~~ — **answered by the
   gate, not by a decision.** The rollup row turned out not to be the
   binding risk; `meta` was. It carries the factor resolver's output and
   each handler's `pre_compute` enrichment, neither reachable from a join
   on `source_data_entry_id`. C2 is dropped (see "Why C2 was dropped").
   The open question that replaced it — is the recompute worth attacking
   on its own, or does C3 (one job per report) come first? — is now
   **answered by C0: C3.** The recompute has no N+1 left and no single
   dominant call to remove (C4 was the last candidate and it failed its
   gate). What remains is per-year work that costs what it costs, and a
   range PATCH runs it once per year in one job. If the gate run misses,
   the lever is splitting the years, not shaving the year.
4. C0 is local-only. The gate run on dev is what turns its ~1.5-3 s/year
   extrapolation into a number — and decides whether C3 is needed at all.
