import pytest
from httpx import AsyncClient

import app.core.config as config


@pytest.mark.asyncio
async def test_login_redirect_uri_https(client: AsyncClient):
    # Simulate HTTPS via X-Forwarded-Proto header
    settings = config.get_settings()
    prefix = settings.API_VERSION

    response = await client.get(
        f"{prefix}/auth/login",
        headers={"X-Forwarded-Proto": "https"},
        follow_redirects=False,
    )
    # The response should be a redirect to the OAuth provider
    assert response.status_code in (302, 307)
    # The redirect location should contain https in the redirect_uri param
    location = response.headers["location"]
    assert (
        "redirect_uri=https%3A%2F%2F" in location or "redirect_uri=https://" in location
    )
