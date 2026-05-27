---
status: delivered
issue: 458
last_updated: 2026-05-27
title: "Security: authentication & integration hardening"
summary: "Pin the trust boundaries of the OAuth/JWT auth path with regression tests, fix nine of twelve findings, centralize the JWT→user resolution path, and document the contracts."
---

## Problem

`backend/app/api/v1/auth.py` is the only door into the application. The success criteria of issue #458 require: centralized auth logic, explicit validation of claims from the university IdP, documented assumptions, and tests for the failure modes (missing/invalid tokens, role/claim mismatches, unauthorized access).

The current implementation works against well-behaved Entra OAuth flows but:

- **Has no test pinning the trust boundary.** A code edit at `auth.py:377` (`institutional_id=provider_user.get("code", institutional_id)` — `provider_user` is built by `AccredRoleProvider.get_user_by_user_id` which returns `"institutional_id"`, not `"code"`, so the `.get` _always_ silently falls back) or a substitution of the OAuth claim could swap identities with no test failing.
- **Does not document its assumptions.** A future change touching `_set_auth_cookies`, `decode_jwt`, or the role-provider boundary has no on-file contract to break against.
- **Couples cookie `Secure` to `DEBUG`** (`auth.py:97, 108`). One env-var slip (`DEBUG=true` in a real env) simultaneously unprotects cookies AND enables `/login-test` — the latter accepts any role via query-string and crafts a session as that role.

## Trust boundaries (what we are pinning)

The auth path crosses three boundaries. Each test in this PR targets one.

| #   | Boundary                                  | Trusted artefact                                                                                                     | Untrusted artefact                                                                                          | Pinned by                         |
| --- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------- |
| 1   | IdP → backend                             | OAuth `userinfo` claims from `oauth.co2_oauth_provider.authorize_access_token` (signed by IdP, validated by Authlib) | Anything else on the `/callback` request                                                                    | `test_callback_*`                 |
| 2   | backend → client                          | JWT in `auth_token` / `refresh_token` cookies (signed with `SECRET_KEY`, validated in `decode_jwt`)                  | Cookie bodies, query params, headers carrying identity                                                      | `test_jwt_*`                      |
| 3   | client → backend (on subsequent requests) | `decode_jwt(cookie)` payload after signature + alg check + type check                                                | Anything the client could write (cookies are httpOnly but the JWT body is still client-readable in transit) | `test_get_me_*`, `test_refresh_*` |

The `/login-test` endpoint deliberately bypasses boundary 1 — its only safeguard is `settings.DEBUG`. That gate has to be tested.

## Findings

(Severity = blast radius if the assumption fails. T1 = fix in this PR; T2+ = follow-up.)

