# Bot Review TODOs: PR #1310

## Source Branch: `feat/458-security-authentication-integration-hardening`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR hardens the authentication trust boundaries by fixing JWT expiry validation in the backend, adding focused regression tests for common JWT/OAuth boundary attacks, and documenting the trust-boundary contract to prevent future regressions.

**Changes:**

- Fix JWT claim validation by explicitly validating decoded claims (including `exp`) and mapping claim-validation failures to HTTP 401.
- Add a dedicated integration security test suite covering alg-confusion, tampering, expired tokens, token-type confusion, `/login-test` gating, cookie flags, and OAuth state mismatch.
- Add documentation (module docstring + implementation plan) describing the three trust boundaries and enumerating follow-ups.

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated 2 comments.

| File                                                                               | Description                                                                                                                    |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| docs/src/implementation-plans/458-security-authentication-integration-hardening.md | Adds security hardening plan documenting trust boundaries and findings (F1–F10) with Tier-1/Tier-2 scope.                      |
| backend/tests/integration/v1/test_auth_security.py                                 | New trust-boundary regression tests for JWT integrity, expiry, type confusion, cookie flags, and OAuth callback failure modes. |
| backend/app/core/security.py                                                       | Fixes `decode_jwt` to validate JWT claims (incl. `exp`) in addition to signature/algorithm checks.                             |
| backend/app/api/v1/auth.py                                                         | Documents auth trust boundaries and clarifies `/login-test`’s debug-only bypass semantics.                                     |

<details>
<summary>Comments suppressed due to low confidence (1)</summary>

**backend/app/core/security.py:82**

- `decode_jwt` returns a 401 with `detail` that includes the raw exception message (`str(e)`). For claim validation errors (e.g., `InvalidClaimError`) this can leak internal validation details to clients. Consider returning a stable, non-detailed message (and optionally a dedicated "Token expired" message for `ExpiredTokenError`) while logging the underlying exception server-side.

```
        JWTClaimsRegistry().validate(payload.claims)
        return payload.claims
    except (BadSignatureError, ExpiredTokenError, InvalidClaimError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 8 out of 8 changed files in this pull request and generated 2 comments.

---

### File: `backend/app/api/v1/auth.py` (Line 17) — Copilot

## The docstring states that identity from `auth_token` is only trusted after signature/algorithm validation AND after the JWT `type` matches the endpoint (access for `/me`, refresh for `/refresh`). However, `GET /auth/me` currently does not enforce `payload.get("type") == "access"`, so a signed refresh token can be accepted as an access token if presented as `auth_token`. Either enforce the access-token type check in `/me` (preferred) or adjust the trust-boundary documentation to match actual behavior.

### File: `docs/src/implementation-plans/458-security-authentication-integration-hardening.md` (Line null) — Copilot

This plan references “husky pre-commit gate”, but this repository uses Lefthook (see `lefthook.yml`) for hook orchestration. Update the wording to avoid confusion for future contributors.

---

### File: `backend/app/api/v1/auth.py` (Line 545) — Copilot

## `/me` is described (module docstring) as requiring an access token, but the call to `resolve_user_by_jwt_payload` does not enforce `payload["type"] == "access"`. This means a refresh token placed in the `auth_token` cookie would be accepted for `/me`, weakening the boundary between access vs refresh tokens. Pass `expected_token_type="access"` here (and consider adding a regression test mirroring `test_refresh_rejects_access_token_in_refresh_cookie`).

### File: `backend/app/core/security.py` (Line 156) — Copilot

`get_current_user` does not enforce that the JWT is an access token. Since many endpoints depend on `get_current_user`, a refresh token could be accepted if sent in the `auth_token` cookie. Consider calling `resolve_user_by_jwt_payload(..., expected_token_type="access")` so the access/refresh boundary is consistently enforced across the app.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **`backend/app/api/v1/auth.py:544` + `backend/app/core/security.py:156`** — `/me` and the shared `get_current_user` dependency don't enforce `payload["type"] == "access"`, so a signed refresh token presented as the `auth_token` cookie is accepted on `/me` and on every endpoint that depends on `get_current_user`. The trust-boundary docstring on `auth.py` already promises this check is in place. Fix: pass `expected_token_type="access"` at both call sites (the helper already supports it — `/refresh` uses the mirror `expected_token_type="refresh"`). Add a regression test `test_me_rejects_refresh_token_in_auth_cookie` mirroring the existing `test_refresh_rejects_access_token_in_refresh_cookie`. Three Copilot comments (auth.py:17 doc-vs-code, auth.py:545, security.py:156) fold into this one fix.

### Maintainability / refactoring

- [ ] **`backend/app/core/security.py:77-82`** — `decode_jwt` 401 detail interpolates `str(e)` from the underlying joserfc exception, disclosing whether the failure was a bad signature, expired token, or invalid claim (mild CWE-209). Bot suppressed as low-confidence; impact is small because the attacker already owns the token they presented, but best practice is a stable opaque message. Fix: replace `detail=f"Could not validate credentials: {str(e)}"` with `detail="Could not validate credentials"` and add a `logger.info("JWT validation failed", extra={"error": str(e), "error_type": type(e).__name__})` before the raise so the diagnostic stays server-side.

_Dropped: the "husky vs Lefthook" wording nit — `grep -i "husky\|lefthook"` against the current plan returns nothing, so the offending text was already removed (likely during the earlier lefthook reformat pass)._
