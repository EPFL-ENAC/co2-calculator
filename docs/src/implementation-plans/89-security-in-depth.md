---
status: proposed
issue: 89
last_updated: 2026-08-26
title: "Security in depth: CSRF — Origin/Sec-Fetch-Site enforcement"
summary: "Close the sibling-subdomain CSRF gap left by SameSite=Lax on the shared *.epfl.ch registrable domain with a fail-closed Origin/Sec-Fetch-Site middleware, rather than a double-submit cookie token (which the same threat model defeats). Ships with regression tests and corrects two docs that describe controls the codebase does not have."
---

## Problem

The API is entirely cookie-authenticated: `_set_auth_cookies`
(`backend/app/api/v1/auth.py:118`) issues `auth_token` / `refresh_token`
as `httponly`, `samesite="lax"`, `secure=settings.COOKIE_SECURE`,
host-only cookies, and the frontend calls the API with
`credentials: 'include'` (`frontend/src/api/http.ts:32`). That is the
correct shape — but it makes every state-changing endpoint a CSRF target
by default, and today `SameSite=Lax` is the _only_ control standing in
front of some of them.

Two documents assert otherwise, and both are wrong:

- `docs/src/backend/01-overview.md:187` — _"CSRF protection is not needed
  (stateless JWT, no cookies)."_ The premise is false; the app uses
  cookies exclusively.
- `docs/src/architecture/04-auth-flow.md:201` — _"…ride CSRF mitigations
  via `SameSite` and the standard `Origin`/`Referer` checks already in
  place."_ **There are no `Origin`/`Referer` checks in place** — not in
  the app (`backend/app/main.py:364` registers `SessionMiddleware` and
  nothing else; the file even carries the comment `# NO CORS origins
configured allowed on this instance`), not in Traefik, not in the helm
  ingress. A documented control that does not exist is worse than a
  missing one: it is why this gap went unexamined.

### Why `SameSite=Lax` is not enough _here_

We deploy on `co2-calculator.epfl.ch`, `co2-calculator-dev.epfl.ch` and
`co2-calculator-stage.epfl.ch` (`.github/workflows/deploy-mkdocs.yml:14`).
`SameSite` is evaluated against the **registrable domain**, so every one
of the hundreds of applications under `*.epfl.ch` is _same-site_ to us.
One XSS, or one attacker-influenced app, anywhere under `epfl.ch` is
enough to issue credentialed, state-changing requests to this API, and
`Lax` will attach `auth_token`.

Chrome's `Lax-allowing-unsafe` grace period compounds it: a top-level
cross-site `POST` still carries a cookie less than ~2 minutes old, and
our cookies are re-minted on every `POST /api/v1/session` refresh, so
that window reopens continuously.

### What is _already_ safe (and must stay that way)

The absence of CORS is doing real work, and the audit below is the reason
this plan is narrow rather than a full token scheme:

- **JSON-body endpoints are unreachable cross-origin.**
  `application/json` is not a CORS-simple content type, so the browser
  preflights; no CORS headers come back, so the request is never sent.
  The attacker cannot downgrade to a simple content type either —
  FastAPI's body reader (`fastapi/routing.py`) only calls
  `request.json()` when the content type is `application/*` +
  `json`/`+json`, so a `text/plain` body reaches Pydantic as raw bytes
  and 422s before any handler logic runs.
- **`PUT` / `PATCH` / `DELETE` always preflight** → blocked outright.
- **No state-changing `GET` in production.** Every `GET` route was
  scanned for DB mutation; the only genuine hit is `oauth_callback`
  (`auth.py:368`), which is protected by the OAuth `state` parameter —
  `MismatchingStateError` is handled explicitly. `/v1/auth/login-test`
  _is_ a `GET` that mints a session from a query-string `role`, but it is
  registered only under `settings.DEBUG` (`auth.py:452`) and helm pins
  `DEBUG: "false"` (`helm/values.yaml:32`).

This is why **a double-submit cookie token is the wrong fix**: it would
add a token to every frontend call while leaving the actual hole open.
Naive double-submit is defeated by exactly the attacker in our threat
model — any `*.epfl.ch` host can set a `Domain=epfl.ch` cookie in the
victim's browser and forge the value the header must match. A signed /
HMAC double-submit would close it, but that is strictly more machinery
than a same-origin SPA needs.

