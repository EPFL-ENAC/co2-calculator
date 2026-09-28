from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response, status
from fastapi.testclient import TestClient
from starlette.datastructures import URL, Headers

import app.api.v1.auth as auth_module
import app.core.config as config
from app.main import app
from app.models.user import User

API_PREFIX = config.get_settings().API_VERSION


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login_request(callback_url: str) -> MagicMock:
    """A fake login Request whose url_for returns a Starlette URL.

    Mirrors what ``Request.url_for`` actually returns (a ``URL`` exposing
    ``.scheme``/``.replace``), so the scheme-forcing branch in
    ``oauth_login`` exercises real behaviour rather than a stub string.
    """
    request = MagicMock()
    request.url_for = lambda name: URL(callback_url)
    request.headers = Headers({})
    return request


def _session_request(host: str | None = "128.178.1.2") -> MagicMock:
    """A fake Request carrying the one thing ``get_session`` reads from it.

    ``scope["client"]`` is what uvicorn's ProxyHeadersMiddleware rewrites from
    X-Forwarded-For once FORWARDED_ALLOW_IPS trusts the proxy, so this is the
    address the endpoint must echo back to the browser — never the raw header,
    which a client can forge.
    """
    request = MagicMock()
    request.client = MagicMock(host=host) if host else None
    return request


@pytest.mark.asyncio
async def test_login_redirect(monkeypatch):
    mock_authorize_redirect = AsyncMock(return_value="redirected")
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_redirect",
        mock_authorize_redirect,
    )
    result = await auth_module.oauth_login(_login_request("https://test/callback"))
    assert result == "redirected"
    mock_authorize_redirect.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_redirect_forces_https_behind_tls_terminator(monkeypatch):
    """Regression: behind a TLS-terminating LB the proxy may leave the
    pod-visible scheme as http (e.g. duplicate X-Forwarded-Proto that uvicorn's
    ProxyHeadersMiddleware drops). With COOKIE_SECURE set, oauth_login must
    still hand Entra an https redirect_uri.
    """
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", True)
    captured = {}

    async def capture(request, redirect_uri):
        captured["redirect_uri"] = redirect_uri
        return "redirected"

    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider, "authorize_redirect", capture
    )
    await auth_module.oauth_login(_login_request("http://co2-dev.epfl.ch/callback"))
    assert str(captured["redirect_uri"]) == "https://co2-dev.epfl.ch/callback"


@pytest.mark.asyncio
async def test_login_redirect_keeps_http_for_local_dev(monkeypatch):
    """Local http dev keeps COOKIE_SECURE=false, so http://localhost is left
    intact — Entra exempts localhost from the https redirect_uri requirement.
    """
    monkeypatch.setattr(auth_module.settings, "COOKIE_SECURE", False)
    captured = {}

    async def capture(request, redirect_uri):
        captured["redirect_uri"] = redirect_uri
        return "redirected"

    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider, "authorize_redirect", capture
    )
    await auth_module.oauth_login(_login_request("http://localhost:8000/callback"))
    assert str(captured["redirect_uri"]) == "http://localhost:8000/callback"


@pytest.mark.asyncio
async def test_auth_callback_no_userinfo(monkeypatch):
    mock_token = {"userinfo": None}
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(return_value=mock_token),
    )
    db = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.oauth_callback(request, db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["email", "uniqueid"])
async def test_auth_callback_missing_fields(monkeypatch, field):
    userinfo = {"email": None, "uniqueid": None}
    if field == "email":
        userinfo["uniqueid"] = "123456"
    else:
        userinfo["email"] = "test@example.com"
    mock_token = {"userinfo": userinfo}
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(return_value=mock_token),
    )
    db = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.oauth_callback(request, db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_auth_callback_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        AsyncMock(side_effect=Exception("fail")),
    )
    db = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.oauth_callback(request, db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_session_anonymous_answers_200_with_null_user():
    """No cookie means no session, and that is an answer, not an error (#2943):
    the SPA learns it in one request instead of a 401 followed by a refresh.
    """
    session = await auth_module.get_session(
        _session_request(), user=None, db=MagicMock()
    )

    assert session.user is None
    assert session.units == []
    assert session.configured_years == []


@pytest.mark.asyncio
async def test_get_session_user_missing_email(monkeypatch):
    user = User(id=1, institutional_id="123456", email=None)
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_session(_session_request(), user=user, db=MagicMock())
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "expected"), [("128.178.1.2", "128.178.1.2"), (None, None)]
)
async def test_get_session_echoes_the_address_the_server_saw(
    monkeypatch, host, expected
):
    """The browser cannot discover its own IP, and GlitchTip stores Sentry's
    ``{{auto}}`` sentinel verbatim instead of resolving it (seen on a real dev
    event), so the session payload has to carry a real value for error reports
    to be attributable. It comes from ``scope["client"]`` — which uvicorn
    resolves against FORWARDED_ALLOW_IPS — never from the forgeable header.
    """
    user = User(id=2, institutional_id="123456", email="tester@epfl.ch")
    monkeypatch.setattr(
        auth_module.UnitService, "get_user_units", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(
        auth_module, "list_configured_years", AsyncMock(return_value=[])
    )

    session = await auth_module.get_session(
        _session_request(host), user=user, db=MagicMock()
    )

    assert session.client_ip == expected


def test_logout(client):
    async def override_get_db():
        yield MagicMock()

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        response = client.delete(f"{API_PREFIX}/session")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    cleared = [c for c in response.headers.get_list("set-cookie") if "Max-Age=0" in c]
    assert [c.split("=")[0] for c in cleared] == ["auth_token"]


@pytest.mark.asyncio
async def test_logout_logs_audit_event(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"user_id": 7, "email": "test@example.com"}),
    )
    mock_user = MagicMock(id=7, institutional_id="987654")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
    )
    log_mock = AsyncMock()
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", log_mock)

    response = Response()
    request = MagicMock()
    db = MagicMock()

    result = await auth_module.delete_session(
        response=response,
        request=request,
        auth_token="token",
        db=db,
    )

    assert result["message"] == "Logged out successfully"
    log_mock.assert_awaited_once()
