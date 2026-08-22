---
status: proposed
issue: 2278
last_updated: 2026-08-22
title: "Cache the per-request user lookup"
summary: "Investigation of #2049 item C1. Every authenticated request pays an uncached SELECT users (15.2 ms idle, 71.7 ms burst) whose result carries the roles that permissions are calculated from, so caching it is a permission-scoping change and gated on maintainer review. Recommendation is DEFER: n=2 measurement, #2049 A1 unanswered, and the burst that produces the 71.7 ms figure is already being dismantled by #2275 and B2. If approved anyway, the design is a 30 s process-local TTL on an immutable snapshot, TTL-only with no eviction hooks and no cross-pod broadcast, failing closed on miss."
---

# 2278 — Cache the per-request user lookup

**Awaiting maintainer review.** No application code has been changed and
none should be until this plan is signed off by both maintainers: the
object being cached carries the user's roles, which is squarely the
guardrails' "permission scoping" category.

Parked from
[#2049](https://github.com/EPFL-ENAC/co2-calculator/issues/2049) item **C1**.
The full finding, measurements and asks are in
[issue #2278](https://github.com/EPFL-ENAC/co2-calculator/issues/2278).

## Problem

`backend/app/core/security.py:165` runs, on every authenticated request:

```
SELECT ... FROM users WHERE institutional_id = ? AND provider = ?
```

via `UserService.get_by_institutional_id_and_provider` →
`backend/app/repositories/user_repo.py:54`. It sits under
`get_current_user` → `get_current_active_user` → `require_permission`,
~131 dependency sites across 24 routers. It is the most-executed query in
the application and a shared latency floor under every other slow-route
finding in #2049.

Measured (#2049 Appendix A, two `GET /v1/taxonomies/module/{m}/{de}`
traces): **15.2 ms idle, 71.7 ms under burst** — 11% of the 134.5 ms trace,
3.5% of the 2064 ms one.

An index fix is ruled out: `backend/app/models/user.py:343` already has
`unique=True, index=True` on `institutional_id`, and uniqueness on the
leading column already reduces the scan to one row. The cost is network RTT
plus DB load. The only way to remove it is to not make the round trip.

## Recommendation: defer

Four reasons, in order of weight:

1. **n = 2.** Both figures come from two traces in one 200-row, 39.5-minute
   stage export averaging 0.5 concurrent streams. #2049 Appendix B records
   four consecutive confident conclusions in this investigation that the
   next round of measurement overturned. A 4.7× burst factor from a sample
   of two is a hypothesis.
2. **#2049 A1 gates this item** ("A1 … gates B1, C1, C2") and is
   unanswered. One Grafana screenshot of the DB Pool Usage panel.
3. **The 71.7 ms figure is being dismantled elsewhere.** Burst
   amplification tracks concurrent DB load, and the burst is shrinking:
   #2275 (shipped) cut taxonomies 16 → 5, #2049 B2 batches the remaining
   ~18 `modules/{m}/{sub}` calls. 31 requests becomes ~7, so per-request
   cost reverts toward the 15.2 ms idle figure — this item's win shrinks
   by roughly the factor it is currently measured at.
4. **It removes only half the floor.** #2049 A2 recommends keeping
   `pool_pre_ping` (4.6 ms idle → 28.7 ms burst), so every request still
   pays a checkout plus a pre-ping RTT afterwards.

**Unblock conditions — both, not either:** A1 answered with a number, and a
post-B2 re-export in which the auth `SELECT users` is still a material
share of the remaining floor, with n ≫ 2 and ideally one prod sample. That
is #2049 D1's sequence anyway: fix the floor, re-measure, then triage.

## Invalidation surface

Two narrowings shrink it; one fact enlarges it.

**Only `roles_raw` matters.** `User.calculate_permissions()`
(`models/user.py:333`, `:382`) calls `calculate_user_permissions(self.roles)`,
and the `roles` property (`:315`) reads *only* `roles_raw` — no other
column, no other table, no relationship. So `last_login` and
`last_roles_sync_at` bumps are not invalidation events, and `unit_users`
writes matter only insofar as they feed a later role sync that rewrites
`roles_raw`.

**There is no user-management API and no deactivation.**
`backend/app/api/v1/users.py` mounts one read-only route. `create_user`
(`user_service.py:442`), `update_user` (`:474`), `delete_user` (`:506`) and
`UserRepository.delete` (`user_repo.py:190`) have no callers. There is no
`is_active` / `deleted_at` column; `get_current_active_user`
(`security.py:191`) is a documented no-op. **No "admin revokes a role and
expects it now" path exists today.** If one is added, this plan is void.

**Multi-pod.** `helm/values.yaml:13` sets `backend.replicaCount: 2` (dev
runs 3). A process-local cache has N independent copies; a write on pod A
is invisible to pods B and C. This decides the design below.

Everything that writes `users.roles_raw`:

| # | Site | Trigger | Process |
| --- | --- | --- | --- |
| 1 | `api/v1/auth.py:430` → `upsert_user(roles=…)` | `GET /v1/auth/callback` — every OAuth login | API pod, user's own request |
| 2 | `services/role_sync_service.py:149` — `user.roles = new_roles` | `POST /v1/session` (`auth.py:612`) → `background_tasks.add_task(trigger_role_sync_for_user)` (`auth.py:659`), 15-min per-user TTL (`role_sync_service.py:43`) | in-process `BackgroundTasks`, own session, same API pod |
| 3 | `api/v1/auth.py:296` → `upsert_user(roles=…)` | `GET /v1/auth/login-test` — DEBUG builds only (`auth.py:547`) | API pod, user's own request |
| 4 | `tasks/unit_sync_tasks.py:196` → `bulk_upsert(principal_users)` | `unit_sync` ACCRED job (~2231 units) | worker pod if `worker.enabled`, else an API pod — `helm/values.yaml:231` defaults it `false` |
| 5 | `seed/seed_units_from_accred.py:54` | `make seed-units` | separate CLI |
| 6 | `seed/seed_fake_user_unit.py:25` | seed CLI | separate CLI |
| 7 | `seed/random_generator/populate_units_and_users.py:234` | perf-seed CLI — raw asyncpg `INSERT … roles_raw` | separate CLI |
| 8 | `scripts/migrate_test_users.py:72` | one-shot CLI — raw `UPDATE users SET institutional_id`, mutates the cache key itself | separate CLI |

Dispatchers of #4: `POST /v1/data-sync/units` (`data_sync.py:2028`),
`create_year_configuration` auto-enqueue (`year_configuration.py:715`), the
safety poller (`tasks/_poller.py:82`), the orphan sweep
(`tasks/_pipeline_reconciler.py:45`), `seed/bootstrap_years.py:136`.

## Freshness reality check

The fact that makes a short TTL defensible. Today's freshness against
ACCRED — the actual authority on roles — is already ~8 hours:

- `ACCESS_TOKEN_EXPIRE_MINUTES = 480` (`core/config.py:353`).
- Role sync fires from one place only: the `POST /v1/session` background
  task (`auth.py:659`).
- The frontend calls it **only reactively on a 401** —
  `frontend/src/api/http.ts:42-48` `beforeRetry`, `API_REFRESH_URL =
  'session'` (`http.ts:20`). No proactive timer.
- `RoleSyncService` gates on `sync_ttl_minutes: int = 15`
  (`role_sync_service.py:35`) even when called.

So a role revoked in ACCRED reaches the `users` table on the order of the
next token expiry, not instantly. The row this query reads is already a
stale copy by design; a 30 s cache in front of it is a rounding error
against an 8-hour authority window.

## Design, if approved

**1. TTL 30 s, process-local, keyed on `(institutional_id, provider)`.**
Sized to span a page-load burst (31 requests in 1.5 s) and nothing longer.
Key on the pair — never `institutional_id` alone; cross-provider collision
is what the current lookup exists to prevent.

**2. TTL only — no eviction hooks, no cross-pod broadcast.** With
`replicaCount` 2–3, evicting at write sites 1–3 clears one pod's entry
while the others keep theirs until expiry anyway. Hooks would buy a 1-in-N
improvement inside a window that is already only 30 s. Note also where the
win actually comes from: the 31-request burst round-robins across the
pods, so a TTL alone already collapses it to one lookup per pod — 2–3
queries instead of 31. Hooks are unnecessary, not merely marginal. The TTL
does essentially all the work; let it, and don't write them. Sites 4–8 are
bulk or operator commands measured in minutes.

**3. Cache an immutable snapshot, not the ORM row.** `User` is
`table=True` (`models/user.py:337`) and `get_db` closes its session per
request (`db.py:135`), so a cached instance would be handed detached into
the next request's session; `expire_on_commit=False` (`db.py:110`) covers
loaded columns but not re-attachment. Cache `id`, `institutional_id`,
`provider`, `email`, `display_name`, `function`, `roles_raw` and
reconstruct a transient, non-session-bound `User` per request — preserving
the `User` return type across all ~131 dependency sites rather than
changing a signature with that blast radius.

**4. Fail closed.** Two prohibitions, both load-bearing:

- **No stale-on-error.** Serving an expired entry when the DB is down is
  exactly the silent fallback the guardrails forbid. On a miss the query
  runs; if it raises, the exception propagates. A DB outage produces
  errors, never a cached authorization decision outliving the outage.
- **No negative caching.** Never cache `user is None` — it would 401 a
  freshly-provisioned user for the whole TTL.

The cache must also be resettable per test; a process-global TTL cache
leaks across tests in a shared-process suite.

## Why not reuse #2273's cross-pod broadcast

[#2258](https://github.com/EPFL-ENAC/co2-calculator/issues/2258) / #2273
built a `pods` heartbeat-table
registry extended with `pod_ip` from the Downward API, a bare-mounted
`POST /internal/cache/taxonomy/clear` gated on the caller's TCP source IP
matching a live `pods` row, and a best-effort `asyncio.gather` + `httpx`
fan-out (200 ms timeout, failures logged and swallowed). Good machinery,
and the right pattern for factors.

Declining it here is deliberate and does not violate "mirror, don't
invent" — this is not building a second pattern, it is not building the
pattern at all:

- **It buys ≤ 30 s**, on writes that are either the user's own request or a
  multi-minute bulk job.
- **The shapes differ.** Factors change rarely, globally, from the worker,
  so one global `clear()` is correct and cheap. User rows change often and
  individually, mostly from the user's own request — reusing a global-clear
  broadcast would flush every pod's entire user cache on every login.
- **Cost.** That broadcast runs a `SELECT pods` plus up to 200 ms inside
  the write's own session, per write call — a new per-login cost to save a
  per-request one.
- **Its auth is one config change from spoofable.** The IP gate holds only
  because no `ProxyHeadersMiddleware` is registered and uvicorn runs
  without `--proxy-headers`. Enabling either would let anyone reach
  `POST /api/internal/...` — the OpenShift `Route` `path: '/api'` is a
  prefix match (`helm/templates/routes.yaml:24`) — with a spoofed
  `X-Forwarded-For`. For an idempotent factors clear the blast radius is a
  cold cache; for anything touching authorization state it wants a real
  shared secret first.

**Build it if, and only if,** a TTL beyond ~60 s is wanted, or a
user-management write endpoint is added. Then add a second path to
`backend/app/api/internal.py` reusing `_caller_is_live_pod` and
parameterise `_clear_remote`'s hardcoded path. Do not build a second
registry.

## Tests it would ship with

Hit / miss / expiry against a mocked clock; a DB-failure-during-miss test
asserting the exception propagates and nothing stale is served; a
`user is None` test asserting no negative caching; a cross-provider test
asserting two users sharing an `institutional_id` across providers never
collide; and a snapshot-reconstruction test asserting the returned `User`
touches no session.

## Side-findings — not part of this change

Both concern `UserRepository.bulk_upsert` (`user_repo.py:140`), which
`unit_sync` runs over every principal user. Recorded here rather than
silently dropped; neither should be fixed under this issue.

**A. `bulk_upsert` is provider-blind.** `user_repo.py:143-144` builds its
existing-row map from `institutional_id` alone, then merges. Every other
lookup in the codebase — including `security.py:165` — keys on
`(institutional_id, provider)`. A `unit_sync` principal user whose
`institutional_id` collides with a `TEST` or `DEFAULT` row would merge onto
that row and flip its `provider`.

**B. ⚠️ UNVERIFIED — `bulk_upsert` may null `roles_raw` on existing rows.**
`roles` is a plain `@property` on `UserBase` (`models/user.py:315`), not a
SQLModel `Field`, so `User(..., roles=[...])` would not fire the setter and
`roles_raw` would stay at its `None` default. Corroborating:
`user_repo.create:98-99` constructs `User(... roles=roles ...)` and then
re-assigns `entity.roles = roles or []` under the comment
`# ensure setter is called`, whereas `AccredRoleProvider.map_api_user`
(`role_provider.py:483`) does not. If it holds, each `unit_sync` wipes
`roles_raw` for every principal user until their next login re-populates
it.

**Inferred from source, not executed.** It needs a one-line runtime check
before anyone acts on it. If confirmed it is a live authorization bug
independent of this plan and deserves its own issue.

## Not in scope

Putting roles in the JWT (an 8-hour unrevocable authorization claim — worse
than the problem), a Redis or other shared cache (no such dependency in
`backend/pyproject.toml`, and #2258 already established process-local as
this codebase's shape), caching anything else on the request path, and the
`pool_pre_ping` half of the floor (#2049 A2 keeps it).
