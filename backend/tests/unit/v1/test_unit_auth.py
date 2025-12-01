from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
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
async def test_auth_callback_success(monkeypatch):
    mock_token = {
        "userinfo": {
            "email": "test@example.com",
            "uniqueid": "123456",
        }
    }
    mock_authorize_access_token = AsyncMock(return_value=mock_token)
    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_access_token",
        mock_authorize_access_token,
    )
    mock_role_provider = MagicMock()
    mock_role_provider.get_roles = AsyncMock(return_value=(["user"], [], []))
    monkeypatch.setattr(auth_module, "get_role_provider", lambda: mock_role_provider)
    mock_upsert_user = AsyncMock(
        return_value=MagicMock(
            id="1", email="test@example.com", sciper=123456, roles=["user"]
        )
    )
    monkeypatch.setattr(auth_module, "upsert_user", mock_upsert_user)
    db = MagicMock()
    request = MagicMock()
    request.url_for = lambda x: "http://test/callback"
    response = await auth_module.auth_callback(request, db)
    assert isinstance(response, auth_module.RedirectResponse)
    assert response.status_code == status.HTTP_302_FOUND


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
async def test_get_me_success(monkeypatch):
    # Mock decode_jwt (sync function)
    mock_decode_jwt = MagicMock(return_value={"sub": "1", "sciper": "123456"})
    monkeypatch.setattr(auth_module, "decode_jwt", mock_decode_jwt)

    # Mock user object
    mock_user = MagicMock(
        id="1",
        is_active=True,
        email="test@example.com",
        sciper="123456",
        roles=["user"],
    )

    # Mock get_user_by_sciper (async function)
    mock_get_user_by_sciper = AsyncMock(return_value=mock_user)
    monkeypatch.setattr(auth_module, "get_user_by_sciper", mock_get_user_by_sciper)

    # Mock role provider with async get_roles - return different roles to trigger update
    mock_role_provider = MagicMock()
    mock_role_provider.get_roles = AsyncMock(return_value=(["admin", "user"], [], []))

    # Mock get_role_provider (sync function that returns the provider)
    mock_get_role_provider = MagicMock(return_value=mock_role_provider)
    monkeypatch.setattr(auth_module, "get_role_provider", mock_get_role_provider)

    # Mock update_user_roles as ASYNC (this was the missing piece!)
    mock_update_user_roles = AsyncMock()
    monkeypatch.setattr(auth_module, "update_user_roles", mock_update_user_roles)

    # Mock db
    mock_db = AsyncMock()

    # Mock cookie dependency
    result = await auth_module.get_me(auth_token="token", db=mock_db)
    assert result == mock_user

    # Verify the calls
    mock_decode_jwt.assert_called_once_with("token")
    mock_get_user_by_sciper.assert_called_once()
    mock_role_provider.get_roles.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"sub": None}])
async def test_get_me_invalid_token(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("user_attr", ["is_active", "email", "sciper"])
async def test_get_me_user_missing(monkeypatch, user_attr):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value={"sub": "1"}))
    mock_user = MagicMock(
        id="1", is_active=True, email="test@example.com", sciper=123456, roles=["user"]
    )
    setattr(mock_user, user_attr, False if user_attr == "is_active" else None)
    mock_get_user_by_id = AsyncMock(return_value=mock_user)
    monkeypatch.setattr(auth_module, "get_user_by_id", mock_get_user_by_id)
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
async def test_refresh_token_success(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"type": "refresh", "sub": "1"}),
    )
    mock_user = MagicMock(
        id="1", is_active=True, email="test@example.com", sciper=123456
    )
    monkeypatch.setattr(
        auth_module, "get_user_by_id", AsyncMock(return_value=mock_user)
    )
    monkeypatch.setattr(auth_module, "_set_auth_cookies", MagicMock())
    db = MagicMock()
    response = MagicMock()
    result = await auth_module.refresh_token(
        refresh_token="token", response=response, db=db
    )
    assert result["message"] == "Token refreshed successfully"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"type": "access"}, {"sub": None}])
async def test_refresh_token_invalid_payload(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    response = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(refresh_token="token", response=response, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_user_missing(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"type": "refresh", "sub": "1"}),
    )
    monkeypatch.setattr(auth_module, "get_user_by_id", AsyncMock(return_value=None))
    db = MagicMock()
    response = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(refresh_token="token", response=response, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_no_token():
    db = MagicMock()
    response = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(refresh_token=None, response=response, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_refresh_token_exception(monkeypatch):
    monkeypatch.setattr(
        auth_module, "decode_jwt", MagicMock(side_effect=Exception("fail"))
    )
    db = MagicMock()
    response = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.refresh_token(refresh_token="token", response=response, db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout(client):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
