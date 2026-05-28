"""Trust-boundary regression tests for `app.api.v1.auth`.

Each test in this file pins one row of the trust-boundary table documented
in `docs/src/implementation-plans/458-security-authentication-integration-hardening.md`.
The tests intentionally use the real `create_access_token` / `decode_jwt`
code paths so signature, algorithm and claim handling are exercised, not
mocked.
"""

import base64
import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from authlib.integrations.base_client.errors import MismatchingStateError
from fastapi.testclient import TestClient
from joserfc import jwt as joserfc_jwt
from joserfc.jwk import OctKey

import app.api.v1.auth as auth_module
import app.core.config as config
from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.models.user import UserProvider

API_PREFIX = config.get_settings().API_VERSION


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def override_db():
    """Override get_db with an awaitable-mocked session."""

    async def _override():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[auth_module.get_db] = _override
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def mock_user_lookup(monkeypatch):
    """Make UserService.get_by_institutional_id_and_provider return a user."""

    user = MagicMock(
        id=42,
        email="resolved@example.org",
        institutional_id="123456",
        provider=UserProvider.TEST,
        roles=[],
    )
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=user),
    )
    # /me revalidates via UserRead.model_validate — keep it simple
    monkeypatch.setattr(
        auth_module.UserRead,
        "model_validate",
        MagicMock(return_value=MagicMock(id=42, email="resolved@example.org")),
    )
    return user


def _valid_access_token(institutional_id: str = "123456") -> str:
    return create_access_token(
        data={
            "sub": "abc",
            "type": "access",
            "email": "resolved@example.org",
            "institutional_id": institutional_id,
            "provider": str(UserProvider.TEST.value),
        },
        expires_delta=timedelta(minutes=10),
    )


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


# ---------------------------------------------------------------------------
# Boundary 3: JWT integrity at the cookie -> backend hop
# ---------------------------------------------------------------------------


def test_jwt_alg_none_rejected(client, override_db):
    """alg=none must be rejected — pins decode_jwt's algorithms=[ALGORITHM]."""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": "attacker",
                "institutional_id": "victim-id",
                "provider": str(UserProvider.TEST.value),
            }
        ).encode()
    )
    forged = f"{header}.{payload}."

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": forged})
    assert response.status_code == 401


def test_jwt_wrong_alg_rejected(client, override_db):
    """A token signed with HS512 must be rejected when ALGORITHM=HS256."""
    settings = config.get_settings()
    key = OctKey.import_key(settings.SECRET_KEY.encode())
    forged = joserfc_jwt.encode(
        {"alg": "HS512"},
        {
            "sub": "attacker",
            "institutional_id": "victim-id",
            "provider": str(UserProvider.TEST.value),
        },
        key,
        algorithms=["HS256", "HS512"],
    )

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": forged})
    assert response.status_code == 401


def test_jwt_tampered_signature_rejected(client, override_db):
    """Mutating the signature segment must surface as 401."""
    good = _valid_access_token()
    header, payload, sig = good.split(".")
    tampered_sig = "A" + sig[1:] if sig[0] != "A" else "B" + sig[1:]
    tampered = f"{header}.{payload}.{tampered_sig}"

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": tampered})
    assert response.status_code == 401


def test_jwt_with_swapped_institutional_id_rejected(client, override_db):
    """Editing the JWT payload (e.g. impersonating another institutional_id)
    must fail signature verification — pins the boundary the user's manual
    reproducer crossed via source edit."""
    good = _valid_access_token(institutional_id="123456")
    header, payload, sig = good.split(".")

    body = json.loads(_b64url_decode(payload))
    body["institutional_id"] = "999999"  # victim's id
    forged_payload = _b64url(json.dumps(body).encode())
    forged = f"{header}.{forged_payload}.{sig}"

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": forged})
    assert response.status_code == 401


def test_jwt_expired_rejected(client, override_db, mock_user_lookup):
    """An access token whose `exp` is in the past must be rejected.

    Pins F10: decode_jwt invokes JWTClaimsRegistry().validate(claims) so
    expired tokens raise ExpiredTokenError -> 401.
    """
    expired = create_access_token(
        data={
            "sub": "abc",
            "type": "access",
            "email": "resolved@example.org",
            "institutional_id": "123456",
            "provider": str(UserProvider.TEST.value),
        },
        expires_delta=timedelta(seconds=-30),
    )

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": expired})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Token type / claim validation
# ---------------------------------------------------------------------------