### The exposed surface

Three endpoints are reachable by a same-site attacker today. All are
`POST` (the only unsafe method that can avoid a preflight) and all avoid
a JSON body:

| Endpoint                                                                      | Why reachable                                                                                                                                        | Blast radius                                                                                                                                                                                                                  |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/v1/files/temp-upload` (`files.py:315`)                             | `multipart/form-data` is a CORS-simple content type → no preflight. `fetch` with a `FormData` body gives the attacker full control of the file bytes | Attacker-chosen file written to temp storage, bounded by `validate_upload_mimetype` (`files.py:122`). **Not** a data-poisoning path — ingesting it requires the JSON `POST /api/v1/sync/dispatch`, which is preflight-blocked |
| `POST /api/v1/year-configuration/{year}/upload` (`year_configuration.py:940`) | same (`File(...)` + `Form(...)`)                                                                                                                     | Superadmin-gated file write                                                                                                                                                                                                   |
| `POST /api/v1/sync/admin/recompute-stats` (`data_sync.py:2245`)               | **query parameters only, no body** — a plain `<form method="POST">` reaches it                                                                       | Forces a full stats recompute across every `(module_type_id, year)` scope. Idempotent, so no corruption, but a cheap pipeline and DB-pool hammer                                                                              |

`POST /api/v1/session` is also bodyless-reachable; its only effect is
session extension, so it is in scope for the fix but is not a finding on
its own.

Note that all three are permission-gated
(`backoffice.pipeline_operations.edit`,
`backoffice.configuration.edit`, `modules.*.sync`). CSRF rides the
victim's session, so the gate is exactly what makes the attack worth
mounting — it is not a mitigation.

## Approach

Add one fail-closed request-origin middleware in
`backend/app/main.py`. Stateless, ~20 lines of logic, **no frontend
change** (the SPA is already same-origin), and it covers every endpoint
including ones not yet written — which is the property the per-endpoint
audit above cannot give us.

Decision rules, in order:

1. **Skip safe methods** — `GET`, `HEAD`, `OPTIONS`. Justified by the
   "no state-changing `GET`" audit above; the app-level routes (`/`,
   `/healthz`, `/ready`, `/health/deps`) are all `GET` and fall out for
   free.
2. **Skip the documented cross-site entry point** — `GET
/api/v1/auth/callback` is cross-site by design and already carries its
   own state protection. It is a `GET`, so rule 1 already covers it; the
   exemption is written down explicitly so a future change to that route
   cannot silently lose the reasoning.
3. **`Sec-Fetch-Site`** — when present, require `same-origin` (accept
   `none`, which is a user-initiated navigation). Every browser we
   support sends this header, so it is the primary check.
4. **`Origin`, then `Referer`** — match the scheme+host+port against an
   allowlist derived from `settings.FRONTEND_URL`, plus an explicit
   settings field for any extra origin an environment genuinely needs.
5. **Fail closed** — an unsafe method arriving with _none_ of
   `Sec-Fetch-Site` / `Origin` / `Referer` is rejected with `403`. Per
   the no-silent-fallbacks invariant, an unverifiable origin is a
   rejected origin, not a trusted one.

Rejections return `403` with an opaque detail and are logged at
`WARNING` with a structured marker (route path, method, observed origin)
so the ingress can alert on them.

### Where it goes

`backend/app/main.py`, registered **after** `SessionMiddleware` in source
order so it runs **before** it — the origin check must not depend on
session state, and a rejected request should not touch the session
cookie. The middleware itself lives in
`backend/app/core/request_origin.py` (new), keeping `main.py` to
registration.

### Configuration

One new field in `backend/app/core/config.py`:

```python
CSRF_ADDITIONAL_ORIGINS: list[str] = Field(
    default_factory=list,
    description=(
        "Extra origins accepted on state-changing requests, beyond the one "
        "derived from FRONTEND_URL. Empty in every normal deployment."
    ),
)
```

Surfaced in `helm/values.yaml` and `backend/.env.example` as empty. It
exists so a genuine need (a second frontend host during a migration) does
not force a code change; it is not expected to be set.

## Changes

| File                                                 | Change                                                                                                                                                   |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/core/request_origin.py`                 | **New.** The middleware and its allowlist derivation                                                                                                     |
| `backend/app/main.py`                                | Register the middleware; delete the now-false `# NO CORS origins configured allowed on this instance` comment and replace it with a pointer to this plan |
| `backend/app/core/config.py`                         | Add `CSRF_ADDITIONAL_ORIGINS`                                                                                                                            |
| `backend/.env.example`, `helm/values.yaml`           | Surface the new setting, empty                                                                                                                           |
| `backend/tests/unit/core/test_request_origin.py`     | **New.** Unit tests for the decision rules                                                                                                               |
| `backend/tests/integration/v1/test_auth_security.py` | Extend with the end-to-end regression                                                                                                                    |
| `docs/src/backend/01-overview.md`                    | Replace the false "CSRF protection is not needed" line                                                                                                   |
| `docs/src/architecture/04-auth-flow.md`              | Make the `Origin`/`Referer` claim true, and link here                                                                                                    |

