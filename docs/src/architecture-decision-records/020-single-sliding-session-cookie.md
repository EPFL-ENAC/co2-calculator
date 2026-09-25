---
status: delivered
last_updated: 2026-09-25
summary: "One httponly session cookie renewed server-side at half-life with a hard cap from the OIDC auth_time claim replaces the access + refresh pair; the client never refreshes and GET /session answers 200 with user null when anonymous."
---

# ADR-020: Single sliding session cookie

**Status**: Accepted (issue #2943, 2026-09-25)
**Date**: 2026-09-24
**Deciders**: Development Team
**Amends**: [ADR-012](./012-jwt-authentication-strategy.md), mitigation
"optional refresh tokens for session continuity"

## TL;DR

Keep JWT-in-httponly-cookie (ADR-012). Drop the second cookie. The backend
renews the one cookie inside the auth dependency when it is past half its
idle life, and refuses renewal once the login is older than the hard cap.
The SPA never calls a refresh endpoint and never sees a 401 on its session
bootstrap.

## Context

ADR-012 chose stateless JWTs and listed short-lived access tokens plus
optional refresh tokens as the expiration strategy. The implementation
issued both as stateless JWTs with no revocation store, so the refresh token
carries none of the revocation benefit it exists for. What it does carry is
a client-driven flow: the SPA cannot see httponly cookies, so on every
anonymous page load and every return after idle it sends a session check
that 401s and a refresh that 401s or succeeds. Those two 401 lines per login
were the trigger (#2934); the round trips and the retry machinery in the
HTTP client are the cost.

## Decision

- One cookie, `auth_token`, idle lifetime `ACCESS_TOKEN_EXPIRE_MINUTES` (2880).
- The token carries `auth_time` (OIDC claim) set at login. Renewal sets
  `exp = min(now + idle, auth_time + REFRESH_TOKEN_EXPIRE_HOURS)`; when that is in
  the past the request is 401 and the user logs in again. Sessions cannot
  slide forever.
- Renewal happens in `get_current_user` when `exp - now < idle / 2`, so at
  most once per 24 h per user, and it is where role sync is triggered.
- Every renewal writes an audit row ("Session renewed"), from a background
  task with its own session, so the trail of who kept a session alive from
  where is as complete as it is today for refreshes.
- `GET /v1/session` returns 200 with `user: null` for anonymous callers.
  "What session do I have" has "none" as a valid answer. 401 keeps its
  meaning on every other route.
- No refresh endpoint, no refresh cookie, no client retry.
- Settings keep their names (`ACCESS_TOKEN_EXPIRE_MINUTES` is the idle
  window, `REFRESH_TOKEN_EXPIRE_HOURS` the hard cap); a docstring, not a
  rename, because a rename touches every env file and ops overlay.

## Alternatives considered

**Keep both cookies, refresh server-side inside `GET /session`.** Removes
the 401 pair but keeps two tokens whose only difference is a `type` claim.
Half the deletion for the same behaviour.

**Readable `has_session` marker cookie so the SPA skips the bootstrap.**
Second source of truth for "logged in" that must expire and clear in step
with the real cookie; still 401s when the marker outlives the session.

**SPA-driven OAuth (authorize URL fetched as JSON, code posted back).**
Removes the two 302s as well, at the price of moving state/PKCE handling to
the browser and rewriting every login path. The redirect flow is the one
Entra documents.

## Consequences

Positive: one cookie, one code path in the guard, no auth branches in the
HTTP client beyond "401 on a real request → login page", a faster return
after idle (no refresh round trip), zero session 401s in the log.

Negative: session length changes. The old refresh endpoint re-minted a
fresh 24 h refresh cookie on every refresh, so a user returning within
24 h stayed logged in with no cap. With 480 min idle and a 24 h cap, an
overnight gap now means a login each morning, and a session ends 24 h
after login whatever the activity. Setting `ACCESS_TOKEN_EXPIRE_MINUTES`
to 2880 (48 h, renewed after 24 h) with a 168 h cap keeps "back within
24 h, still logged in" and bounds the rest to a week; that is what dev,
stage and prod run (2026-09-25, plan 2943, "Behaviour change").

A cookie that is present but refused (expired after idle,
tampered, retired `refresh` type) is still a 401 on the session check, so
"every user's first morning load" writes one 401 line. That is a real
event, not the two-line dance of before. Revocation is unchanged from
ADR-012: none before expiry.

Rollout, in one step (maintainer's call, 2026-09-25, no compatibility
window): an `auth_token` minted before the change validates but is not
renewed (it carries neither `auth_time` nor `iat`), so each user logs in
once more within 8 h of the deploy, which their access token would have
required anyway; the stale `refresh_token` expires within 24 h. An old
frontend bundle left open reads the anonymous 200 as "no user" and shows
the login page; its refresh attempt on an expired cookie meets a 405 and
ends on the login page too.
