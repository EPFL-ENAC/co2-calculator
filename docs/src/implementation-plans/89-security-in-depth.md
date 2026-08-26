---
status: delivered
issue: 89
last_updated: 2026-08-26
title: "CSRF: Origin/Sec-Fetch-Site enforcement — implementation plan"
summary: "Fail-closed request-origin middleware to close the *.epfl.ch sibling-subdomain CSRF gap. Compact version; full rationale and endpoint audit in the long-form plan."
---

## The one-paragraph why

All auth is cookies (`SameSite=Lax`, host-only). `Lax` is evaluated
against the **registrable domain**, so every app under `*.epfl.ch` is
same-site to us — one compromised sibling can send credentialed `POST`s
that `Lax` happily attaches `auth_token` to. Three endpoints are
reachable that way today (`files/temp-upload`,
`year-configuration/{year}/upload`, `sync/admin/recompute-stats` — all
`POST`, none needs a JSON body, so no preflight). Docs claim
Origin/Referer checks exist; they don't. Fix: one middleware, no
frontend change, no CSRF token.

## What to change

### 1. New file: `backend/app/core/request_origin.py`

The middleware. **Precondition: enforce only on requests carrying an
auth cookie** (`auth_token`, `refresh_token`, or `session`). CSRF rides
ambient credentials; a cookieless request has no victim authority, so it
skips the check and falls through to normal auth (401 if
unauthenticated). A request with both a cookie and a Bearer header is
still enforced — cookies win. This is the Django/Rails line: token-auth
requests are CSRF-exempt, cookie-auth ones never are.

Decision rules, in order — first match wins:

- **`GET` / `HEAD` / `OPTIONS` → pass.** (Audited: no state-changing
  `GET` in prod; the OAuth callback protects itself with `state`.)
- **`Sec-Fetch-Site` present →** accept only `same-origin` or `none`.
  - `same-site` → **403** — this IS the attack. Not `cross-site` only.
  - **Why primary:** forbidden header — page script can never set it,
    and every supported browser sends it.
- **Else `Origin`, else `Referer` →** exact scheme+host+port match
  against `{FRONTEND_URL} ∪ CSRF_ADDITIONAL_ORIGINS`.
  - Exact match only — no `startswith`, no substring.
  - Literal `Origin: null` → 403, never special-cased.
- **None of the three headers → 403.** Fail closed; an unverifiable
  origin is a rejected origin.

Rejections: `403`, opaque detail, `WARNING` log with route/method/origin.
Length-cap and strip control chars from the logged origin
(attacker-controlled input).

### 2. `backend/app/main.py`

- Register the middleware **after** `SessionMiddleware` in source order
  (so it **runs before** it — no session touch on rejected requests).
- Delete the comment `# NO CORS origins configured allowed on this
instance`; point to the plan instead. Keep CORS disabled — it does
  real work (preflights block all JSON-body and PUT/PATCH/DELETE
  forgeries).

### 3. `backend/app/core/config.py`

```python
CSRF_ADDITIONAL_ORIGINS: str = Field(default="")   # comma-separated
```

**Delivered as a comma-separated `str`, not `list[str]`** — mirrors the
existing `CONNECTOR_ALLOWED_HOST_SUFFIXES`, and avoids pydantic-settings'
JSON-only parsing of `list` from the environment (helm would otherwise
have to set `'["https://…"]'`). A `csrf_additional_origins` computed
field does the split. Empty in every normal deployment; surfaced empty in
`backend/.env.example` and `helm/values.yaml`.

### 4. Cookies: change nothing

- Keep `Secure` + `HttpOnly` + `SameSite=Lax`. Exactly as is.
- **Not `Strict`:** the attacker is same-site by definition — Strict
  blocks nothing they can do, and breaks login state on inbound links.
- **Not `None`, ever:** re-attaches the cookie cross-site for zero gain.
- **Why keep `Lax` at all:** browser-enforced, fails independently of
  our app code, and keeps the cookie **off** cross-site requests
  entirely — stronger than receiving it and returning 403.

### 5. No CSRF token

Naive double-submit is defeated by our exact attacker (any `*.epfl.ch`
host can set a `Domain=epfl.ch` cookie and forge the pair). Signed
double-submit is machinery a same-origin SPA doesn't need. If a
cross-origin frontend ever appears, that's a new ADR.

### 6. Tests

**Unit** — new `backend/tests/unit/core/test_request_origin.py`:

```text
GET  + hostile Origin                              → pass
POST + Sec-Fetch-Site: same-origin                 → pass
POST + Sec-Fetch-Site: same-site                   → 403   ← the assertion
POST + Sec-Fetch-Site: cross-site                  → 403
POST + Origin == FRONTEND_URL                      → pass
POST + Origin: https://evil.com                    → 403
POST + Origin: https://co2-calculator.epfl.ch.evil.com → 403  (substring guard)
POST + Origin: null                                → 403
POST + no Sec-Fetch-Site / Origin / Referer        → 403   (fail closed)
POST + Origin ∈ CSRF_ADDITIONAL_ORIGINS            → pass
POST + Bearer only, no cookies, no headers         → pass middleware (401s later)
POST + auth cookie + Bearer + no headers           → 403   (cookies win)
403 log line with newline-laden Origin             → single line, capped
```

**Integration** — extend
`backend/tests/integration/v1/test_auth_security.py`, real signed cookie
(pattern: `test_temp_upload_auth_ordering.py`):

```text
POST /api/v1/sync/admin/recompute-stats + same-site      → 403, no dispatch
POST /api/v1/files/temp-upload (multipart) + cross-site  → 403, no file
same two + Sec-Fetch-Site: same-origin                   → reach permission gate
```

### 7. Fix the docs (they're currently false)

- `docs/src/backend/01-overview.md:187` — delete "CSRF protection is not
  needed (stateless JWT, no cookies)"; the app is cookie-only.
- `docs/src/architecture/04-auth-flow.md:201` — the claimed
  Origin/Referer checks now actually exist; describe them, link the
  plan, and record the two rebuttals (why not Strict, why keep Lax) so
  they aren't re-litigated in every review.

## Blocker — resolved

**Tableau/connector integration**
(`1552-api-connect-tableau-credentials-plan.md`): confirmed not affected.
The cookie precondition covers it in any case — a server-to-server caller
sends no auth cookie, so the middleware never engages and the request
falls through to normal authentication.

## Delivered — test-suite impact

The middleware being fail-closed means a bare `TestClient` looks exactly
like the forged request it stops: 32 existing tests that POST with an
auth cookie began returning 403. They were doing something a browser
never does, so the fix is realism, not an exemption —
`tests/browser.py::SAME_ORIGIN_HEADERS` is attached at the `TestClient`
construction site in each affected file. The tests that exercise the
middleware itself deliberately omit it.

## Deliberately out of scope

Rate-limiting `recompute-stats` (cost problem, separate issue) ·
ingress-level filtering (app-level holds in dev/tests) · any cookie
attribute change · token schemes.

## Verify before quoting in docs

Chrome's `Lax-allowing-unsafe` ~2-min grace window is being retired —
check current status before citing it. The same-site argument stands
without it.
