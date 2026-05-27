---
status: in-progress
issue: 458
last_updated: 2026-05-27
title: "Security: authentication & integration hardening"
summary: "Pin the trust boundaries of the OAuth/JWT auth path with regression tests and explicit documentation. Identify follow-ups for defence-in-depth fixes."
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

| #   | Finding                                                                                                                                                                                                                                                                                                   | Severity | Tier               | Disposition                                                                                                                                                                                                                                                                                                        |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1  | `provider_user.get("code", institutional_id)` at `auth.py:377` is a silent fallback — the dict never carries `"code"` (see `role_provider.py:398-404`). Read of code path is opposite to intent.                                                                                                          | Med      | T2                 | T1 pins the realistic boundary (IdP-derived institutional_id is what gets persisted) via `test_callback_binds_session_to_idp_institutional_id`. The latent shadow branch (dict carrying `"code"`) is not exercised; the follow-up fix removes the `.get("code", …)` entirely so there is no shadow branch to test. |
| F2  | `_set_auth_cookies` sets `secure=not DEBUG`. Tying `Secure` to a debug flag means one env-var change silently downgrades all cookies.                                                                                                                                                                     | High     | T2                 | Test pins both branches today; refactor to a dedicated `COOKIE_SECURE` setting in follow-up.                                                                                                                                                                                                                       |
| F3  | `/login-test` accepts an arbitrary `role` query param. Only DEBUG-gated; no audit-event marker; same code path otherwise as real login.                                                                                                                                                                   | High     | T1                 | Test that `DEBUG=false` → 403 and that the audit event records `provider=TEST`.                                                                                                                                                                                                                                    |
| F4  | `decode_jwt` uses `algorithms=[settings.ALGORITHM]` — correct, but no regression test for `alg=none` or wrong-alg tokens.                                                                                                                                                                                 | High     | T1                 | Add explicit tests.                                                                                                                                                                                                                                                                                                |
| F5  | `/refresh` does not rotate the refresh token. A stolen refresh-token cookie = indefinite session (up to `REFRESH_TOKEN_EXPIRE_HOURS`).                                                                                                                                                                    | Med      | T2                 | Out of scope this PR; documented here.                                                                                                                                                                                                                                                                             |
| F6  | `/logout` does not denylist the JWT. A leaked cookie remains valid until `exp`.                                                                                                                                                                                                                           | Med      | T2                 | Documented.                                                                                                                                                                                                                                                                                                        |
| F7  | `_log_auth_audit_event` swallows every exception (`except Exception:` → warning). A failing audit log on an auth event is exactly the case where we want the failure to be loud.                                                                                                                          | Med      | T2                 | Documented; behaviour unchanged in this PR.                                                                                                                                                                                                                                                                        |
| F8  | Legacy tokens carrying `user_id` (no `institutional_id`/`provider`) are rejected — good — but the rejection branch in `/refresh` writes to `response.delete_cookie` then raises, which is dead-code for the FastAPI response (the exception path discards the modified `response`).                       | Low      | T2                 | Documented; T1 test pins the 401.                                                                                                                                                                                                                                                                                  |
| F9  | `get_role_provider` falls back to `DefaultRoleProvider` on an unknown `PROVIDER_PLUGIN` setting (`role_provider.py:648-653`). Silent provider downgrade is a misconfig amplifier.                                                                                                                         | Low      | T2                 | Documented.                                                                                                                                                                                                                                                                                                        |
| F10 | **`decode_jwt` did not validate the `exp` claim.** joserfc's `jwt.decode` validates only signature + algorithm; claim validation requires an explicit `JWTClaimsRegistry().validate(claims)` call that was missing. An expired access or refresh token was therefore accepted until `SECRET_KEY` rotated. | **High** | T1 — **delivered** | `decode_jwt` in `app/core/security.py` now calls `JWTClaimsRegistry().validate(claims)` and converts `ExpiredTokenError` / `InvalidClaimError` into 401. Pinned by `test_jwt_expired_rejected`.                                                                                                                    |

