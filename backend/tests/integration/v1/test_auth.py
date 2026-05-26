from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.core.config as config
from app.main import app
from app.models.user import UserProvider


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def csrf_client(csrf_enabled_settings):
    """Client with CSRF enabled and middleware initialized for each test."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


async def test_login_redirect_uri_https(client, monkeypatch):
    from starlette.responses import RedirectResponse

    import app.api.v1.auth as auth_module

    async def fake_authorize_redirect(request, redirect_uri):
        return RedirectResponse(url=f"https://fake-oauth?redirect_uri={redirect_uri}")

    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_redirect",
        fake_authorize_redirect,
    )

    settings = config.get_settings()
    prefix = settings.API_VERSION

    response = client.get(
        f"{prefix}/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert (
        "redirect_uri=https%3A%2F%2F" in location or "redirect_uri=https://" in location
    )


def test_refresh_logs_audit_event(client, monkeypatch):
    import app.api.v1.auth as auth_module

    async def override_get_db():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={
                "type": "refresh",
                "sub": "1",
                "user_id": 5,
                "institutional_id": "654321",
                "provider": UserProvider.TEST,
                "email": "test@example.com",
            }
        ),
    )
    mock_user = MagicMock(id=5, email="test@example.com", institutional_id="654321")
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=mock_user),
    )
    create_version_mock = AsyncMock()
    monkeypatch.setattr(
        auth_module.AuditDocumentService,
        "create_version",
        create_version_mock,
    )

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        response = client.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": "token"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["message"] == "Token refreshed successfully"
    assert create_version_mock.await_count == 1


def test_logout_logs_audit_event(client, monkeypatch):
    import app.api.v1.auth as auth_module

    async def override_get_db():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"user_id": 7, "email": "test@example.com"}),
    )
    mock_user = MagicMock(id=7, institutional_id="987654")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
    )
    create_version_mock = AsyncMock()
    monkeypatch.setattr(
        auth_module.AuditDocumentService,
        "create_version",
        create_version_mock,
    )

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        response = client.post("/api/v1/auth/logout", cookies={"auth_token": "token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
    assert create_version_mock.await_count == 1


def test_csrf_bootstrap_returns_token_and_cookie(csrf_client, csrf_enabled_settings):
    """GET /auth/csrf returns plain token and sets signed CSRF cookie."""
    response = csrf_client.get("/api/v1/auth/csrf")

    assert response.status_code == 200
    payload = response.json()
    assert payload["csrf_enabled"] is True
    assert isinstance(payload["csrf_token"], str)
    assert payload["csrf_token"]

    cookie_key = csrf_enabled_settings.CSRF_COOKIE_KEY
    assert cookie_key in response.cookies
    signed_token = response.cookies.get(cookie_key)
    assert isinstance(signed_token, str)
    assert signed_token and "." in signed_token


def test_refresh_without_csrf_header_returns_403(csrf_client, monkeypatch):
    """POST /auth/refresh without CSRF header must be rejected with 403."""
    import app.api.v1.auth as auth_module

    async def override_get_db():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={
                "type": "refresh",
                "sub": "1",
                "user_id": 5,
                "institutional_id": "654321",
                "provider": UserProvider.TEST,
                "email": "test@example.com",
            }
        ),
    )

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        # Ensure signed cookie exists, but omit header on purpose.
        csrf_client.get("/api/v1/auth/csrf")
        response = csrf_client.post(
            "/api/v1/auth/refresh", cookies={"refresh_token": "token"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"] == "csrf_validation_failed"


def test_refresh_with_valid_csrf_header_and_cookie_succeeds(csrf_client, monkeypatch):
    """POST /auth/refresh with valid CSRF header and signed cookie must succeed."""
    import app.api.v1.auth as auth_module

    async def override_get_db():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(
            return_value={
                "type": "refresh",
                "sub": "1",
                "user_id": 5,
                "institutional_id": "654321",
                "provider": UserProvider.TEST,
                "email": "test@example.com",
            }
        ),
    )
    mock_user = MagicMock(id=5, email="test@example.com", institutional_id="654321")
    monkeypatch.setattr(
        auth_module.UserService,
        "get_by_institutional_id_and_provider",
        AsyncMock(return_value=mock_user),
    )

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        csrf_resp = csrf_client.get("/api/v1/auth/csrf")
        csrf_token = csrf_resp.json()["csrf_token"]
        response = csrf_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "token"},
            headers={"X-CSRF": csrf_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["message"] == "Token refreshed successfully"


def test_logout_without_csrf_header_returns_403(csrf_client):
    """POST /auth/logout without CSRF header must be rejected with 403."""
    csrf_client.get("/api/v1/auth/csrf")
    response = csrf_client.post("/api/v1/auth/logout", cookies={"auth_token": "token"})

    assert response.status_code == 403
    assert response.json()["error"] == "csrf_validation_failed"


def test_logout_with_valid_csrf_header_and_cookie_succeeds(csrf_client, monkeypatch):
    """POST /auth/logout with valid CSRF header and signed cookie must succeed."""
    import app.api.v1.auth as auth_module

    async def override_get_db():
        db = MagicMock()
        db.commit = AsyncMock()
        yield db

    monkeypatch.setattr(
        auth_module,
        "decode_jwt",
        MagicMock(return_value={"user_id": 7, "email": "test@example.com"}),
    )
    mock_user = MagicMock(id=7, institutional_id="987654")
    monkeypatch.setattr(
        auth_module.UserService, "get_by_id", AsyncMock(return_value=mock_user)
    )

    app.dependency_overrides[auth_module.get_db] = override_get_db
    try:
        csrf_resp = csrf_client.get("/api/v1/auth/csrf")
        csrf_token = csrf_resp.json()["csrf_token"]
        response = csrf_client.post(
            "/api/v1/auth/logout",
            cookies={"auth_token": "token"},
            headers={"X-CSRF": csrf_token},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
