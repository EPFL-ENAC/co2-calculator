from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.core.config as config
from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
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
        MagicMock(return_value={"type": "refresh", "sub": "1", "user_id": 5}),
    )
    mock_user = MagicMock(id=5, email="test@example.com", provider_code="654321")
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
    mock_user = MagicMock(id=7, provider_code="987654")
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