| #   | Finding                                                                                                                                                                                                                                                                                                   | Severity | Tier                    | Disposition                                                                                                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | `provider_user.get("code", institutional_id)` at `auth.py:377` was a silent fallback — the dict never carries `"code"`. Read of code path was opposite to intent.                                                                                                                                         | Med      | **Delivered**           | `auth.py` now uses `institutional_id` directly. Pinned by `test_callback_binds_session_to_idp_institutional_id`.                                                                                                                                                                       |
| F2  | `_set_auth_cookies` set `secure=not DEBUG`. One env-var change silently downgraded all cookies.                                                                                                                                                                                                           | High     | **Delivered**           | New `COOKIE_SECURE` setting (default `True`) drives the flag independently. `_set_auth_cookies` reads `settings.COOKIE_SECURE`. Pinned by `test_auth_cookies_secure_when_cookie_secure_true` + `_when_cookie_secure_false`.                                                            |
| F3  | `/login-test` was always registered and used a runtime `if not DEBUG: 403` gate. One misconfig + a code bug in the gate = arbitrary-role session.                                                                                                                                                         | High     | **Delivered**           | The route is now `add_api_route`'d only when `settings.DEBUG` is true at import; in production the path is absent (404, not 403). Pinned by `test_login_test_registration_matches_debug_flag` + `_returns_404_in_prod_build`.                                                          |
| F4  | `decode_jwt` used `algorithms=[settings.ALGORITHM]` — correct — but had no regression test for `alg=none` / wrong-alg.                                                                                                                                                                                    | High     | **Delivered**           | `test_jwt_alg_none_rejected`, `test_jwt_wrong_alg_rejected`, `test_jwt_tampered_signature_rejected`.                                                                                                                                                                                   |
| F5  | `/refresh` re-issued an access cookie but no test pinned that the refresh cookie was rotated alongside. A future regression could leave the refresh cookie stale.                                                                                                                                         | Med      | **Delivered (partial)** | Implementation already rotates both cookies via `_set_auth_cookies`. Pinned by `test_refresh_rotates_both_auth_and_refresh_cookies`. **Full mitigation requires F6 (server-side reuse detection)** — pure rotation without a denylist does not protect against a stolen refresh token. |
| F6  | `/logout` does not denylist the JWT. A leaked cookie remains valid until `exp`.                                                                                                                                                                                                                           | Med      | T2 (out of scope)       | Needs a server-side store (Redis or DB). Deferred per user request — out of #458's success criteria.                                                                                                                                                                                   |
| F7  | `_log_auth_audit_event` swallowed every exception and only logged WARNING. A failing audit log on an auth event was invisible to alerting.                                                                                                                                                                | Med      | **Delivered**           | Bumped to ERROR + structured `audit_failure: true` marker. New `must_succeed` param: `/callback` opts in so an audit failure surfaces as 401 (the outer handler converts the raise); `/refresh` and `/logout` stay best-effort.                                                        |
| F8  | Both `/me` and `/refresh` legacy-token branches wrote to `response.delete_cookie` then raised — dead code, the mutated response was discarded by the exception path.                                                                                                                                      | Low      | **Delivered**           | Deleted from both call sites. Behaviour unchanged; existing legacy-token tests still 401.                                                                                                                                                                                              |
| F9  | `get_role_provider` silently fell back to `DefaultRoleProvider` on an unknown `PROVIDER_PLUGIN` setting. Misconfig amplifier.                                                                                                                                                                             | Low      | **Delivered**           | Now raises `ValueError("Unknown role provider type: …")`. Pinned by `test_get_unknown_role_provider_raises`.                                                                                                                                                                           |
| F10 | **`decode_jwt` did not validate the `exp` claim.** joserfc's `jwt.decode` validates only signature + algorithm; claim validation requires an explicit `JWTClaimsRegistry().validate(claims)` call that was missing. An expired access or refresh token was therefore accepted until `SECRET_KEY` rotated. | **High** | **Delivered**           | `decode_jwt` in `app/core/security.py` now calls `JWTClaimsRegistry().validate(claims)` and converts `ExpiredTokenError` / `InvalidClaimError` into 401. Pinned by `test_jwt_expired_rejected`.                                                                                        |
| F11 | **`DefaultRoleProvider.get_roles` raises `ValueError` on an unknown `RoleName` mid-iteration** (`role_provider.py:168`: `RoleName(parts[0].strip())`). One malformed role from the IdP DoS's the entire login. Caught only by the outer `except Exception` in `/callback` which turns it into a 401.      | **High** | T2                      | xfail(strict) regression tests in `TestDefaultRoleProviderClaimCombinations` document the bug. Fix: wrap `RoleName(...)` in try/except, log+skip the bad entry.                                                                                                                        |
| F12 | `DefaultRoleProvider.get_roles` silently drops roles with an unknown scope type (e.g. `"co2.user.standard@bogus:val"`) with no warning log. Violates the "no silent fallbacks" policy.                                                                                                                    | Low      | T2                      | xfail(strict) test `test_unknown_scope_type_warns_when_skipped` pins the desired behaviour (warn before dropping).                                                                                                                                                                     |

## Delivered (issue #458)

The PR closes all three of #458's success criteria except as noted below.

**Centralized authentication logic** — `resolve_user_by_jwt_payload(payload, db, *, expected_token_type=None)` in `app/core/security.py` is the single trust-boundary check shared by `/auth/me`, `/auth/refresh`, and `get_current_user`. Each callsite shrunk from ~25 lines of inline validation to a 2-line dispatch. `/logout` deliberately retains its own audit-only resolution (best-effort lookup that must not fail the request).

**Explicit validation of IdP claims** — F10 (expired tokens) and F4 (alg confusion / tampered signatures) are now hard-pinned. F1 (silent code fallback) deleted. F2 (cookie Secure flag) decoupled from DEBUG. F3 (`/login-test`) absent in production builds. F9 (unknown PROVIDER_PLUGIN) raises instead of degrading.

**Documented assumptions** — module-level trust-boundary docstring at the top of `auth.py`. `decode_jwt` and `resolve_user_by_jwt_payload` carry their own contracts.

