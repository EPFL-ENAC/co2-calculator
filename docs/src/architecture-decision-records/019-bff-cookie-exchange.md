---
status: superseded
last_updated: 2026-06-29
superseded_by: PR #1687
summary: Superseded. The BFF exchange step was removed; oauth_callback now sets cookies directly on the 302 redirect response. The Safari ITP issue only reproduced on localhost (port mismatch) and was never a production concern.
---

# ADR-019: BFF cookie exchange for OAuth callback

**Status**: Superseded by PR #1687 (2026-06-29)
**Date**: 2026-05-28
**Deciders**: Development Team

> **This ADR is superseded.** The BFF exchange pattern (`AuthExchangeCode`
> table, `POST /v1/session/exchange`, `/auth/complete` SPA page) was removed
> in PR #1687. `GET /v1/auth/callback` now sets `auth_token` /
> `refresh_token` cookies directly on the `302` response and redirects to
> `/`. The root cause of the original Safari ITP regression was a localhost
> port mismatch (frontend on 5173, backend on 8000); in production frontend
> and backend share the same domain (`/api` prefix), so `Set-Cookie` on the
> redirect is accepted by all browsers without ITP interference.

## TL;DR

The OAuth callback at `GET /v1/auth/callback` does not set session
cookies directly. It writes a single-use `AuthExchangeCode` (60 s TTL)
and redirects the browser to `<FRONTEND_URL>/auth/complete#code=<token>`.
The SPA's `/auth/complete` page POSTs the code to
`POST /v1/session/exchange`, which is the only endpoint that emits
`auth_token` / `refresh_token` cookies for a real login. Same-origin
POST → cookies always land.

## Context

The previous flow set `Set-Cookie` on the OAuth-callback's 302 to
`FRONTEND_URL`. Two problems showed up:

1. **Safari ITP can drop `Set-Cookie` on cross-site redirect tails.**
   The callback is served from the backend origin; the redirect
   target is the frontend origin. Safari's Intelligent Tracking
   Prevention may classify the redirect as a tracking pattern and
   silently discard the cookies. The user sees a successful login
   that 401s on every follow-up call — the exact failure mode #458
   F2 (dev-mode `COOKIE_SECURE` over HTTP) documented as a "looks
   like login succeeded but doesn't actually" footgun.
2. **No defensible separation between OAuth machinery and the
   session resource.** `/v1/auth/*` housed both browser-driven OAuth
   endpoints and JSON-API session CRUD. The trust boundaries differed
   (browser redirect chain vs. SPA fetch) but the URL surface did not.

## Decision

**Split the trust boundaries by URL namespace and introduce a BFF
cookie-exchange step.**

- `GET /v1/auth/login` → kick off OAuth.
- `GET /v1/auth/callback` → consume the OAuth code, upsert the user,
  audit the event, mint a single-use `AuthExchangeCode`, redirect to
  `<FRONTEND_URL>/auth/complete#code=<token>`. **No cookies set here.**
- `POST /v1/session/exchange` → atomically consume the code, set
  cookies on the same-origin response, return `{id, email}`.
- `GET /v1/session` (whoami), `POST /v1/session` (refresh),
  `DELETE /v1/session` (logout) → the rest of the session resource.

The code is placed in the URL **fragment** (`#code=...`) not the query
string. Fragments are not sent to the server in `Referer` headers and
do not appear in access logs, so a third-party asset the SPA loads
cannot leak the code.

The exchange endpoint is rate-limited to 10 requests/minute per client
IP (in-process token bucket). A leaked code grants at most a 60 s
brute-force window before expiry, and the bucket caps how many guesses
can land in that window.

## Alternatives Considered

**Direct cookies on the callback (the previous design).**
✓ One round-trip instead of two.
✗ Safari ITP drops cookies on the cross-site redirect tail.
✗ Couples OAuth flow concerns to the session resource.

**[Storage Access API](https://developer.mozilla.org/en-US/docs/Web/API/Storage_Access_API).**
✓ Browser-blessed escape hatch from ITP.
✗ Safari-specific behaviors, still maturing.
✗ Requires a user-gesture prompt in some configurations — bad UX for
a silent post-login bounce.

**Server-side session cookie (BFF storing JWT, issuing a session id).**
✓ Eliminates JWT-in-cookie entirely.
✗ Bigger refactor than the trust-boundary problem warrants right now;
ADR-012 (JWT) remains in force. Track separately.

## Consequences

**Positive**:

- Works across browsers, including Safari ITP, without per-browser
  shims.
- Cookies emitted on a same-origin POST; no cross-site cookie
  reliance.
- Code in fragment → no leakage via logs or `Referer` headers.
- URL surface (`/auth/*` for the browser-driven IdP dance vs `/session/*`
  for the SPA-facing session resource) keeps the trust boundaries
  visible without forcing a `redirect_uri` reconfiguration in Entra.

**Negative**:

- One extra round-trip on login (callback → exchange POST).
- Requires the `auth_exchange_code` DB table and an Alembic migration
  (no backfill — v0.x drops the DB between deploys).
- Adds a +60 s attacker window if the code leaks between callback and
  exchange. Mitigated by: short TTL, single-use atomic consumption,
  fragment placement, IP rate limit on exchange.

**Operational**:

- In-process rate limiter is per-pod. With multiple pods an attacker
  could 10× the rate cap; acceptable for pre-v1.x. A shared limiter is
  future work with F6 (logout denylist) in a later PR.
- `DELETE /v1/session` does not invalidate any outstanding exchange
  codes; they self-clear at TTL. Cleanup of consumed/expired rows is
  not implemented in this PR (table is small; sweep with F6).

## Implementation

```python
# Callback (excerpt)
code = secrets.token_urlsafe(48)
db.add(AuthExchangeCode(
    code=code,
    user_id=user.id,
    expires_at=_naive_utcnow() + timedelta(seconds=60),
))
await db.commit()
return RedirectResponse(
    url=f"{settings.FRONTEND_URL}/auth/complete#code={code}",
    status_code=status.HTTP_302_FOUND,
)

# Exchange (excerpt)
row = await _consume_exchange_code(db, body.code)  # 401 on any failure
user = await UserService(db).get_by_id(row.user_id)
_set_auth_cookies(response, ...)
return {"id": user.id, "email": user.email}
```

## References

- [Safari ITP](https://webkit.org/tracking-prevention/)
- ADR-012 — JWT authentication strategy (the cookies emitted here)
- Plan `458-security-authentication-integration-hardening.md`
