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
from app.models.user import User, UserProvider

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
        db.rollback = AsyncMock()
        db.add = MagicMock()
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
# Boundary 5 (formerly 3): JWT integrity at the cookie -> backend hop
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

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": forged})
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

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": forged})
    assert response.status_code == 401


def test_jwt_tampered_signature_rejected(client, override_db):
    """Mutating the signature segment must surface as 401."""
    good = _valid_access_token()
    header, payload, sig = good.split(".")
    tampered_sig = "A" + sig[1:] if sig[0] != "A" else "B" + sig[1:]
    tampered = f"{header}.{payload}.{tampered_sig}"

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": tampered})
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

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": forged})
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

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": expired})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Token type / claim validation
# ---------------------------------------------------------------------------


def test_refresh_rejects_access_token_in_refresh_cookie(client, override_db):
    """`POST /session` must check JWT `type == "refresh"`. An access token
    submitted as the refresh cookie is a token-type confusion attack."""
    access = _valid_access_token()  # type == "access"

    response = client.post(f"{API_PREFIX}/session", cookies={"refresh_token": access})
    assert response.status_code == 401


def test_me_rejects_refresh_token_in_auth_cookie(client, override_db):
    """Symmetric to the /refresh case: `GET /session` must reject a refresh JWT
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

    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": refresh})
    assert response.status_code == 401


def test_refresh_rotates_both_auth_and_refresh_cookies(
    client, override_db, monkeypatch
):
    """Pin F5: a successful refresh re-issues BOTH the access cookie and
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

    response = client.post(f"{API_PREFIX}/session", cookies={"refresh_token": refresh})
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
    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": token})
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
    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": token})
    assert response.status_code == 401


def test_me_rejects_legacy_user_id_only_token(client, override_db):
    """Tokens carrying only `user_id` (no institutional_id/provider) must 401.
    Pins the legacy-token rejection at security.py:113-122 / auth.py:544-568."""
    token = create_access_token(
        data={"sub": "abc", "type": "access", "user_id": 7},
        expires_delta=timedelta(minutes=10),
    )
    response = client.get(f"{API_PREFIX}/session", cookies={"auth_token": token})
    assert response.status_code == 401


def test_refresh_rejects_legacy_user_id_only_token(client, override_db):
    """Same as above for `POST /session`."""
    token = create_refresh_token(
        data={"sub": "abc", "user_id": 7},
        expires_delta=timedelta(hours=1),
    )
    response = client.post(f"{API_PREFIX}/session", cookies={"refresh_token": token})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# /auth/login-test gating (F3)
# ---------------------------------------------------------------------------


