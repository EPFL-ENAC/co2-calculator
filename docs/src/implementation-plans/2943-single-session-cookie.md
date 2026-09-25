---
status: in-progress
issue: 2943
last_updated: 2026-09-25
summary: "Replace the access + refresh cookie pair and the client-driven POST /session refresh with one sliding httponly session cookie renewed inside the auth dependency, audited on renewal; two dated steps so a two-week-old frontend tab keeps working; GET /session answers 200 with user null once the window closes."
---

# Single sliding session cookie

Split out of [#2934](https://github.com/EPFL-ENAC/co2-calculator/issues/2934),
where the prod log audit and the scored options live. Decision record:
[ADR-020](../architecture-decision-records/020-single-sliding-session-cookie.md),
which amends ADR-012's "optional refresh tokens" mitigation.

**Auth change: this plan is reviewed by both maintainers before the
implementation PR opens.** Decisions taken on the review of 2026-09-25:

- renewals **are** audited (one row per renewal, like "Token refreshed" today)
- `GET /session` answers 200 with `user: null` for anonymous callers, but
  only in step 2; the login page stays as it is
- settings keep their names; a comment explains the new meaning, so no
  `.env`, helm value or ops overlay changes hands
- rollout is the critical part: current prod users must not notice, and the
  backend serves both the old and the new frontend for about two weeks,
  until every cached bundle and open tab is gone
- soak on dev, then stage, for several days before prod

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

One httponly cookie, `auth_token` (name unchanged; every test and the
logout path already know it). Claims: the existing `sub`, `email`,
`institutional_id`, `provider`, plus:

- `exp` = now + `ACCESS_TOKEN_EXPIRE_MINUTES` (480). The setting keeps its
  name; its docstring becomes "idle lifetime of the session cookie, renewed
  on activity".
- `auth_time` (OIDC standard claim) = the login instant, set once at
  `/auth/callback` and `/auth/login-test`, carried unchanged through every
  renewal. `REFRESH_TOKEN_EXPIRE_HOURS` (24) keeps its name and becomes the
  hard cap on `auth_time`; its docstring says so.

Renewal lives in `get_current_user`, which gains `response: Response`,
`request: Request` and `background_tasks: BackgroundTasks` parameters
(FastAPI merges a dependency's `Set-Cookie` into the route response):

```
if exp - now < ACCESS_TOKEN_EXPIRE / 2:
    new_exp = min(now + ACCESS_TOKEN_EXPIRE, auth_time + REFRESH_TOKEN_EXPIRE)
    if new_exp <= now: raise 401          # hard cap reached
    set_cookie(auth_token, ..., max_age=new_exp - now)
    background_tasks.add_task(audit_session_renewal, user, request_context)
    background_tasks.add_task(trigger_role_sync_for_user, user_id, force=False)
```

Renewal is at most once per 4 h per user, not per request. Concurrent
requests renewing together each set a valid cookie and the last one wins;
stateless, so harmless. The audit row (`change_reason="Session renewed"`,
same snapshot shape as today's "Token refreshed") is written by a
background task with its own session, so the request path never commits
mid-dependency; a failed audit write logs at ERROR with the
`audit_failure` marker, exactly as `POST /session` does today.

Tokens minted before the change carry neither `auth_time` nor `iat`. They
are not renewed: they live out their remaining idle window and the user
logs in once. See Rollout.

### Frontend

- `http.ts`: delete `retry`, `beforeRetry`, `isRefresh`, `API_REFRESH_URL`.
  The `afterResponse` 401 branch keeps one behaviour: a 401 on any real
  request means the session hit the hard cap or was cleared, so notify and
  go to the login page. The session check stays exempt from that redirect.
- `bootstrap()` treats **both** a 401 and a 200 with `user: null` as
  "anonymous", without retrying. That is what lets the frontend ship before
  the backend flips `GET /session` in step 2.
- `SessionRead.user` becomes nullable in the generated OpenAPI types in
  step 2, when the backend actually sends it.

### Not in scope

- Revocation or a JTI denylist: unchanged from ADR-012.
- The OAuth redirects (two 302 per login): correct and documented.
- The login page: unchanged.

## Rollout: two dated steps

The constraint: a browser tab or a cached bundle of the **old** frontend
must keep working for about two weeks after step 1 reaches prod. The old
frontend expects a 401 on `GET /session` when anonymous, calls
`POST /session` on any 401, and treats a 200 on `GET /session` as "logged
in, here is the user".

### Step 1: new cookie, old contract (one PR, soaks on dev then stage)

Backend:

- `/auth/callback` and `/auth/login-test` mint only `auth_token`, with
  `auth_time`; no `refresh_token` is set any more
- `get_current_user` renews as designed above
- `GET /session` still answers 401 when there is no valid cookie
- `POST /session` stays, and is the compatibility path: with a valid
  `refresh_token` (old login) it behaves as today; with none and a valid
  `auth_token` it renews that cookie and answers 200; with neither, 401.
  A `# removed in step 2 (#2943)` comment carries the date.
- `delete_session` clears both cookie names for the whole window

Frontend: the interceptor and `bootstrap()` changes above.

What each user sees:

| user state at deploy                   | behaviour                                                                                                                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| old frontend tab, old cookie pair      | backend renews `auth_token` on activity, so no 401 while active; at the 24 h cap the old `refresh_token` has expired too, so `POST /session` → 401 → login page, exactly today's behaviour |
| old frontend tab, logs in after deploy | gets the new cookie only; renewed on activity; at the cap, `POST /session` renews nothing → login page, same as today at the refresh limit                                                 |
| new frontend, any cookie               | one `GET /session` per app start, no refresh call; a 401 is "anonymous"                                                                                                                    |
| anonymous visitor, either frontend     | old frontend: 401 + 401 as today; new frontend: one 401                                                                                                                                    |

Nobody is logged out by the deploy. The one visible change is a re-login
within 8 h for users whose pre-deploy token cannot be renewed, which is
what would have happened anyway at their 8 h access-token limit.

### Step 2: flip the contract (second PR, after the window)

Earliest date: two weeks after step 1 reaches prod, written into the step 2
PR body.

- `GET /session` answers 200 with `user: null` when anonymous
- delete `POST /session`, the `refresh_token` clearing in `delete_session`,
  `create_refresh_token`, `TOKEN_TYPE_REFRESH`, and the 401 branch in
  `bootstrap()`
- `SessionRead.user: UserRead | None` in OpenAPI and the frontend types

After step 2 a normal day has zero 401 on `/v1/session`.

## Tests

Backend, rewritten from "refresh" to "renewal" in
`tests/unit/v1/test_unit_auth.py`, `tests/integration/v1/test_auth*.py`:

- request with a token younger than half-life → no `Set-Cookie`
- request with a token past half-life → `Set-Cookie auth_token` with a later
  `exp`, same `auth_time`, one audit row "Session renewed", role sync
  queued
- token past half-life whose `auth_time + cap` is in the past → 401, no
  cookie
- token without `auth_time` (pre-deploy) → accepted until its `exp`, never
  renewed
- a token carrying `type: refresh` on a protected route → 401
- step 1: `POST /session` with an old `refresh_token` → 200 + new cookie;
  with only a valid `auth_token` → 200 + renewed cookie; with none → 401
- step 1: anonymous `GET /session` → 401; step 2: → 200, `user` null, no
  `Set-Cookie`

Frontend (Playwright CT, `frontend/tests/unit`):

- `bootstrap()` with a 401 leaves `isAuthenticated` false and issues
  exactly one request (no refresh)
- `bootstrap()` with a 200 `user: null` payload does the same

## Verification

- `uv run pytest tests/unit/v1/test_unit_auth.py tests/integration/v1/test_auth.py tests/integration/v1/test_auth_security.py`
- `npm run test-ct` for the auth store tests
- dev, then stage, for several days each: log in with an old-frontend tab
  kept open across the deploy (hard-refresh disabled), work past the 4 h
  renewal point, confirm no logout and one "Session renewed" audit row
- after step 2 in prod: `scripts/loki-dump.sh prod` for a day; expect zero
  401 on `/v1/session` and zero `POST /v1/session`
