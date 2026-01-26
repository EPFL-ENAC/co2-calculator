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