## Tier-1 scope (this PR)

1. **Plan document** (this file).
2. **Trust-boundary regression tests** at `backend/tests/integration/v1/test_auth_security.py`. Each test targets exactly one row in the table above. No production code changes.
3. **Module docstring on `auth.py`** spelling out the three trust boundaries so a future change has something explicit to break.

Tests in scope:

- **JWT integrity** — `test_jwt_alg_none_rejected`, `test_jwt_wrong_alg_rejected`, `test_jwt_tampered_signature_rejected`, `test_jwt_expired_rejected`. Use the real `create_access_token` / `decode_jwt` from `app.core.security` against `/auth/me`; tamper at the signature or header level.
- **JWT identity binding** — `test_jwt_with_swapped_institutional_id_invalid_signature` confirms that an attacker who edits `institutional_id` in the cookie payload cannot pass `decode_jwt` (the user's reproducer: they edited source, _not_ the cookie; this test pins that the cookie path is closed).
- **Token type confusion** — `test_refresh_rejects_access_token_in_refresh_cookie` (a valid access JWT sent as `refresh_token` is rejected because `type != "refresh"`).
- **Provider validation** — `test_me_rejects_non_integer_provider`, `test_me_rejects_unknown_provider_int` (currently caught by `UserProvider(int(...))` → `ValueError` → 401).
- **Legacy-token rejection** — `test_me_rejects_legacy_user_id_only_token`, `test_refresh_rejects_legacy_user_id_only_token`.
- **`/login-test` gating** — `test_login_test_disabled_when_debug_false` (403), `test_login_test_audits_with_provider_test_when_debug_true`.
- **Cookie security flags** — `test_auth_cookies_secure_in_prod` (`DEBUG=false` → `Secure` set), `test_auth_cookies_not_secure_in_debug` (pins the current coupling; F2 will revisit).
- **OAuth state mismatch** — `test_callback_state_mismatch_returns_400_and_audits` (existing handler at `auth.py:426-443`, untested).
- **Boundary-1 invariant** — `test_callback_uses_idp_claim_for_institutional_id` confirms that the `institutional_id` written to the DB and embedded in the cookie comes from the OAuth `userinfo`, not from anything else on the request. This is the test that would have caught the F1-style silent override the user reported.

Out of scope (T2+):

- F1: change `auth.py:377` to drop the silent `.get("code", ...)`.
- F2: introduce `COOKIE_SECURE` setting independent of `DEBUG`.
- F5: refresh-token rotation.
- F6: logout denylist (requires a server-side store).
- F7: surface audit-log failures (probably 500 on `/callback`, fail-open with metric on `/refresh` and `/logout`).
- F8, F9: small cleanups.

## Approach

- Use `TestClient` + `app.dependency_overrides[get_db]` (mirrors the existing `test_auth.py`/`test_unit_auth.py` patterns) so the new tests run without a DB.
- Use the real `create_access_token` / `create_refresh_token` from `app.core.security` so signature/alg/exp checks exercise the actual code paths, not mocks. Mocking would defeat the point.
- For alg-confusion cases, encode tokens with `joserfc` directly using `{"alg": "none"}` / `{"alg": "HS512"}` so we hit `decode_jwt`'s `algorithms=[settings.ALGORITHM]` pin.
- For `/login-test` gating, `monkeypatch.setattr("app.api.v1.auth.settings.DEBUG", False)`.
- For cookie flags, parse `Set-Cookie` headers off the `RedirectResponse` and assert `Secure` presence/absence.

## Validation

- `uv run pytest backend/tests/integration/v1/test_auth_security.py -v` green.
- Existing `test_auth.py` / `test_unit_auth.py` unchanged and still green.
- `make type-check` clean (husky pre-commit gate per project memory).

## Failure handling

Per #458's stated procedure: if a regression test surfaces a real auth/authz failure during development, treat as high priority — file a follow-up ticket linked to the failing test and to this plan. The tier-2 findings F1–F9 are the seed list.
