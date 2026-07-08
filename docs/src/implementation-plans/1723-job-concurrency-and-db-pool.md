---
status: in-progress
issue: 1723
last_updated: 2026-07-07
title: "Bound background-job concurrency and size the DB pool"
summary: "Cap per-pod running jobs with an asyncio.Semaphore acquired before the DB claim, and give the async engine explicit pool settings, to stop QueuePool exhaustion when a factor CSV upload fans out one emission_recalc child per (module, det)."
---

# Bound background-job concurrency and size the DB pool

## Problem

Uploading a factor CSV produced `QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00`.

Root cause: `backend/app/db.py` creates the async engine with no pool config, so SQLAlchemy defaults to `pool_size=5, max_overflow=10, pool_timeout=30` — the exact numbers in the error. `schedule_job` -> `fire_and_forget(dispatch_job)` (`app/tasks/_poller.py`) has no concurrency bound: the poller sweeps up to `POLLER_BATCH_LIMIT=100` jobs every 2s, and `chain_job`'s deferred-dispatch drain fans out the same way. A factor upload chains one `emission_recalc` child per (module, det); each running job holds 1-2 connections (runner `job_session` + handler `data_session`) for its whole runtime, so the 15-connection default pool exhausts on the first sweep — the HTTP upload request is the collateral timeout victim.

`INGEST_COPY_BATCH_SIZE` is unrelated. Lowering `POLLER_BATCH_LIMIT` would only shrink one of the two stampede paths (poller sweep, chain-job drain), not both.

We run 2-3 replicas in prod: starvation is per-pod, but the fleet also multiplies total Postgres connections — the design accounts for both.

## Design

### 1. Per-pod job concurrency bound (the fix)

New `MAX_CONCURRENT_JOBS` setting (proposed default 4/pod -> 8-12 running jobs fleet-wide at 2-3 replicas). One `asyncio.Semaphore` in the runner, acquired in `run_job` **before** the DB claim.

The ordering is the load-balancing trick: a queued job holds no connection and no claim, so an idle replica's poller can claim it instead of it sitting stuck behind a busy pod's semaphore — saturation on pod A drains via pods B/C.

The heartbeat task is exempt: it must beat while a job runs, and a queued job has no claim to heartbeat yet.

### 2. Explicit pool settings (conscious tuning, same PR)

New settings, wired into `create_async_engine` in `backend/app/db.py` (skipped for sqlite):

- `DB_POOL_SIZE` (default 10)
- `DB_MAX_OVERFLOW` (default 10)
- `DB_POOL_TIMEOUT` (default 30)

Documented in `env.example` next to the poller block.

Fleet math: 3 replicas x 20 max (pool_size + overflow) = 60 connections peak vs Postgres default `max_connections=100`. Per pod: <=4 jobs x 2 conns = 8 reserved for background work, >=12 remain for HTTP.

### 3. Ops note: no PgBouncer (with a revisit trigger)

Direct connections fit comfortably at 2-3 replicas. PgBouncer adds a hop, and its transaction-pooling mode sits badly with long recalc transactions. Revisit when `replicas x (pool_size + overflow)` approaches ~80% of `max_connections` — roughly 4+ replicas at these defaults, or sooner on a managed-PG tier with a small `max_connections`.

## Steps

- [x] Add `MAX_CONCURRENT_JOBS` setting (default 4; kept the plan's default — see "Implementation notes").
- [x] Add one `asyncio.Semaphore(MAX_CONCURRENT_JOBS)` in the runner, acquired in `run_job` before the DB claim; exempt the heartbeat task.
- [x] Add `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` settings (defaults 10/10/30 — kept the plan's default) and pass them to `create_async_engine` in `backend/app/db.py`, skipped for sqlite.
- [x] Document the new pool settings in `backend/.env.example` next to the poller block (repo uses `.env.example`, not `env.example`).
- [x] Add ops note on skipping PgBouncer, with the `replicas x (pool_size + overflow)` ~= 80% of `max_connections` revisit trigger — landed in [ADR-004](../architecture-decision-records/004-database-selection.md), which already documented pooling/PgBouncer.
- [x] Unit tests: N blocking fake jobs -> at most `MAX_CONCURRENT_JOBS` run concurrently; a queued job stays `NOT_STARTED` (claimable by another pod); heartbeats unaffected; settings passthrough into the engine. See `backend/tests/unit/tasks/test_runner_concurrency.py` and `backend/tests/unit/test_db_pool_settings.py`.
- [ ] Real repro: re-run the same factor CSV upload in a live environment — success is no QueuePool timeout and `pg_stat_activity` staying within the per-pod cap during the recalc fan-out. Not run as part of this PR (no live repro environment in this session) — flagged for the owner before merge.

## Implementation notes (as landed)

- **`MAX_CONCURRENT_JOBS=4`, not 8**: kept the plan's conservative default. 8/pod x 2-3 replicas = 16-24 concurrent jobs x ~2 connections each = 32-48 connections just for background work, eating deep into the `DB_POOL_SIZE=10 + DB_MAX_OVERFLOW=10 = 20`/pod budget before HTTP traffic is accounted for. 4/pod keeps the fleet-wide job-connection footprint (8-16 connections) comfortably under headroom; raise later if throughput data justifies it.
- **`DB_POOL_SIZE=10` / `DB_MAX_OVERFLOW=10`, not 5+10**: the *default* 5+10 is exactly what produced the original bug report, so keeping it unchanged would leave the pool the same size while only adding the job-concurrency bound as the fix. Doubling `pool_size` to 10 gives the explicit-settings change real headroom of its own (20/pod vs the previous 15), matching the plan's fleet math (3 x 20 = 60 vs Postgres default `max_connections=100`).
- The semaphore is acquired via `async with _get_job_semaphore()` wrapping everything from `claim_job` through `finish_job` (including the heartbeat-task lifecycle) — released only when `run_job` returns. The heartbeat task itself never acquires the semaphore (it's a separate `asyncio.Task`), satisfying the "heartbeat exempt" requirement without extra bookkeeping.