def test_login_test_registration_matches_debug_flag():
    """Pins F3: ``/auth/login-test`` is added to the router only when
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
# Cookie security flags (F2) — exercised on /auth/callback which sets
# cookies directly on the 302 redirect response.
# ---------------------------------------------------------------------------


def _patch_callback_chain(monkeypatch, *, user_id: int = 1):
    """Wire OAuth + role provider + UserService mocks so /auth/callback
    runs end-to-end and writes an AuthExchangeCode through ``db.add``."""
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
                id=user_id,
                email="real@example.org",
                institutional_id="INST-REAL",
                provider=UserProvider.TEST,
            )
        ),
    )
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())


def test_auth_cookies_secure_when_cookie_secure_true(client, override_db, monkeypatch):
    """COOKIE_SECURE=True ⇒ both cookies carry `Secure` on the callback 302."""
    monkeypatch.setattr(auth_module.settings, "DEBUG", True)  # DEBUG must not matter
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", True)
    _patch_callback_chain(monkeypatch, user_id=1)

    response = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)

    assert response.status_code in (302, 307), response.text
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
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)
    _patch_callback_chain(monkeypatch, user_id=1)

    response = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)

    assert response.status_code in (302, 307), response.text
    set_cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(c for c in set_cookies if c.startswith("auth_token="))
    assert "Secure" not in auth_cookie
    assert "HttpOnly" in auth_cookie  # HttpOnly is unconditional


def test_callback_sets_cookies_and_redirects_to_frontend(
    client, override_db, monkeypatch
):
    """Pin the simplified flow: /auth/callback sets auth cookies directly on
    the 302 response and redirects to FRONTEND_URL, not to /auth/complete."""
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)
    _patch_callback_chain(monkeypatch, user_id=1)

    response = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)

    assert response.status_code in (302, 307)
    set_cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith("auth_token=") for c in set_cookies)
    assert any(c.startswith("refresh_token=") for c in set_cookies)
    assert "auth/complete" not in response.headers["location"]


# ---------------------------------------------------------------------------
# Audit-event failure handling (F7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_event_failure_logs_error_with_marker(monkeypatch, caplog):
    """Pins F7: when the audit DB call fails, `_log_auth_audit_event` logs at
    ERROR with a structured `audit_failure` marker so alerting can fire."""
    fake_request = MagicMock()
    fake_request.url.path = "/v1/session"
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
    """Pins F7: when `must_succeed=True` (only the /auth/callback success path
    opts in), an audit failure re-raises so the caller can refuse to mint
    the session."""
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
    """The institutional_id in the session cookie must come from the role
    provider's ``get_user_id(userinfo)`` derivation of the OAuth claims, not
    from the request envelope or any client-supplied value."""
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
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)

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

    # Attempt to influence identity via query string / headers — must be ignored.
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

    # Inspect the auth cookie set directly on the callback response.
    set_cookies = response.headers.get_list("set-cookie")
    auth_cookie = next(c for c in set_cookies if c.startswith("auth_token="))
    raw = auth_cookie.split("auth_token=", 1)[1].split(";", 1)[0]
    payload_segment = raw.split(".")[1]
    pad = "=" * (-len(payload_segment) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload_segment + pad))
    assert claims["institutional_id"] == "IDP-PROVIDED-ID"


# ---------------------------------------------------------------------------
# End-to-end happy path (simplified direct-cookie flow)
# ---------------------------------------------------------------------------


def test_e2e_callback_session_refresh_logout_happy_path(client, monkeypatch):
    """End-to-end happy path:

    1. /auth/callback -> sets auth_token + refresh_token on the 302
    2. GET /session reads the session
    3. POST /session rotates cookies
    4. DELETE /session clears them

    Single TestClient session so cookies flow naturally between calls.
    """
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)

    user = User(
        id=99,
        email="e2e@example.org",
        institutional_id="E2E-INST",
        provider=UserProvider.TEST,
        display_name="E2E User",
    )

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
    monkeypatch.setattr(
        auth_module.UserService, "upsert_user", AsyncMock(return_value=user)
    )
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=user),
    )
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", AsyncMock())

    async def _override():
        db = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()
        db.add = MagicMock()
        yield db

    app.dependency_overrides[auth_module.get_db] = _override
    try:
        # 1. /auth/callback — sets cookies on the 302 response.
        r_callback = client.get(f"{API_PREFIX}/auth/callback", follow_redirects=False)
        assert r_callback.status_code in (302, 307), r_callback.text
        assert client.cookies.get("auth_token"), "callback must set auth_token"
        assert client.cookies.get("refresh_token"), "callback must set refresh_token"

        # 2. GET /session — uses the auth_token cookie.
        r_me = client.get(f"{API_PREFIX}/session")
        assert r_me.status_code == 200, r_me.text
        body = r_me.json()
        assert body["email"] == "e2e@example.org"
        assert body["institutional_id"] == "E2E-INST"

        # 3. POST /session — rotates both cookies.
        r_refresh = client.post(f"{API_PREFIX}/session")
        assert r_refresh.status_code == 200, r_refresh.text
        set_cookies = r_refresh.headers.get_list("set-cookie")
        assert any(c.startswith("auth_token=") for c in set_cookies)
        assert any(c.startswith("refresh_token=") for c in set_cookies)

        # The rotated access cookie must still authenticate GET /session.
        r_me_after = client.get(f"{API_PREFIX}/session")
        assert r_me_after.status_code == 200, r_me_after.text

        # 4. DELETE /session — clears both cookies.
        r_logout = client.delete(f"{API_PREFIX}/session")
        assert r_logout.status_code == 200, r_logout.text
        client.cookies.clear()
        r_me_logged_out = client.get(f"{API_PREFIX}/session")
        assert r_me_logged_out.status_code == 401
    finally:
        app.dependency_overrides.clear()
