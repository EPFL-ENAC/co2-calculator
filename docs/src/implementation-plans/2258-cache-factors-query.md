---
status: delivered
issue: 2258
last_updated: 2026-08-21
title: "Cache the factors query behind taxonomy lookups"
summary: "Process-local TTL cache for ModuleHandlerService.get_taxonomy, keyed on (data_entry_type, year), invalidated on every FactorRepository write and backstopped by a 60s TTL for the cross-process case ingestion runs in a separate worker deployment."
---

# Cache the factors query behind taxonomy lookups

## Problem

`GET /v1/taxonomies/module/{module}/{data_entry}` rebuilds a `TaxonomyNode`
tree from every `factors` row for a `(data_entry_type_id, year)` pair on
every call. For `purchase/other_purchases` (20,915 rows for year=2025) that
is 1338ms of `SELECT` plus 684ms of Python tree-building, versus 70ms/51ms
for `buildings/building` (846 rows) — a genuine large-result-set cost, not
a missing index (`ix_factors_data_entry_type_year` already exists). The page
fires this endpoint ~11× in parallel per report-page load, so the cost is
paid repeatedly per view.

## Why caching, not narrowing

`values`/`classification` are both consumed by
`ModuleHandlerService.get_taxonomy` and returned to the frontend as-is —
narrowing the column list isn't free, the data is actually used. Factors
change only when an ingestion job runs, not per request, so the whole
built tree is a safe cache candidate.

## What was built

- `backend/app/core/factor_taxonomy_cache.py` — a small in-process
  LRU+TTL cache (`_TTLCache`, stdlib `OrderedDict`, no new dependency:
  grepped `redis`/`cachetools` in `backend/pyproject.toml`, neither is a
  project dependency). 60s TTL, capped at 64 entries (bounded key space —
  data_entry_type × year — but years accumulate over uptime as users
  browse history, so it's capped rather than left unbounded; det=66's
  tree is tens of thousands of nodes).
- `ModuleHandlerService.get_taxonomy` checks the cache first, keyed
  `(data_entry_type, year)`, and populates it with the built `TaxonomyNode`
  before returning. This caches the query **and** the 684ms Python
  tree-build, not just the `SELECT`.
- `FactorRepository`'s every write method (`create`, `bulk_create`,
  `upsert_factors`, `update`, `delete`, `bulk_delete`,
  `delete_stale_for_year`) calls `taxonomy_cache.clear()`. This is the
  single choke point every factor writer routes through — CSV ingestion,
  `factor_update_provider`'s recompute pass, seeds, and any future admin
  CRUD — so a full-cache clear (rather than fine-grained per-key removal)
  can't miss a writer that bypasses invalidation. Over-eviction is free;
  a missed eviction is the failure this repo can't afford.
- `Cache-Control: private, max-age=60` on all four `/v1/taxonomies/*`
  routes, mirroring the server TTL, so the browser stops re-issuing the
  ~11 parallel identical calls one page load already fires.

## Invalidation story — read before merging

The write-time `clear()` above is exact and immediate **within one
process**, but it is not sufficient on its own, and this needs a
maintainer's confirmation before merging non-draft:

- Ingestion jobs (CSV factor upload, `factor_update_provider` recompute)
  run via FastAPI `BackgroundTasks` in the dedicated poller-only worker
  deployment (`helm/templates/backend-worker-deployment.yaml`) — a
  separate pod from the API deployment that serves this endpoint.
- The API deployment itself runs multiple uvicorn workers
  (`backend/Dockerfile`'s `--workers $WORKERS`) across multiple pod
  replicas (`backend.replicaCount` in `helm/values.yaml`).
- A `clear()` call only reaches the one process that runs it. The other
  API workers/pods keep serving their own cached tree until it expires.

The 60s server-side TTL is therefore the real cross-process safety net,
not a fallback for a rare miss. It was chosen because factor ingestion is
a deliberate, infrequent admin action (not something staleness-sensitive
on a per-second basis), and 60s is short enough that a stale read after
an upload is a brief, bounded window rather than an indefinite one.
Reaching for a shared cache (Redis) to get exact cross-process
invalidation would be a bigger architectural decision than this issue
should make unilaterally — no cache backend is a project dependency
today, and the issue explicitly asks not to introduce one for this alone.

**The actual worst-case staleness is ~120s, not 60s**: the
`Cache-Control: max-age=60` response header sits on top of the 60s
server TTL, so a browser can serve its own cached response for up to
60s after the server response it cached was itself already up to 60s
stale. That combined ~120s bound is the number a maintainer is actually
signing off on below.

There is also a smaller, same-process gap: `FactorRepository` calls
`taxonomy_cache.clear()` at `session.flush()`/`session.execute()` time,
not at commit — per the guardrails, the commit happens in the route.
A write that later rolls back has over-evicted (free, harmless), but a
read on another connection between this flush and the eventual commit
can repopulate the cache with pre-commit data, which then lives for one
more TTL window. This doesn't change the staleness ceiling above — the
TTL still bounds it — but it does mean the ceiling isn't purely
"time since ingestion finished."

**Open question for a maintainer:** is a ~120s worst-case staleness
window for factor data after an ingestion job completes acceptable, or
does this need a real cross-process invalidation mechanism (pub/sub,
Redis, or a version counter read from the DB) before merging? The PR is
opened as a draft pending this confirmation.

## What wasn't verified

The acceptance bar in the issue is "`SELECT factors` under 100ms for
every `data_entry_type_id`, or served from cache." This PR was not
verified against a running stack with real data (no local Postgres
seeded with the 20,915-row `other_purchases` fixture was stood up) —
reasoning from the code:

- A cache hit skips the query and the tree-build entirely, so it's well
  under any latency bar by construction; this only needs runtime
  confirmation that the cache is actually reached under real traffic,
  not that a hit is fast.
- **A cold key still pays the full ~2s** (1338ms query + 684ms
  tree-build) — this PR does not make the first request for a given
  `(data_entry_type, year)` faster. It bounds how often that cost is
  paid (once per 60s per worker process, not once per page load), it
  doesn't remove it. The first visitor after a deploy, after a TTL
  expiry, or on a new worker process still pays it. That's the case for
  the frontend 11-call batching mentioned as out of scope in the
  issue — this PR doesn't reduce how much work one page load asks for,
  only how often that work repeats.

## Tests

- `backend/tests/unit/core/test_factor_taxonomy_cache.py` — the cache
  primitive itself: get/set, TTL expiry (mocked clock), `clear()`, LRU
  eviction at capacity.
- `backend/tests/unit/services/test_module_handler_service.py` — a
  second `get_taxonomy` call for the same key does not re-query factors;
  a different year does; clearing the cache (as a write would) forces a
  re-query.
- `backend/tests/unit/repositories/test_factor_repo.py` — `create`,
  `update`, `delete`, `bulk_delete`, and `delete_stale_for_year` each
  invalidate a pre-populated cache entry; a no-op `update` (factor not
  found) leaves the cache untouched.

## Not in scope

- The 11-call-per-load frontend fan-out (batching into one call) — a
  separate, smaller win noted in the issue.
- `EXPLAIN (ANALYZE, BUFFERS)` confirmation of scan type — not needed to
  decide the fix per the issue's own investigation.
