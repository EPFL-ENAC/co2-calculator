import pytest
from httpx import AsyncClient

import app.core.config as config


@pytest.mark.asyncio
async def test_login_redirect_uri_https(client: AsyncClient, monkeypatch):
    # Patch the authorize_redirect method to simulate OAuth provider redirect
    from starlette.responses import RedirectResponse

    import app.api.v1.auth as auth_module

    async def fake_authorize_redirect(request, redirect_uri):
        # Simulate a redirect to the provider with the correct redirect_uri
        return RedirectResponse(url=f"https://fake-oauth?redirect_uri={redirect_uri}")

    monkeypatch.setattr(
        auth_module.oauth.co2_oauth_provider,
        "authorize_redirect",
        fake_authorize_redirect,
    )

    settings = config.get_settings()
    prefix = settings.API_VERSION

    response = await client.get(
        f"{prefix}/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert (
        "redirect_uri=https%3A%2F%2F" in location or "redirect_uri=https://" in location
    )
