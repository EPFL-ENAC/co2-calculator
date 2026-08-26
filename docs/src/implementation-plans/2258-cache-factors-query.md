---
status: delivered
issue: 2258
last_updated: 2026-08-26
title: "Cache the factors query behind taxonomy lookups"
summary: "Process-local TTL cache for ModuleHandlerService.get_taxonomy, keyed on (data_entry_type, year), invalidated on every FactorRepository write and backstopped by a 60s TTL for the cross-process case ingestion runs in a separate worker deployment. Follow-up: active cross-pod invalidation broadcast on top of the TTL, dropping worst-case staleness from ~120s to the time one broadcast round-trip takes."
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
  choke point production factor writers route through — CSV ingestion
  (`base_factor_csv_provider.py`, via `_upsert_batch`/`_delete_stale_factors`)
  and `factor_update_provider`'s recompute pass both call the repo, so
  both get exact same-process invalidation. A full-cache clear (rather
  than fine-grained per-key removal) can't miss a writer that goes
  through the repo at all. Over-eviction is free; a missed eviction on
  a covered path is the failure this repo can't afford.
  **Known bypass:** the dev/local seed scripts
  (`app/seed/random_generator/seed_factors.py`,
  `seed_emission_factors.py`) construct `Factor` rows and call
  `session.add_all(...)` directly, skipping `FactorRepository` entirely
  — grepped, confirmed. These don't get explicit invalidation and rely
  solely on the TTL, same as the cross-process case below. This is
  acceptable in practice: seeding runs as a one-off CLI/`make
seed-*` invocation against a dev/local database, not as a live
  ingestion path against a warm production cache.
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

**Resolved:** `FactorRepository` used to call `taxonomy_cache.clear()` at
`session.flush()`/`session.execute()` time, not at commit — per the
guardrails, the commit happens in the route. A read on another
connection between that flush and the eventual commit would repopulate
the cache with pre-commit data, for a fresh TTL window — invalidating
_before_ the write was durable made staleness worse than not
invalidating at all, on top of the ~120s bound above.

