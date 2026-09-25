---
status: delivered
issue: 2943
last_updated: 2026-09-25
summary: "One sliding httponly session cookie renewed inside the auth dependency and audited on renewal replaces the access + refresh pair and the client-driven POST /session; GET /session answers 200 with user null when anonymous. Shipped in one step, no compatibility window, after the maintainer chose to test the cut-over on dev and stage."
---

# Single sliding session cookie

Split out of [#2934](https://github.com/EPFL-ENAC/co2-calculator/issues/2934),
where the prod log audit and the scored options live. Decision record:
[ADR-020](../architecture-decision-records/020-single-sliding-session-cookie.md),
which amends ADR-012's "optional refresh tokens" mitigation.

Review decisions of 2026-09-25: renewals are audited; `GET /session`
answers 200 with `user: null` for anonymous callers; the login page stays;
settings keep their names; **no compatibility window**: the maintainer
preferred to experience the cut-over on dev and stage rather than carry a
two-week dual path. Soak on dev, then stage, for several days before prod.

## Why

Every anonymous page load was `GET /v1/session` 401 then `POST /v1/session`
401: the SPA cannot see the httponly cookies, so it asked, got a 401, and
the ky retry hook tried a refresh that also 401'd. Every returning user
after 8 h idle paid the same two round trips before the app rendered.

Both cookies were stateless JWTs signed with the same key with no
revocation table (ADR-012 lists a JTI denylist as "future | optional"). A
refresh token normally buys revocation; ours bought only the client-side
dance. The 24 h bound on a session came from the refresh cookie's lifetime,
and that bound is the one thing kept.

## What shipped

### Backend

One httponly cookie, `auth_token` (name unchanged). Claims: `sub`, `email`,
`institutional_id`, `provider`, `type: access`, plus:

- `exp` = now + `ACCESS_TOKEN_EXPIRE_MINUTES` (2880), the idle window. The
  setting keeps its name; the comment in `config.py` says what it now means.
- `auth_time` (OIDC standard claim) = the login instant, set once by
  `/auth/callback` and `/auth/login-test`, carried unchanged through every
  renewal. `REFRESH_TOKEN_EXPIRE_HOURS` (168) keeps its name and is the hard
  cap on `auth_time`.

`app/core/security.py`:

- `issue_session_cookie(response, *, sub, email, institutional_id, provider, auth_time)`
  mints the cookie with `exp = min(now + idle, auth_time + cap)`.
- `session_needs_renewal(payload, now)`: past half the idle window **and** a
  new cookie would end later than the current one. A token without
  `auth_time` predates the change and is never renewed.
- `get_optional_user(request, response, background_tasks, db, auth_token)`:
  no cookie → `None`; a cookie that fails validation → 401 (a refused
  credential is not "anonymous"); otherwise the detached user, and when
  renewal is due the cookie is re-issued on this response and two
  background tasks are queued, each with its own DB session:
  `audit_session_renewal` (`app/tasks/session_tasks.py`, one "Session
  renewed" audit row, `audit_failure` marker on error) and
  `trigger_role_sync_for_user` (same cadence `POST /session` used to give
  it, plan 2539).
- `get_current_user` is now `get_optional_user` + 401 when `None`.
  `get_jwt_from_cookie` is gone.
- `decode_jwt` catches every `JoseError`, not three of them: before, an
  `alg=none` token on a protected route was a 500 that only the session
  route's broad `except` used to hide.

`app/api/v1/auth.py`:

- `GET /session` → 200 always for a valid or absent cookie; `user: null`
  (dropped from the JSON by `response_model_exclude_none`), empty `units`
  and `configured_years` when anonymous. The route no longer decodes the
  cookie itself: it depends on `get_optional_user`, so the bootstrap call
  renews a session past half-life like any other request.
- `POST /session` deleted, with `create_refresh_token`, `TOKEN_TYPE_REFRESH`
  and the refresh cookie. `DELETE /session` clears one cookie.
- `request_origin.AUTH_COOKIE_NAMES` no longer lists `refresh_token`.

### Frontend

- `http.ts`: `retry: 0`, no `beforeRetry`, no `API_REFRESH_URL`, no
  `isRefresh`. The 401 branch keeps one exemption: the bootstrap GET.
- `auth.ts` `bootstrap()`: one request; 200 without `user` or a 401 means
  anonymous; anything else propagates to the guard instead of being read as
  "logged out". `SessionPayload.user` is optional.
- `openapi.d.ts` regenerated from the app (`SessionRead.user` nullable,
  `POST /session` gone). The committed snapshot had drifted, so the diff
  carries other endpoints' doc changes too.

## Behaviour change: session length

The old pair was not "8 h idle, 24 h cap". Every `POST /session` re-minted
**both** cookies, so the refresh cookie got a fresh 24 h each time the 8 h
access token lapsed. In practice a user stayed logged in indefinitely as
long as they came back within 24 h, with no cap at all.

With the values every environment runs today (480 min / 24 h):

| user                                            | before             | after                       |
| ----------------------------------------------- | ------------------ | --------------------------- |
| works 9:00–18:00, back next morning (15 h idle) | silently continued | login page                  |
| active all day, every day                       | never logged out   | logged out 24 h after login |
| idle more than 24 h                             | login page         | login page                  |

Two ways to go, both config-only:

1. **Keep the new shape** (8 h idle, 24 h cap): a morning login per day,
   Entra SSO usually makes it one silent redirect.
2. **Match the old UX**: `ACCESS_TOKEN_EXPIRE_MINUTES=1440` (24 h idle,
   renewed after 12 h), and either keep a cap (`REFRESH_TOKEN_EXPIRE_HOURS`
   = 168 for one week) or accept no practical cap. Renewal audit rows drop
   to about one per user per 12 h of activity.

Decided 2026-09-25, after dev testing: **2880 min idle / 168 h cap**,
set in the dev, stage and prod overlays (openshift-app-config#73) and as
the defaults in `config.py`, `helm/values.yaml` and `.env.example`. 480 / 24
had brought back the complaints the old rolling refresh was set up to fix:
a login every morning, and a lost save after 8 h idle or at hour 24. 48 h
idle renews after 24 h, so anyone back within 24 h stays logged in, a hard
guarantee the old logic only gave for about 16 h. 1440 min was rejected:
it renews only after 12 h, so a 15 h overnight gap could still log out. A
week's cap means at most one login a week.

## Verification done before review

- Rollout matrix replayed against both code versions: six cookie states
  on the dev and this branch's backend, and the real dev and new frontends
  in Playwright against the other backend's answers. Every combination
  either works or ends on the login page; none errors.
- Renewal watched locally at a 1-minute idle window (fires after 30 s),
  in Chromium and Safari. Real Entra login checked.

## Renewal side effects

- **Every response shape carries the cookie.** FastAPI merges a
  dependency's headers only into plain-data returns, so the renewed
  `Set-Cookie` is parked on `request.state` and `SessionRenewalMiddleware`
  (`app/core/session_renewal.py`, raw ASGI, outermost) appends it at
  response start: 304s, downloads, SSE streams and redirects included.
- **Concurrent renewals.** A page load fans out several requests with the
  same past-half-life cookie; each re-issues it (harmless, stateless) and
  each writes one "Session renewed" row. Accepted: a handful of rows per
  user per renewal window, grouped when reading by `renewed_exp` in the
  snapshot, the `exp` of the cookie they replaced. Revisit if the audit table volume says otherwise.

## Rollout

Users holding the old cookie pair at deploy time: `auth_token` still
validates (same claims minus `auth_time`) but is not renewed; it lives out
its remaining idle window (8 h at most) and the user logs in once, which
their access token would have required anyway. The stale `refresh_token`
is ignored and expires on its own within 24 h.

An **old frontend bundle** still open in a tab keeps working while its
cookie is valid. When anonymous it gets a 200 it reads as "no user" and
shows the login page; on an expired cookie its refresh attempt hits a 405
and it lands on the login page as well. Nobody is stuck, but there is no
dual path: this is the accepted cost of a single step.

## Tests

Backend (`tests/unit/v1/test_unit_auth.py`, `tests/integration/v1/test_auth*.py`,
`tests/unit/core/test_get_current_user_releases_connection.py`):

- anonymous `GET /session` → 200, no `user`, no `Set-Cookie`
- token younger than half-life → no `Set-Cookie`
- token past half-life → `Set-Cookie auth_token`, same `auth_time`, later
  `exp`, one `audit_session_renewal` call
- token at the hard cap → 200, no `Set-Cookie`
- token without `auth_time` → 200, never renewed
- a `type: refresh` JWT presented as `auth_token` → 401
- `alg=none` and wrong-alg tokens → 401 through the dependency
- callback sets one cookie; logout clears one; the end-to-end flow ends on
  an anonymous 200

Frontend (`frontend/tests/unit/session-bootstrap.spec.ts`, Playwright CT):

- 200 without `user` → anonymous, exactly one GET
- 401 → anonymous, exactly one GET, no refresh
- a payload with `user` hydrates the store
- a 500 is an error, not a logged-out user

## Verification

- `uv run pytest tests/unit/v1/test_unit_auth.py tests/integration/v1/test_auth.py tests/integration/v1/test_auth_security.py tests/unit/core/test_get_current_user_releases_connection.py`
- `npx playwright test -c playwright-ct.config.ts tests/unit/session-bootstrap.spec.ts`
- dev, then stage, for several days each: log in, work past the 4 h renewal
  point, confirm no logout and one "Session renewed" audit row; leave a tab
  idle past 8 h and confirm the login page, not an error
- after prod: `scripts/loki-dump.sh prod` for a day; expect zero
  `POST /v1/session` and a 401 on `/v1/session` only for expired cookies
