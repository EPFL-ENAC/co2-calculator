---
status: in-progress
issue: 2943
last_updated: 2026-09-24
summary: "Replace the access + refresh cookie pair and the client-driven POST /session refresh with one sliding httponly session cookie renewed inside the auth dependency; GET /session answers 200 with user null when anonymous."
---

# Single sliding session cookie

Split out of [#2934](https://github.com/EPFL-ENAC/co2-calculator/issues/2934),
where the prod log audit and the scored options live. Decision record:
[ADR-020](../architecture-decision-records/020-single-sliding-session-cookie.md),
which amends ADR-012's "optional refresh tokens" mitigation.

**Auth change: this plan is reviewed by both maintainers before the
implementation PR opens.**

## Why

Every anonymous page load is `GET /v1/session` 401 then `POST /v1/session`
401: the SPA cannot see the httponly cookies, so it asks, gets a 401, and
the ky retry hook tries a refresh that also 401s. Every returning user after
8 h idle pays the same two round trips before the app renders.

Both cookies are stateless JWTs signed with the same key and there is no
revocation table (ADR-012 lists a JTI denylist as "future | optional"). A
refresh token normally buys revocation; ours buys only the client-side
dance. The 24 h bound on a session comes from the refresh cookie's
lifetime, and that bound is the one thing worth keeping.

## Design

### Backend

One httponly cookie, `auth_token` (name unchanged, every test and the
logout path already know it). Claims: the existing `sub`, `email`,
`institutional_id`, `provider`, plus:

- `exp` = now + `SESSION_IDLE_MINUTES` (default 480, today's
  `ACCESS_TOKEN_EXPIRE_MINUTES`)
- `auth_time` (OIDC standard claim) = the login instant, set once at
  `/auth/callback` and `/auth/login-test`, carried unchanged through every
  renewal

Renewal lives in `get_current_user`, which gains `response: Response` and
`background_tasks: BackgroundTasks` parameters (FastAPI merges a
dependency's `Set-Cookie` into the route response):

```
if exp - now < SESSION_IDLE / 2:
    new_exp = min(now + SESSION_IDLE, auth_time + SESSION_MAX_HOURS)
    if new_exp <= now: raise 401          # hard cap reached
    set_cookie(auth_token, ..., max_age=new_exp - now)
    background_tasks.add_task(trigger_role_sync_for_user, user_id, force=False)
```

Renewal is at most once per 4 h per user, not per request. Concurrent
requests renewing together each set a valid cookie and the last one wins;
stateless, so harmless.

`GET /v1/session` no longer requires a cookie: it answers **200** with
`user: null` and empty `units` / `configured_years` when there is no valid
cookie, and the full payload otherwise. It goes through the same dependency,
so a session past half-life renews on the bootstrap call.

Deleted, no compatibility path:

- `POST /v1/session` (`refresh_session`) and its "Token refreshed" audit
  event. A renewal is not a security event; login and logout stay audited.
- the `refresh_token` cookie, `create_refresh_token`, `TOKEN_TYPE_REFRESH`;
  `delete_session` clears one cookie
- `REFRESH_TOKEN_EXPIRE_HOURS` → `SESSION_MAX_HOURS` (24),
  `ACCESS_TOKEN_EXPIRE_MINUTES` → `SESSION_IDLE_MINUTES` (480). Both renamed
  in `.env.example`, helm values and the ops overlays in the same change.

Role sync (plan 2539) is triggered by renewal instead of refresh. Today a
refresh happens once per access-token lifetime (8 h); renewal at half-life
happens every 4 h of activity, and `ROLE_SYNC_TTL_MINUTES` (60) still gates
the provider call. Deprovisioning exposure stays bounded by
`SESSION_MAX_HOURS`, as it is today by the refresh lifetime.

### Frontend

- `bootstrap()` loses its try/catch: `user = raw.user` (null or user),
  `hasChecked = true`. The guard logic is unchanged.
- `http.ts`: delete `retry`, `beforeRetry`, `isRefresh`, `isSessionCheck`,
  `API_REFRESH_URL`. The `afterResponse` 401 branch keeps one behaviour: a
  401 on any real request means the session hit the hard cap or was cleared,
  so notify and go to the login page. `SessionRead.user` becomes nullable in
  the generated OpenAPI types.

### Not in scope

- Revocation or a JTI denylist: unchanged from ADR-012.
- The OAuth redirects (two 302 per login): correct and documented.
- Turning off the access log: #2934, option 1 shipped as a probe filter.

## Tests

Backend (`tests/unit/v1/test_unit_auth.py`, `tests/integration/v1/test_auth*.py`,
rewritten from "refresh" to "renewal"):

- anonymous `GET /v1/session` → 200, `user` null, no `Set-Cookie`
- request with a token younger than half-life → no `Set-Cookie`
- request with a token past half-life → `Set-Cookie auth_token` with a later
  `exp`, same `auth_time`, role sync task queued
- token past half-life whose `auth_time + SESSION_MAX_HOURS` is in the
  past → 401, no cookie
- a token carrying `type: refresh` (old cookie still in a browser) → 401

Frontend (Playwright CT, `frontend/tests/unit`):

- `bootstrap()` with a 200 `user: null` payload leaves `isAuthenticated`
  false and issues exactly one request

## Rollout

Users holding the old cookie pair at deploy time: `auth_token` still
validates (same claims minus `auth_time`; treat a missing `auth_time` as
`iat` and renew from there), `refresh_token` is ignored and expires on its
own within 24 h. No forced re-login.

## Verification

- `uv run pytest tests/unit/v1/test_unit_auth.py tests/integration/v1/test_auth.py tests/integration/v1/test_auth_security.py`
- `npm run test-ct` for the auth store test
- after deploy: `scripts/loki-dump.sh prod` for a day; expect zero 401 on
  `/v1/session` and zero `POST /v1/session`