Fixed: `FactorRepository._invalidate_taxonomy_cache` now calls
`app.core.taxonomy_cache_broadcast.schedule_taxonomy_cache_invalidation`,
which registers a one-shot `after_commit` hook on the session (plain
`sqlalchemy.event.listen`, no new dependency) instead of clearing
inline. The local `clear()` and the cross-pod broadcast both fire only
once the write is durable; a rollback never fires `after_commit` at
all, so it correctly triggers no invalidation. Multiple writes on one
session/transaction (e.g. a factor-recompute job's per-row loop)
collapse into a single post-commit clear + broadcast via a pending flag
on `session.info`, instead of one redundant broadcast per row.

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
  defer invalidating a pre-populated cache entry until commit (not at
  flush); a no-op `update` (factor not found) leaves the cache
  untouched; a rollback never invalidates; several writes on the same
  transaction broadcast exactly once.

## Not in scope

- The 11-call-per-load frontend fan-out (batching into one call) — a
  separate, smaller win noted in the issue.
- `EXPLAIN (ANALYZE, BUFFERS)` confirmation of scan type — not needed to
  decide the fix per the issue's own investigation.

## Follow-up: active cross-pod invalidation

Branch `perf/2258-cross-pod-cache-invalidation`, stacked on top of the
PR above. Answers the "open question" above by closing most of the
~120s worst case actively, keeping the TTL as the fallback for whatever
the broadcast doesn't reach — belt-and-suspenders, not a replacement.

**Pod discovery.** The `pods` heartbeat table (`app/models/pod.py`,
`app/tasks/_pod_heartbeat.py`) already tracks every live pod by `POD_ID`
but not its routable IP. Added:

- `POD_IP` (Kubernetes Downward API `status.podIP`) to the Helm chart's
  shared `co2-calculator.backendSecretEnv` block, alongside the existing
  `POD_NAME`/`POD_NAMESPACE` — given to both the API and worker
  Deployments.
- `pods.pod_ip` column (migration `a62060da49c0`), refreshed on every
  heartbeat tick (unlike `started_at`) since a Deployment pod's IP
  changes across restarts even when `POD_ID` happens to repeat.

**Broadcast.** `app/core/taxonomy_cache_broadcast.py` — after a
`FactorRepository` write clears its own process' cache
(`_invalidate_taxonomy_cache`), it queries the `pods` table for every
OTHER pod heartbeating within the live window `GET /v1/sync/workers`
already uses, and POSTs to each one's internal cache-clear endpoint
concurrently (`asyncio.gather(..., return_exceptions=True)`, 200ms
per-call timeout). Best-effort throughout: any pod failure is logged
and swallowed, never raised, and never fails the write.

**Internal endpoint.** `app/api/internal.py`, mounted directly on
`app` (not under `settings.API_VERSION`, never referenced by
`helm/templates/routes.yaml`) — the same root-level trust boundary
`/healthz`/`/ready` already rely on. That boundary alone isn't airtight
for a state-mutating endpoint: an OpenShift `Route` `path` match is a
_prefix_ match, so `/api/internal/...` would still reach it. The
endpoint therefore additionally gates on the caller's source IP being a
currently-live pod from the `pods` table — no new auth machinery, just
the registry this feature already needs.

**New staleness bound:** however long a broadcast takes to reach every
live pod — typically low hundreds of ms, bounded by the 200ms per-call
timeout — with the 60s TTL (+ `Cache-Control`) as the fallback for
whatever a broadcast misses (a pod mid-restart, a network blip). Down
from the ~120s worst case above.

**Tests:** `test_taxonomy_cache_broadcast.py` (fans out to every other
live pod, skips self/stale/no-IP pods, one pod's failure doesn't stop
the others or raise), `test_internal_cache_endpoint.py` (clears the
local cache for a live-pod caller, 403s otherwise), `test_factor_repo.py`
(defer-to-commit, rollback never invalidates, N writes in one
transaction broadcast once, a no-op delete/sweep invalidates nothing),
`test_taxonomies_batch_endpoint.py` (a per-entry runtime failure is
isolated and rolls back the session instead of poisoning the rest of
the batch), and `taxonomy-batch.spec.ts` (a missing entry surfaces
through `state.error` instead of failing silently).

## Follow-ups parked from code review

A review of this branch (`code-review`, medium effort) surfaced a few
more findings alongside the flush-vs-commit one above. Fixed in this PR:

- The batch endpoint (`GET /module/{module}/data-entries`) had no
  per-entry error isolation: one bad entry failed the whole batch, and
  the frontend then blanked every already-resolved submodule in it, not
  just the failing one. Fixed: an `HTTPException` (bad entry name,
  entry not in this module) is a request-shape bug and still fails the
  whole batch loudly; any other exception is a per-entry runtime
  failure, now logged loud and left out of the response instead of
  nulling the rest.
- The pod-liveness cutoff (`now - 2×POD_HEARTBEAT_INTERVAL_SECONDS`)
  was hand-duplicated in three places (`taxonomy_cache_broadcast.py`,
  `internal.py`, `data_sync.py`'s `list_workers`). Deduplicated into
  `app.models.pod.live_cutoff()` / `is_live()`.

Parked, not fixed here — each needs more than this PR's scope:

- **Internal cache-clear endpoint auth is IP-based**
  (`app/api/internal.py:_caller_is_live_pod`), which is spoofable via
  pod-IP reuse in Kubernetes within the liveness window. Fixing this
  properly means a real internal-auth primitive (shared token, mTLS)
  — an architecture change that needs a maintainer's sign-off, not an
  improvised fix while they're away.
- **Cached `TaxonomyNode` is a shared, mutable object.**
  `model_config = ConfigDict(frozen=True)` only blocks attribute
  _reassignment_ (`node.label = "x"`), not mutation of the contained
  `children` list/`classification` dict (`node.children.append(...)`)
  — verified empirically, not assumed. Real immutability needs
  `children: tuple[TaxonomyNode, ...]` plus frozen mappings, which
  cascades into `ModuleHandlerService.get_taxonomy`'s construction (it
  currently mutates nodes in place while building the tree) and every
  consumer. Bigger than a one-file fix; not attempted here.
- **`_TTLCache.clear()` evicts the whole cache on any write**, not just
  the affected `(data_entry_type, year)` keys. Threading exact keys
  through would only fix the _local_ half — ingestion runs on a
  separate worker deployment from the API pods serving reads (see
  "Problem" above), so the pod doing the write is the one with nothing
  cached to spare; the API pods that actually hold hot trees still get
  a full `clear()` via the broadcast either way, since its wire
  protocol (`POST /internal/cache/taxonomy/clear`, no body) carries no
  key information. Doing this right means extending that protocol too.
  The per-row-recompute case this would have mattered most for is
  already fixed above (N writes on one transaction now broadcast once
  instead of N times).
- **The batch endpoint resolves entries sequentially, not
  concurrently.** `asyncio.gather` over the per-entry resolution would
  run every entry's `factor_service.list_by_data_entry_type` on the
  _same_ `AsyncSession` from `Depends(get_db)` concurrently — SQLAlchemy
  `AsyncSession` isn't safe for concurrent use from two coroutines at
  once. Fixing it means giving each entry its own session, which the
  route doesn't have a way to do today. The warm-cache path (the common
  case) does no DB work either way, so the risk only shows up on a cold
  batch — low enough traffic to defer.