## Tests

Every case below fails without the middleware.

**Unit** (`tests/unit/core/test_request_origin.py`) — drive the decision
rules directly, no DB:

- `GET` with a hostile `Origin` → passes (safe method).
- `POST` with `Sec-Fetch-Site: same-origin` → passes.
- `POST` with `Sec-Fetch-Site: same-site` → **403** (this is the
  sibling-subdomain case, and the single most important assertion in
  the file).
- `POST` with `Sec-Fetch-Site: cross-site` → 403.
- `POST` with no `Sec-Fetch-Site` but `Origin` matching `FRONTEND_URL` →
  passes; a mismatched `Origin` → 403.
- `POST` with `Origin: https://co2-calculator.epfl.ch.evil.com` → 403
  (guards against a substring/`startswith` match creeping into the
  allowlist comparison).
- `POST` with none of the three headers → 403 (fail-closed).
- An origin listed in `CSRF_ADDITIONAL_ORIGINS` → passes.

**Integration** (`tests/integration/v1/test_auth_security.py`) — with a
real signed token in the cookie jar, mirroring the pattern in
`tests/unit/v1/test_temp_upload_auth_ordering.py`, which mints a genuine
token rather than relying on `dependency_overrides`:

- `POST /api/v1/sync/admin/recompute-stats` with
  `Sec-Fetch-Site: same-site` → **403**, and the recompute is not
  dispatched.
- `POST /api/v1/files/temp-upload` with a `multipart/form-data` body and
  a cross-site origin → **403**, and no file is written.
- The same two calls with `Sec-Fetch-Site: same-origin` reach their
  normal permission gate — proving the middleware did not become a
  blanket denial.

## Risks

- **A legitimate non-browser client is rejected.** Anything calling this
  API server-to-server sends none of the three headers and will now get
  a `403`. The connector/Tableau integration
  (`1552-api-connect-tableau-credentials-plan.md`) is the one to check
  before merging — if it authenticates by cookie rather than by its own
  credential path, it needs an explicit exemption keyed on its auth
  method, not on a header it could spoof. **This is the one blocking
  question for review.**
- **Fail-closed on a missing header** could surface an old browser or an
  exotic proxy that strips `Origin`. Accepted deliberately: the
  alternative is a silent fallback, and the `WARNING` log makes the case
  visible rather than mysterious.
- **Not a substitute for `SameSite`.** Both stay. The middleware is
  defense in depth; `samesite="lax"` remains the first line and must not
  be relaxed to `none` on the strength of this change.

## Out of scope

- Any change to the cookie attributes themselves.
- A CSRF _token_ scheme, double-submit or otherwise — see the rationale
  above. If a future requirement puts a genuinely cross-origin frontend
  in play, that decision reopens as an ADR, not as an edit to this plan.
- Rate limiting on the exposed endpoints. `recompute-stats` deserves a
  throttle on its own merits; that is a separate issue, since it is a
  cost problem rather than a CSRF one.
- Ingress-level origin filtering. Keeping the control in the app means it
  holds in local dev and in tests, where no Traefik exists.

## References

- `458-security-authentication-integration-hardening.md` — the trust
  boundaries this plan extends. Boundary 3 (cookie → backend) gains a
  fourth check: _the request must have come from us_.
- OWASP Top 10:2025 A01 (Broken Access Control — CSRF is classified
  here), A02 (Security Misconfiguration).
- OWASP ASVS 5.0 V3, Web Frontend Security — CSRF defenses, which admit
  origin verification as a primary control, not merely a supplement.
