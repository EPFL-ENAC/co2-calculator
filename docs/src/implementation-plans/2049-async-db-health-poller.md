---
status: delivered
issue: 2049
last_updated: 2026-09-24
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
  Since 2026-09-24 `down` fails readiness only before the first
  success; see the section below.
- `/health/deps` (Accred) is untouched — stays a live, on-demand,
  operator-facing check, never gates a probe.
- No helm changes for the settings themselves: `RUN_DB_HEALTH_POLLER`,
  `DB_HEALTH_CHECK_INTERVAL_SECONDS`, `DB_HEALTH_SLOW_THRESHOLD_MS` all
  default correctly in code, same precedent as
  `RUN_POD_HEARTBEAT`/`RUN_PIPELINE_RECONCILER` (neither appears in
  `values.yaml` either).
- One helm change followed from the endpoints working, though: the
  worker deployment (Track B) gained a `readinessProbe` on `/ready`.
  It has no `Service`, so this never gated traffic, but it does gate
  `RollingUpdate` progress — without it, a new worker counted as ready
  the instant its container started, so
  `maxSurge: 1`/`maxUnavailable: 0` would swap in a worker that
  couldn't reach the DB. No `startupProbe` added: the existing
  `wait-for-postgres` init container already blocks the worker's main
  container from starting until Postgres is reachable.

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

## 2026-09-24: readiness fails only on per-pod faults

**Why.** The DB is shared. When it was exhausted or down, every pod failed
`/ready` together and left the Endpoints. The OpenShift router then served
its own HTML 503 for the whole API, and the app never got to answer. The
same argument that already kept `slow` out of readiness applies to `down`.

**Rule.** `/ready` answers `503` only when:

- no check has come back `ok`/`slow` since process start. This is the
  boot gate: a release with broken DB config never takes traffic, and
  the rolling update stalls with the old pods still serving.
  `_db_health._ever_healthy` is set by the poller only, never cleared, and
  read through `db_ever_healthy()`.
- the cached verdict is missing or stale, meaning this pod's poller died.

After the first success, `down` answers `200` with
`{"status": "degraded", "database": "unresponsive"}`. The warning log
and the span attributes stay, so the outage stays loud. `/ready`'s
`database` field now uses `/healthz`'s vocabulary (`sluggish`, not `slow`).

**Stale still means the poller died, not that the DB hung.** A hung probe is
re-awaited, not restarted. Each tick still writes a fresh `down` after the 1 s
wait, at most interval + 1 s apart against a 3× interval stale window.
`test_stuck_probe_teardown_does_not_freeze_the_loop` pins that the
timestamp advances.

**503 JSON for DB outages.** `db_unavailable_handler` (registered for
SQLAlchemy's pool `TimeoutError` and `OperationalError`) maps the
following to `503 {"detail": "Database temporarily unavailable"}`:

- a pool checkout timeout;
- a connection that dropped or was never established
  (`connection_invalidated`);
- a full bouncer or server (`explain_db_wait`: `query_wait_timeout`,
  53300).

For connect failures, `count_connect_failure` marks the raised error
`connection_invalidated`, using the same predicate as the
`db_connect_failures_total` counter. The pool is untouched. Any other error is
re-raised and stays a 500. There is no `Retry-After`, since the frontend's
ky client does not retry 503. Side effect: `emission_recalculation`
already stops its batch on `connection_invalidated`, so a connect failure
there now stops the batch too. Before, it logged one error per remaining
entry.