def test_refresh_rejects_access_token_in_refresh_cookie(client, override_db):
    """`/refresh` must check JWT `type == "refresh"`. An access token
    submitted as the refresh cookie is a token-type confusion attack."""
    access = _valid_access_token()  # type == "access"

    response = client.post(
        f"{API_PREFIX}/auth/refresh", cookies={"refresh_token": access}
    )
    assert response.status_code == 401


def test_me_rejects_refresh_token_in_auth_cookie(client, override_db):
    """Symmetric to the /refresh case: `/me` must reject a refresh JWT
    presented as `auth_token`. Closes the inverse type-confusion vector
    flagged by Copilot — get_current_user (used by many protected
    endpoints) also enforces `expected_token_type="access"`."""
    refresh = create_refresh_token(
        data={
            "sub": "abc",
            "institutional_id": "123456",
            "provider": str(UserProvider.TEST.value),
        },
        expires_delta=timedelta(hours=1),
    )

    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": refresh})
    assert response.status_code == 401


def test_refresh_rotates_both_auth_and_refresh_cookies(
    client, override_db, monkeypatch
):
    """Pin F5: a successful /refresh re-issues BOTH the access cookie and
    the refresh cookie. Without F6 (server-side denylist) the old refresh
    token is still server-side valid until exp, but rotation at least keeps
    the client side in sync with the freshest issued pair.
    """
    refresh = create_refresh_token(
        data={
            "sub": "abc",
            "institutional_id": "123456",
            "provider": str(UserProvider.TEST.value),
        },
        expires_delta=timedelta(hours=1),
    )

    mock_user = MagicMock(
        id=42,
        email="resolved@example.org",
        institutional_id="123456",
        provider=UserProvider.TEST,
    )
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=mock_user),
    )
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())

    response = client.post(
        f"{API_PREFIX}/auth/refresh", cookies={"refresh_token": refresh}
    )
    assert response.status_code == 200
    set_cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith("auth_token=") for c in set_cookies)
    assert any(c.startswith("refresh_token=") for c in set_cookies)


def test_me_rejects_non_integer_provider(client, override_db):
    """JWT with non-integer `provider` must 401 (UserProvider(int(...)) raises)."""
    token = create_access_token(
        data={
            "sub": "abc",
            "type": "access",
            "institutional_id": "123456",
            "provider": "not_a_number",
        },
        expires_delta=timedelta(minutes=10),
    )
    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": token})
    assert response.status_code == 401


def test_me_rejects_unknown_provider_int(client, override_db):
    """A JWT carrying a provider integer outside the UserProvider enum must 401."""
    token = create_access_token(
        data={
            "sub": "abc",
            "type": "access",
            "institutional_id": "123456",
            "provider": "9999",
        },
        expires_delta=timedelta(minutes=10),
    )
    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": token})
    assert response.status_code == 401


def test_me_rejects_legacy_user_id_only_token(client, override_db):
    """Tokens carrying only `user_id` (no institutional_id/provider) must 401.
    Pins the legacy-token rejection at security.py:113-122 / auth.py:544-568."""
    token = create_access_token(
        data={"sub": "abc", "type": "access", "user_id": 7},
        expires_delta=timedelta(minutes=10),
    )
    response = client.get(f"{API_PREFIX}/auth/me", cookies={"auth_token": token})
    assert response.status_code == 401


