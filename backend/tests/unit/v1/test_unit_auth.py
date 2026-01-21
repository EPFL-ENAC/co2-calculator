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
            "sub": "1",
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
            id="1", email="test@example.com", user_id="123456", roles=["user"]
        )
    )
    monkeypatch.setattr(auth_module.UserService, "upsert_user", mock_upsert_user)
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
    mock_decode_jwt = MagicMock(return_value={"sub": "1", "user_id": "123456"})
    monkeypatch.setattr(auth_module, "decode_jwt", mock_decode_jwt)

    # Create a real User object for proper validation
    from datetime import datetime

    from app.models.user import GlobalScope, Role, RoleName, User

    mock_roles = [Role(role=RoleName.CO2_USER_STD, on=GlobalScope())]

    # Create a real User instance that can be validated by UserRead
    mock_user = User(
        id="1",
        email="test@example.com",
        display_name="Test User",
        provider="test",
        roles=mock_roles,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    # Set user_id separately as it might be a different field
    if hasattr(mock_user, "user_id"):
        mock_user.user_id = "123456"

    # Create a copy for the second get_by_id call
    mock_user_after_refresh = User(
        id="1",
        email="test@example.com",
        display_name="Test User",
        provider="test",
        roles=mock_roles,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    if hasattr(mock_user_after_refresh, "user_id"):
        mock_user_after_refresh.user_id = "123456"

    # Mock UserService class - when instantiated, return our mock instance
    call_count = {"get_by_id": 0}

    class MockUserService:
        def __init__(self, db):
            self.db = db

        async def get_by_id(self, user_id):
            call_count["get_by_id"] += 1
            # First call returns initial user, second call (if any) returns
            # refreshed user
            if call_count["get_by_id"] == 1:
                return mock_user
            else:
                return mock_user_after_refresh

        async def upsert_user(self, **kwargs):
            return mock_user_after_refresh

    monkeypatch.setattr(auth_module, "UserService", MockUserService)

    # Mock role provider with async get_roles - return same roles to avoid update path
    mock_role_provider = MagicMock()
    # Return the same roles as the user has to avoid the update path
    mock_role_provider.get_roles_by_user_id = AsyncMock(return_value=mock_roles)
    mock_role_provider.type = "test"

    # Mock get_role_provider (sync function that returns the provider)
    mock_get_role_provider = MagicMock(return_value=mock_role_provider)
    monkeypatch.setattr(auth_module, "get_role_provider", mock_get_role_provider)

    # Mock settings to avoid DEBUG check
    mock_settings = MagicMock()
    mock_settings.DEBUG = False
    monkeypatch.setattr(auth_module, "settings", mock_settings)

    # Mock db
    mock_db = AsyncMock()

    # Mock cookie dependency
    result = await auth_module.get_me(auth_token="token", db=mock_db)

    # The result should be a UserRead instance
    assert hasattr(result, "id")
    assert hasattr(result, "email")
    assert result.id == "1"
    assert result.email == "test@example.com"

    # Verify the calls
    mock_decode_jwt.assert_called_once_with("token")
    # get_by_id should be called at least once (and possibly twice if roles differ)
    assert call_count["get_by_id"] >= 1
    mock_role_provider.get_roles_by_user_id.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {"sub": None}])
async def test_get_me_invalid_token(monkeypatch, payload):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value=payload))
    db = MagicMock()
    with pytest.raises(auth_module.HTTPException) as exc:
        await auth_module.get_me(auth_token="token", db=db)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize("user_attr", ["email", "user_id"])
async def test_get_me_user_missing(monkeypatch, user_attr):
    monkeypatch.setattr(auth_module, "decode_jwt", MagicMock(return_value={"sub": "1"}))
    mock_user = MagicMock(
        id="1",
        email="test@example.com",
        user_id="123456",
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
async def test_refresh_token_success(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={
                "type": "refresh",
                "sub": "1",
                "user_id": "123456",
                "email": "test@example.com",
            }
        ),
    )
    mock_user = MagicMock(id="1", email="test@example.com", user_id="123456")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
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