### Round 2: findings on the round-1 fixes

A second review, scoped to the fixes above, found that the batch
endpoint's per-entry isolation had a gap of its own, plus a few smaller
issues. Fixed:

- **The per-entry `except Exception` didn't roll back a poisoned
  session.** A real DB error leaves the shared `AsyncSession`'s
  transaction aborted; every entry ordered after the failing one would
  raise too, undermining the isolation the round-1 fix was for. Fixed
  by rolling back before logging (`app/api/v1/taxonomies.py`) —
  regression test drives this via a mocked session and asserts
  `rollback` was awaited.
- **A failed entry silently missing from the response** is itself a
  "no silent fallbacks" violation once you count the frontend: the
  backend logs loud, but nothing distinguishes "no taxonomy exists"
  from "this entry errored" in the API response the UI renders. Fixed
  on the frontend instead of widening the response contract: a missing
  key now sets `state.error` in `getSubmoduleTaxonomiesBatch`
  (`frontend/src/stores/modules.ts`), which the UI already renders —
  no new response field, no OpenAPI regen.
- **`bulk_delete` / `delete_stale_for_year` invalidated the cache even
  on a no-op** (nothing actually deleted) — a real path via
  `FactorService.bulk_delete_by_data_entry_type_and_year` on an empty
  `(det, year)`. Both now skip invalidation when nothing changed,
  mirroring `update`'s existing not-found guard.
- **`broadcast_taxonomy_cache_clear`'s docstring claimed it was the
  production call site**; it isn't since round 1 —
  `schedule_taxonomy_cache_invalidation` inlines the same
  lookup-then-POST sequence itself (needs to snapshot live pods before
  commit but fire after). Docstring corrected to say so explicitly;
  function kept as the tested unit for that behavior in isolation.
- **`fire_and_forget` inside the `after_commit` listener has no comment
  explaining why it doesn't reuse `app/tasks/_chain.py`'s
  drain-after-commit queue.** That pattern exists to stop a child task
  starting before its parent's transaction is visible — already
  guaranteed here by firing from `after_commit` itself. Comment added
  in place; no rewrite.

Parked, with a code comment at the point of the gap rather than a plan
bullet:

- **`_PENDING_INFO_KEY` / the `live_others` snapshot survive a rollback
  untouched** (verified empirically), and the `once=True` listener
  stays registered rather than firing. A session that rolled back a
  write here and later committed an unrelated write on the same
  session would broadcast to the first write's stale pod list. No
  current caller does this (factor CSV ingestion rolls back and
  re-raises, ending that session's writes). Closing it needs
  `after_rollback` vs. `after_soft_rollback` — picking the wrong one
  risks a double broadcast, worse than the staleness being fixed — so
  it's documented at `taxonomy_cache_broadcast.py`'s
  `schedule_taxonomy_cache_invalidation` rather than attempted blind.

Reported but not touched — pre-existing, not introduced by either
round:

- `factor_taxonomy_cache.py`'s `_MAX_ENTRIES = 64` comment undersells
  how fast the cache fills (a single print/export page load already
  spans most `DataEntryTypeEnum` members for one year); the eviction
  mechanism itself is safe regardless. A tuning call for whoever owns
  the cache-size budget, not a bug.
- `Cache-Control` header-setting is duplicated by hand across the three
  taxonomy routes instead of a router-level dependency — predates both
  review rounds, orthogonal to the caching work itself.