**Tests for the failure modes** specified in the issue:

- _Missing or invalid authentication tokens_ — `test_auth_security.py`: `test_jwt_alg_none_rejected`, `test_jwt_wrong_alg_rejected`, `test_jwt_tampered_signature_rejected`, `test_jwt_with_swapped_institutional_id_rejected`, `test_jwt_expired_rejected` (F10 regression), `test_refresh_rejects_access_token_in_refresh_cookie`, `test_me_rejects_non_integer_provider`, `test_me_rejects_unknown_provider_int`, `test_me_rejects_legacy_user_id_only_token`, `test_refresh_rejects_legacy_user_id_only_token`, `test_refresh_rotates_both_auth_and_refresh_cookies`.
- _Incorrect role/claim combinations_ — `TestDefaultRoleProviderClaimCombinations` in `tests/unit/providers/test_role_provider.py`: bad RoleName (F11 xfail), empty RoleName (F11 xfail), unknown scope type (F12 xfail), non-list `roles`, missing `roles`, non-string entries in a roles list.
- _Unauthorized access attempts_ — `tests/unit/core/test_security_gates.py`: `is_permitted` / `check_permission` / `require_permission` deny-and-allow paths, glob expansion AND-semantics, unknown-path fall-through to OPA.

**Plus** the boundary invariants from Tier 1: `test_callback_binds_session_to_idp_institutional_id`, `test_callback_state_mismatch_returns_400_and_audits`, `test_auth_cookies_secure_when_cookie_secure_true`, `_when_cookie_secure_false`, `test_login_test_registration_matches_debug_flag`, `_returns_404_in_prod_build`.

## Out of scope (Tier-2 follow-ups)

- **F6** — `/logout` denylist. Requires a server-side store (Redis or DB) and necessarily complements F5; explicitly deferred per user direction. Plain rotation (F5) without F6 does not protect against a stolen refresh token.
- **F11** — guard `RoleName(...)` with try/except in `DefaultRoleProvider.get_roles`. Two xfail(strict) tests already pin the desired behaviour.
- **F12** — emit a warning before silently dropping a role with an unknown scope type. One xfail(strict) test pins the desired behaviour.
- Future hardening (not currently a finding): require `payload["type"] == "access"` in `/me`. The centralization step makes this a one-line change (`expected_token_type="access"` at the callsite).

## Approach

- Use `TestClient` + `app.dependency_overrides[get_db]` (mirrors the existing `test_auth.py`/`test_unit_auth.py` patterns) so the new tests run without a DB.
- Use the real `create_access_token` / `create_refresh_token` from `app.core.security` so signature/alg/exp checks exercise the actual code paths, not mocks.
- For alg-confusion, encode tokens with `joserfc` directly using `{"alg": "none"}` (manual base64) / `{"alg": "HS512"}` so we hit `decode_jwt`'s `algorithms=[settings.ALGORITHM]` pin.
- For `/login-test` gating, inspect `app.routes` rather than making a request — the route's _presence_ is the gate.
- For cookie flags, parse `Set-Cookie` headers off the `RedirectResponse` and assert `Secure` presence/absence under both `COOKIE_SECURE` values.
- For F11/F12, mark the desired-behaviour tests `xfail(strict=True)` so they ship as documentation; the fix flips them to passing and removes the marker.

## Validation

- `uv run pytest backend/tests/integration/v1/test_auth_security.py backend/tests/integration/v1/test_auth.py backend/tests/unit/v1/test_unit_auth.py backend/tests/unit/providers/test_role_provider.py backend/tests/unit/core/test_security_gates.py -v` green.
- Wider sweep `uv run pytest tests/unit tests/integration --ignore=tests/integration/services/data_ingestion --ignore=tests/integration/data_ingestion` — 1598 passed + 3 xfailed (F10 was originally one of those, now passing; F11×2 and F12 are the current xfails). The two excluded directories contain pre-existing failures unrelated to auth (Postgres-flavoured tests requiring a container, and an order-dependent CSV flake).
- `mypy app/core/security.py app/api/v1/auth.py tests/integration/v1/test_auth_security.py` clean.

## Failure handling

Per #458's stated procedure: if a regression test surfaces a real auth/authz failure during development, treat as high priority — file a follow-up ticket linked to the failing test and to this plan. The tier-2 follow-ups F6, F11, and F12 are the open seed list.
