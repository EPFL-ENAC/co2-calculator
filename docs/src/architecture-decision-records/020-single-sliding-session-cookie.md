---
status: in-progress
last_updated: 2026-09-24
summary: "One httponly session cookie renewed server-side at half-life with a hard cap from the OIDC auth_time claim replaces the access + refresh pair; the client never refreshes and GET /session answers 200 with user null when anonymous."
---

# ADR-020: Single sliding session cookie

**Status**: Proposed (issue #2943)
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

- One cookie, `auth_token`, idle lifetime `SESSION_IDLE_MINUTES` (480).
- The token carries `auth_time` (OIDC claim) set at login. Renewal sets
  `exp = min(now + idle, auth_time + SESSION_MAX_HOURS)`; when that is in
  the past the request is 401 and the user logs in again. Sessions cannot
  slide forever.
- Renewal happens in `get_current_user` when `exp - now < idle / 2`, so at
  most once per 4 h per user, and it is where role sync is triggered.
- `GET /v1/session` returns 200 with `user: null` for anonymous callers.
  "What session do I have" has "none" as a valid answer. 401 keeps its
  meaning on every other route.
- No refresh endpoint, no refresh cookie, no client retry.

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

Negative: renewals are no longer audited as events. The audit trail keeps
login and logout; the hard cap bounds a session to 24 h as before.
Revocation is unchanged from ADR-012: none before expiry.

Rollout: an `auth_token` minted before the change validates but is not
renewed (it carries neither `auth_time` nor `iat`), so each user logs in
once more within 8 h of the deploy; the stale `refresh_token` is ignored
and expires within 24 h.