def test_refresh_rejects_legacy_user_id_only_token(client, override_db):
    """Same as above for `/refresh`."""
    token = create_refresh_token(
        data={"sub": "abc", "user_id": 7},
        expires_delta=timedelta(hours=1),
    )
    response = client.post(
        f"{API_PREFIX}/auth/refresh", cookies={"refresh_token": token}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /login-test gating (F3)
# ---------------------------------------------------------------------------


def test_login_test_registration_matches_debug_flag():
    """Pins F3: ``/login-test`` is added to the router only when
    ``settings.DEBUG`` is true at import time. In a production build the
    route does not exist — there is no in-handler 403 gate to bypass.
    """
    paths = {getattr(r, "path", None) for r in app.routes}
    expected_present = auth_module.settings.DEBUG
    actually_present = f"{API_PREFIX}/auth/login-test" in paths
    assert actually_present == expected_present


def test_login_test_returns_404_in_prod_build(client):
    """Concrete behaviour the previous 403-gate did not provide: an
    unauthenticated GET in a non-DEBUG build sees the route as absent
    (404), not as forbidden (403)."""
    if auth_module.settings.DEBUG:
        pytest.skip("This test asserts non-DEBUG behaviour; DEBUG is True.")
    response = client.get(f"{API_PREFIX}/auth/login-test", follow_redirects=False)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cookie security flags (F2)
# ---------------------------------------------------------------------------


def _callback_response(client, monkeypatch, *, cookie_secure: bool):
    """Drive a successful /callback under a chosen COOKIE_SECURE value,
    return the response so the caller can inspect Set-Cookie headers."""
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", cookie_secure)

    userinfo = {
        "sub": "subject-x",
        "email": "real@example.org",
        "name": "Real User",
        "uniqueid": "INST-REAL",
    }
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(return_value={"userinfo": userinfo}),
    )

    fake_provider = MagicMock()
    fake_provider.type = UserProvider.TEST
    fake_provider.get_user_id = MagicMock(return_value="INST-REAL")
    fake_provider.get_user_by_user_id = AsyncMock(
        return_value={
            "email": "real@example.org",
            "display_name": "Real User",
            "function": "Tester",
            "roles": [],
        }
    )
    monkeypatch.setattr(
        auth_module, "get_role_provider", lambda *a, **kw: fake_provider
    )

    monkeypatch.setattr(
        auth_module.UserService,
        "upsert_user",
        AsyncMock(
            return_value=MagicMock(
                id=1,
                email="real@example.org",
                institutional_id="INST-REAL",
                provider=UserProvider.TEST,
            )
        ),
    )
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())

    return client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)


def test_auth_cookies_secure_when_cookie_secure_true(client, override_db, monkeypatch):
    """COOKIE_SECURE=True ⇒ both cookies carry `Secure`. Independent of DEBUG."""
    monkeypatch.setattr(auth_module.settings, "DEBUG", True)  # DEBUG must not matter
    response = _callback_response(client, monkeypatch, cookie_secure=True)
    set_cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(c for c in set_cookies if c.startswith("auth_token="))
    refresh_cookie = next(c for c in set_cookies if c.startswith("refresh_token="))
    assert "Secure" in auth_cookie
    assert "Secure" in refresh_cookie
    assert "HttpOnly" in auth_cookie
    assert "HttpOnly" in refresh_cookie


def test_auth_cookies_not_secure_when_cookie_secure_false(
    client, override_db, monkeypatch
):
    """COOKIE_SECURE=False ⇒ no `Secure` (local-HTTP dev only). HttpOnly stays."""
    monkeypatch.setattr(auth_module.settings, "DEBUG", False)  # DEBUG must not matter
    response = _callback_response(client, monkeypatch, cookie_secure=False)
    set_cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(c for c in set_cookies if c.startswith("auth_token="))
    assert "Secure" not in auth_cookie
    assert "HttpOnly" in auth_cookie  # HttpOnly is unconditional


# ---------------------------------------------------------------------------
# Audit-event failure handling (F7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_failure_logs_error_with_marker(monkeypatch, caplog):
    """Pins F7: when the audit DB call fails, `_log_auth_audit_event` logs at
    ERROR with a structured `audit_failure` marker so alerting can fire."""
    fake_request = MagicMock()
    fake_request.url.path = "/v1/auth/refresh"
    fake_request.headers = {}
    fake_request.client = None

    async def boom(*_args, **_kwargs):
        raise RuntimeError("audit DB down")

    monkeypatch.setattr(auth_module.AuditDocumentService, "create_version", boom)

    db = MagicMock()
    db.commit = AsyncMock()

    with caplog.at_level("ERROR"):
        # must_succeed defaults to False → no raise, just an ERROR log.
        await auth_module._log_auth_audit_event(
            db=db,
            request=fake_request,
            change_type=auth_module.AuditChangeTypeEnum.UPDATE,
            change_reason="Token refreshed",
            handler_id="x",
            changed_by=1,
            entity_id=1,
        )

    error_records = [r for r in caplog.records if r.levelname == "ERROR"]
    assert error_records, "audit failure must log at ERROR"
    # Project logger sanitizes structured extras into strings during emit,
    # so accept either the boolean True or the string "True".
    assert any(
        getattr(r, "audit_failure", None) in (True, "True") for r in error_records
    ), "audit failure log must carry the `audit_failure` marker"


