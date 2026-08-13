---
status: delivered
issue: 2049
last_updated: 2026-08-13
title: "Background DB health poller — zero I/O on /healthz and /ready"
summary: "Continuation of 2050's Track A1: a 1s background loop caches a SELECT 1 verdict in a per-pod global; /healthz and /ready read it instead of doing their own DB round trip, so a saturated pool can no longer make either endpoint itself hang."
---

# Background DB health poller (#2049)

## Context

See [2050 — backend compute performance](2050-backend-compute-performance.md)
for the full 504 investigation. Track A1 there bounded `/ready`'s DB check
to 2s (`asyncio.timeout`) so it could never outlive its own k8s probe
deadline — that shipped and is live. It still did a real DB round trip on
every probe, though, and external probing was measured at ~24× the
configured rate. This plan removes that last per-request I/O: `/ready` and
`/healthz` now read a cached verdict instead of touching the DB at all.

## Design

- `app/tasks/_db_health.py` (new) — mirrors `_pod_heartbeat.py`'s loop
  shape. `db_health_check_loop()` runs `SELECT 1` every
  `DB_HEALTH_CHECK_INTERVAL_SECONDS` (default 1s), bounded by a 1s
  timeout, and caches the verdict (`ok` / `slow` / `down` +
  latency + error) in a module-global — safe without a lock, single
  process per pod (Track A's rejected-gunicorn-worker finding).
- `/healthz` — always `200` (liveness ≠ dependency health); body's
  `database` field changes with cached state (`ok` / `sluggish` /
  `unresponsive` / `unknown`), plus `database_latency_ms` when known.
  Zero I/O either way.
- `/ready` — `503` when DB state is `down`, stale (poller stopped
  ticking — `time.monotonic()`-based, 3× the interval), or never
  checked; `200` otherwise. **`slow` does not fail readiness**: DB
  latency is shared state, so gating on it would take every pod unready
  simultaneously — turning "slow" into the exact kind of outage this
  endpoint exists to prevent. `DB_HEALTH_SLOW_THRESHOLD_MS` (default
  100ms) only ever surfaces in `/healthz`'s body / monitoring.
- `/health/deps` (Accred) is untouched — stays a live, on-demand,
  operator-facing check, never gates a probe.
- No helm changes: `RUN_DB_HEALTH_POLLER`, `DB_HEALTH_CHECK_INTERVAL_
SECONDS`, `DB_HEALTH_SLOW_THRESHOLD_MS` all default correctly in code,
  same precedent as `RUN_POD_HEARTBEAT`/`RUN_PIPELINE_RECONCILER`
  (neither appears in `values.yaml` either).

## Footgun, documented not coded around

`RUN_DB_HEALTH_POLLER=False` on a pod that serves `/ready` leaves the
cache forever empty → `/ready` permanently `503`. This is correct
fail-closed behaviour (loud, immediate, same shape as Track B's
poller-off/no-dispatcher guard) — not a case for a fallback DB check
inline in `/ready` (that would be the dual-path the guardrails ban). The
flag exists mainly as a test/diagnostic kill-switch; its `Field`
description states the risk directly.

## Decisions

- **503, not literal 500** — kubelet only distinguishes 2xx/non-2xx; 503
  (Service Unavailable) is already shipped and semantically correct.
- **`slow` gates `/healthz`'s content, never `/ready`'s status code** —
  see Design above.
- **Accred stays out of the background poller** — `/health/deps` already
  covers it and isn't on a 1s cadence; folding it in here would be scope
  creep beyond the DB-specific ask.

## Status

Delivered: `app/tasks/_db_health.py`, `app/core/config.py` (3 new
`Settings` fields), `app/main.py` (lifespan wiring + `/healthz`/`/ready`
rewrite), tests in `tests/unit/tasks/test_db_health.py` and
`tests/integration/test_main.py`.
