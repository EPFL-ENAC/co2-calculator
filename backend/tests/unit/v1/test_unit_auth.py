from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response, status
from fastapi.testclient import TestClient
from starlette.datastructures import URL, Headers

import app.api.v1.auth as auth_module
import app.core.config as config
from app.main import app
from app.models.user import UserProvider

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
    still hand Entra an https redirect_uri."""
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
    intact — Entra exempts localhost from the https redirect_uri requirement."""
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
@pytest.mark.parametrize("payload", [None, {"sub": None}])
async def test_get_session_invalid_token(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_session(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("user_attr", ["email", "institutional_id"])
async def test_get_session_user_missing(monkeypatch, user_attr):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value={"sub": "1"}))
    mock_user = MagicMock(
        id=1,
        email="test@example.com",
        institutional_id="123456",
        roles=["user"],
    )
    setattr(mock_user, user_attr, None)

    mock_get_user_by_user_id = AsyncMock(return_value=mock_user)
    monkeypatch.setattr(auth_module.UserService, "get_by_id", mock_get_user_by_user_id)
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_session(auth_token="token", db=db)
    assert exc.value.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]


@pytest.mark.asyncio
async def test_get_session_no_token():
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_session(auth_token=None, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_session_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module, "decode_jwt", MagicMock(side_effect=Exception("fail"))
    )
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_session(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"type": "access"}, {"sub": None}])
async def test_refresh_session_invalid_payload(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    bg_tasks = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_session(
            refresh_token="token",
            response=response,
            request=request,
            background_tasks=bg_tasks,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_session_user_missing(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={"type": "refresh", "sub": "1", "institutional_id": "123456"}
        ),
    )
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    bg_tasks = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_session(
            refresh_token="token",
            response=response,
            request=request,
            background_tasks=bg_tasks,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_session_no_token():
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    bg_tasks = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_session(
            refresh_token=None,
            response=response,
            request=request,
            background_tasks=bg_tasks,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_session_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module, "decode_jwt", MagicMock(side_effect=Exception("fail"))
    )
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    bg_tasks = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_session(
            refresh_token="token",
            response=response,
            request=request,
            background_tasks=bg_tasks,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_session_logs_audit_event(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={
                "type": "refresh",
                "sub": "1",
                "institutional_id": "123456",
                "provider": UserProvider.TEST,
            }
        ),
    )
    mock_user = MagicMock(
        id=42,
        email="test@example.com",
        institutional_id="123456",
        provider=UserProvider.TEST,
    )
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=mock_user),
    )
    log_mock = AsyncMock()
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", log_mock)

    db = MagicMock()
    response = Response()
    request = MagicMock()
    bg_tasks = MagicMock()

    result = await auth_module.refresh_session(
        refresh_token="token",
        response=response,
        request=request,
        background_tasks=bg_tasks,
        db=db,
    )

    assert result["message"] == "Token refreshed successfully"
    log_mock.assert_awaited_once()


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