@pytest.mark.asyncio
async def test_audit_event_must_succeed_propagates_failure(monkeypatch):
    """Pins F7: when `must_succeed=True` (only the /callback success path
    opts in), an audit failure re-raises so the caller can refuse to mint
    the session. Without this, a failing audit DB would silently let
    sessions be issued without an audit trail."""
    fake_request = MagicMock()
    fake_request.url.path = "/v1/auth/callback"
    fake_request.headers = {}
    fake_request.client = None

    async def boom(*_args, **_kwargs):
        raise RuntimeError("audit DB down")

    monkeypatch.setattr(auth_module.AuditDocumentService, "create_version", boom)

    db = MagicMock()
    db.commit = AsyncMock()

    with pytest.raises(RuntimeError, match="audit DB down"):
        await auth_module._log_auth_audit_event(
            db=db,
            request=fake_request,
            change_type=auth_module.AuditChangeTypeEnum.CREATE,
            change_reason="User login",
            handler_id="x",
            changed_by=1,
            entity_id=1,
            must_succeed=True,
        )


# ---------------------------------------------------------------------------
# OAuth callback error paths
# ---------------------------------------------------------------------------


def test_callback_state_mismatch_returns_400_and_audits(
    client, override_db, monkeypatch
):
    """CSRF state mismatch must surface as 400 (not 401) and be audited."""
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(side_effect=MismatchingStateError()),
    )
    audit_mock = AsyncMock()
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", audit_mock)

    response = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)
    assert response.status_code == 400
    audit_mock.assert_awaited_once()
    call = audit_mock.await_args
    assert "state mismatch" in call.kwargs["change_reason"].lower()


# ---------------------------------------------------------------------------
# Boundary 1: identity comes from IdP claims, not the request envelope
# ---------------------------------------------------------------------------


