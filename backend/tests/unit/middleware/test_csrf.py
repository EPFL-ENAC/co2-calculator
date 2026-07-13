"""CSRF middleware tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app

settings = get_settings()


@pytest.mark.asyncio
async def test_csrf_disabled_by_default():
    """CSRF validation is disabled when CSRF_ORIGIN_CHECK_ENABLED=false."""
    assert settings.CSRF_ORIGIN_CHECK_ENABLED is False

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # POST without Origin should pass when CSRF is disabled
        response = await client.post("/api/v1/session", json={})
        # Should not be blocked by CSRF (may fail for other reasons)
        assert response.status_code != 403


@pytest.mark.asyncio
async def test_csrf_get_requests_pass_without_origin():
    """GET requests pass through without Origin header validation."""
    # Temporarily enable CSRF
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/session")
            # GET should not be blocked (may return 401/404 for other reasons)
            assert response.status_code != 403
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_post_with_correct_origin_passes():
    """POST requests with correct Origin header pass validation."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/session",
                json={},
                headers={"origin": "https://example.com"},
            )
            # Should not be blocked by CSRF (may fail for other reasons)
            assert response.status_code != 403
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_post_without_origin_fails():
    """POST requests without Origin header are rejected when CSRF is enabled."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/session", json={})
            assert response.status_code == 403
            assert "CSRF validation failed: missing Origin header" in response.text
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_post_with_wrong_origin_fails():
    """POST requests with wrong Origin header are rejected."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/session",
                json={},
                headers={"origin": "https://malicious.com"},
            )
            assert response.status_code == 403
            assert "CSRF validation failed: Origin not trusted" in response.text
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_put_patch_delete_without_origin_fail():
    """PUT, PATCH, DELETE requests without Origin are rejected."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # PUT
            response = await client.put("/api/v1/session", json={})
            assert response.status_code == 403

            # PATCH
            response = await client.patch("/api/v1/session", json={})
            assert response.status_code == 403

            # DELETE
            response = await client.delete("/api/v1/session")
            assert response.status_code == 403
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_non_api_paths_bypassed():
    """Non /api/v1/** paths bypass CSRF validation."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # POST to non-API path without Origin should not be blocked by CSRF
            response = await client.post("/healthz", json={})
            # Should not be 403 from CSRF (may return 405 for other reasons)
            assert response.status_code != 403
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin


@pytest.mark.asyncio
async def test_csrf_oauth_callback_bypassed():
    """OAuth callback endpoint bypasses CSRF validation."""
    original_enabled = settings.CSRF_ORIGIN_CHECK_ENABLED
    original_origin = settings.CSRF_TRUSTED_ORIGIN
    settings.CSRF_ORIGIN_CHECK_ENABLED = True
    settings.CSRF_TRUSTED_ORIGIN = "https://example.com"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # POST to /auth/callback without Origin should not be blocked
            response = await client.post("/api/v1/auth/callback", json={})
            # Should not be 403 from CSRF (may return 400/401 for other reasons)
            assert response.status_code != 403
    finally:
        settings.CSRF_ORIGIN_CHECK_ENABLED = original_enabled
        settings.CSRF_TRUSTED_ORIGIN = original_origin
