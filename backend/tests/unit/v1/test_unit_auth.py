from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response, status
from fastapi.testclient import TestClient

import app.api.v1.auth as auth_module
from app.api.v1.auth import router as auth_router
from app.main import app

app.include_router(auth_router, prefix="/api/v1/auth")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_login_redirect(monkeypatch):
    mock_authorize_redirect = AsyncMock(return_value="redirected")
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_redirect",
        mock_authorize_redirect,
    )
    request = MagicMock()
    request.url_for = lambda x: "http://test/callback"
    request.headers = {}
    result = await auth_module.login(request)
    assert result == "redirected"
    mock_authorize_redirect.assert_awaited_once()


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
        await auth_module.auth_callback(request, db)
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
        await auth_module.auth_callback(request, db)
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
        await auth_module.auth_callback(request, db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"sub": None}])
async def test_get_me_invalid_token(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("user_attr", ["email", "provider_code"])
async def test_get_me_user_missing(monkeypatch, user_attr):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value={"sub": "1"}))
    mock_user = MagicMock(
        id=1,
        email="test@example.com",
        provider_code="123456",
        roles=["user"],
    )
    setattr(mock_user, user_attr, None)

    mock_get_user_by_user_id = AsyncMock(return_value=mock_user)
    monkeypatch.setattr(auth_module.UserService, "get_by_id", mock_get_user_by_user_id)
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token="token", db=db)
    assert exc.value.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ]


@pytest.mark.asyncio
async def test_get_me_no_token():
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token=None, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_me_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module, "decode_jwt", MagicMock(side_effect=Exception("fail"))
    )
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"type": "access"}, {"sub": None}])
async def test_refresh_token_invalid_payload(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(
            refresh_token="token",
            response=response,
            request=request,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_user_missing(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={"type": "refresh", "sub": "1", "provider_code": "123456"}
        ),
    )
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(
            refresh_token="token",
            response=response,
            request=request,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_no_token():
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(
            refresh_token=None,
            response=response,
            request=request,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module, "decode_jwt", MagicMock(side_effect=Exception("fail"))
    )
    db = MagicMock()
    response = MagicMock()
    request = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(
            refresh_token="token",
            response=response,
            request=request,
            db=db,
        )
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_logs_audit_event(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"type": "refresh", "sub": "1", "user_id": 42}),
    )
    mock_user = MagicMock(id=42, email="test@example.com", provider_code="123456")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
    )
    log_mock = AsyncMock()
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", log_mock)

    db = MagicMock()
    response = Response()
    request = MagicMock()

    result = await auth_module.refresh_token(
        refresh_token="token",
        response=response,
        request=request,
        db=db,
    )

    assert result["message"] == "Token refreshed successfully"
    log_mock.assert_awaited_once()


def test_logout(client):
    async def override_get_db():
        yield MagicMock()

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        response = client.post("/api/v1/auth/logout")
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
    mock_user = MagicMock(id=7, provider_code="987654")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
    )
    log_mock = AsyncMock()
    monkeypatch.setattr(auth_module, "_log_auth_audit_event", log_mock)

    response = Response()
    request = MagicMock()
    db = MagicMock()

    result = await auth_module.logout(
        response=response,
        request=request,
        auth_token="token",
        db=db,
    )

    assert result["message"] == "Logged out successfully"
    log_mock.assert_awaited_once()