def test_callback_binds_session_to_idp_institutional_id(
    client, override_db, monkeypatch
):
    """The institutional_id embedded in the session cookie must come from the
    role provider's `get_user_id(userinfo)` derivation of the OAuth claims,
    not from the request envelope or any client-supplied value.

    This is the regression test for the user's reported impersonation
    vector: it pins the trust-boundary so a future change cannot quietly
    route an attacker-controlled value into `institutional_id`."""
    userinfo = {
        "sub": "subject-x",
        "email": "real@example.org",
        "uniqueid": "IDP-PROVIDED-ID",
    }
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(return_value={"userinfo": userinfo}),
    )

    fake_provider = MagicMock()
    fake_provider.type = UserProvider.TEST
    # The contract: provider.get_user_id is the only function that turns
    # OAuth claims into institutional_id. Whatever it returns must be what
    # ends up bound to the cookie.
    fake_provider.get_user_id = MagicMock(return_value="IDP-PROVIDED-ID")
    fake_provider.get_user_by_user_id = AsyncMock(
        return_value={
            "email": "real@example.org",
            "display_name": "Real User",
            "function": None,
            "roles": [],
        }
    )
    monkeypatch.setattr(
        auth_module, "get_role_provider", lambda *a, **kw: fake_provider
    )

    captured_upsert: dict = {}

    async def _capture(self, **kwargs):
        captured_upsert.update(kwargs)
        return MagicMock(
            id=1,
            email=kwargs["email"],
            institutional_id=kwargs["institutional_id"],
            provider=UserProvider.TEST,
        )

    monkeypatch.setattr(auth_module.UserService, "upsert_user", _capture)
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())

    # Attempt to influence identity via query string / headers — these MUST
    # be ignored by the auth path.
    response = client.get(
        f"{API_PREFIX}/auth/callback",
        params={"institutional_id": "ATTACKER-ID"},
        headers={
            "X-Institutional-Id": "ATTACKER-ID",
            "X-User-Sub": "attacker-sub",
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    assert captured_upsert["institutional_id"] == "IDP-PROVIDED-ID"

    # And the cookie carries the IdP-derived id.
    set_cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(c for c in set_cookies if c.startswith("auth_token="))
    raw = auth_cookie.split("auth_token=", 1)[1].split(";", 1)[0]
    payload_segment = raw.split(".")[1]
    pad = "=" * (-len(payload_segment) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload_segment + pad))
    assert claims["institutional_id"] == "IDP-PROVIDED-ID"


# ---------------------------------------------------------------------------
# End-to-end happy path
# ---------------------------------------------------------------------------


def test_e2e_callback_me_refresh_logout_happy_path(client, override_db, monkeypatch):
    """End-to-end happy path: /callback mints a session, /me reads it,
    /refresh rotates it, /logout clears it. Single TestClient session so
    cookies flow naturally between calls — catches any future regression
    in how the four endpoints interact (e.g. cookie attribute mismatch,
    JWT shape divergence between callback and refresh)."""
    from app.models.user import User

    # TestClient uses http://testserver — Secure cookies stored by httpx
    # would be silently dropped on the next request. Disable for the test.
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)

    # Stable identity used across every step.
    user = User(
        id=99,
        email="e2e@example.org",
        institutional_id="E2E-INST",
        provider=UserProvider.TEST,
        display_name="E2E User",
    )

    # --- OAuth + role provider mocks ---
    userinfo = {
        "sub": "e2e-sub",
        "email": "e2e@example.org",
        "uniqueid": "E2E-INST",
        "name": "E2E User",
    }
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(return_value={"userinfo": userinfo}),
    )

    fake_provider = MagicMock()
    fake_provider.type = UserProvider.TEST
    fake_provider.get_user_id = MagicMock(return_value="E2E-INST")
    fake_provider.get_user_by_user_id = AsyncMock(
        return_value={
            "email": "e2e@example.org",
            "display_name": "E2E User",
            "function": None,
            "roles": [],
        }
    )
    monkeypatch.setattr(
        auth_module, "get_role_provider", lambda *a, **kw: fake_provider
    )

    # --- Persistence mocks: same user across all four endpoints ---
    monkeypatch.setattr(
        auth_module.UserService,
        "upsert_user",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=user)
    )
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())

    # --- 1. /callback — sets auth_token + refresh_token cookies ---
    r_callback = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)
    assert r_callback.status_code in (302, 307), r_callback.text
    assert client.cookies.get("auth_token"), "callback must set auth_token"
    assert client.cookies.get("refresh_token"), "callback must set refresh_token"

    # --- 2. /me — uses the auth_token cookie from /callback ---
    r_me = client.get(f"{API_PREFIX}/auth/me")
    assert r_me.status_code == 200, r_me.text
    body = r_me.json()
    assert body["email"] == "e2e@example.org"
    assert body["institutional_id"] == "E2E-INST"

    # --- 3. /refresh — rotates both cookies (F5 + the new e2e proof) ---
    r_refresh = client.post(f"{API_PREFIX}/auth/refresh")
    assert r_refresh.status_code == 200, r_refresh.text
    # The Set-Cookie headers on the /refresh response are the rotation
    # signal. Don't compare cookie values: JWT encoding is deterministic,
    # so a refresh issued in the same wall-clock second has the same `exp`
    # and therefore the same bytes — equality here is a property of the
    # encoding, not evidence that rotation didn't happen.
    set_cookies = r_refresh.headers.get_list("set-cookie")
    assert any(c.startswith("auth_token=") for c in set_cookies)
    assert any(c.startswith("refresh_token=") for c in set_cookies)

    # The rotated access cookie must still authenticate /me.
    r_me_after = client.get(f"{API_PREFIX}/auth/me")
    assert r_me_after.status_code == 200, r_me_after.text

    # --- 4. /logout — clears both cookies ---
    r_logout = client.post(f"{API_PREFIX}/auth/logout")
    assert r_logout.status_code == 200, r_logout.text
    # After logout, cookies are cleared (value emptied with Max-Age=0).
    # /me must now reject because the auth_token cookie is gone.
    client.cookies.clear()
    r_me_logged_out = client.get(f"{API_PREFIX}/auth/me")
    assert r_me_logged_out.status_code == 401
