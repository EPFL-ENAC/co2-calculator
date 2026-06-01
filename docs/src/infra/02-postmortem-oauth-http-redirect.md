# Post-mortem: OAuth login redirected to `http://` callback

**Date:** 2026-06-01 · **Area:** Auth / reverse-proxy · **Severity:** login broken on `dev`

## Summary

After deploying to `dev`, OAuth login failed: the backend sent Entra a
`redirect_uri` of `http://co2-calculator-dev.epfl.ch/api/v1/auth/callback`
instead of `https://…`. Entra rejects a non-https, non-localhost redirect URI,
so the flow never completed.

## Root cause

`oauth_login` builds the callback with `request.url_for("oauth_callback")`,
whose scheme comes from `scope["scheme"]`. The pods run plain http behind a
TLS-terminating load balancer, so the public `https` scheme only reaches the app
via `X-Forwarded-Proto`, applied by uvicorn's `ProxyHeadersMiddleware`.

uvicorn (`0.48.0`, bumped from `0.38.0` in the latest dependency
consolidation) **ignores `X-Forwarded-Proto` unless exactly one copy is
present** — an anti-spoofing guard (`if len(x_forwarded_proto_values) == 1`).
Our chain has two proxy hops (LB → ingress), each stamping the header, so the
pod sees two copies, the guard drops them both, and the scheme stays `http`.

The change was **not** in `auth.py`: the pre-refactor code used the same
`request.url_for(...)` mechanism. The behavioural change rode in on the uvicorn
upgrade.

> Pending confirmation: the duplicate-header path is the leading theory but was
> not directly observed. A "header silently dropped/overwritten by ingress"
> variant produces the identical symptom. The DEBUG log added in this fix
> (`x_forwarded_proto` via `getlist`) will disambiguate on the next deploy.

## Why it was hard to see

- The symptom (`http` redirect) is identical whether the proxy sends **two**
  `X-Forwarded-Proto`, **zero**, or one reading `http`. The output alone can't
  tell them apart.
- The pre-existing DEBUG header log built a `dict` from `request.headers`, which
  collapses duplicates (last-wins) — so it could never have revealed the very
  duplication that caused the bug.

## Fix

Force the callback scheme to https when the deployment is served over https,
gated on the existing `COOKIE_SECURE` flag (the same flag that decides the
cookie `Secure` attribute, and is `false` for local http dev):

```python
redirect_uri = request.url_for("oauth_callback")
if settings.COOKIE_SECURE and redirect_uri.scheme != "https":
    redirect_uri = redirect_uri.replace(scheme="https")
```

Local `http://localhost` dev keeps `COOKIE_SECURE=false`, so it is left intact
(Entra exempts localhost from the https requirement). The fix is correct
regardless of which forwarded-header variant the proxy actually sends.

See `backend/app/api/v1/auth.py` (`oauth_login`) and the regression tests in
`backend/tests/unit/v1/test_unit_auth.py`.

## Follow-up

- **Infra (recommended):** make the **ingress** emit a single canonical
  `X-Forwarded-Proto: https` (set, not append). This fixes every future
  `url_for`-based external URL, not just this one call site.
- **Confirm the trigger:** read the new `x_forwarded_proto` DEBUG log from a
  `dev` request and record here whether it was two-copies, zero, or `http`.
- **Pin `COOKIE_SECURE` explicitly:** it was absent from `helm/values.yaml` and
  relied on the code default (`true`). Now set explicitly under `backend.env`
  since it governs both cookie `Secure` and the redirect scheme. Verify no
  per-env override in the ops repo sets it `false` for a TLS-fronted cluster.

## Lessons

- Don't derive a public scheme from forwarded headers when the deployment shape
  already tells you the truth (`COOKIE_SECURE`). Headers are a fragile signal
  across multi-hop proxies.
- Dependency bumps can silently change request-handling semantics. Treat
  proxy/ASGI server upgrades as behaviour changes, not just patches.
- Diagnostic logs that build a `dict` from headers hide duplicates. Use
  `getlist` / raw headers when the _count_ is what matters.
