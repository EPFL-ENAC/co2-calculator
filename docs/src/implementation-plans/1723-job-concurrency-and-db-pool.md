---
status: proposed
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

- [ ] Add `MAX_CONCURRENT_JOBS` setting (default 4); confirm 4 vs 8 at implementation.
- [ ] Add one `asyncio.Semaphore(MAX_CONCURRENT_JOBS)` in the runner, acquired in `run_job` before the DB claim; exempt the heartbeat task.
- [ ] Add `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` settings (defaults 10/10/30; confirm 10+10 vs 5+10) and pass them to `create_async_engine` in `backend/app/db.py`, skipped for sqlite.
- [ ] Document the new pool settings in `env.example` next to the poller block.
- [ ] Add ops note (README/docs) on skipping PgBouncer, with the `replicas x (pool_size + overflow)` ~= 80% of `max_connections` revisit trigger.
- [ ] Unit tests: N blocking fake jobs -> at most `MAX_CONCURRENT_JOBS` run concurrently; a queued job stays `NOT_STARTED` (claimable by another pod); heartbeats unaffected; settings passthrough into the engine.
- [ ] Real repro: re-run the same factor CSV upload — success is no QueuePool timeout and `pg_stat_activity` staying within the per-pod cap during the recalc fan-out.
