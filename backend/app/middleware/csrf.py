"""CSRF protection middleware: Origin header validation for state-changing requests."""

from typing import Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

settings = get_settings()


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Validate Origin header on state-changing requests to /api/v1/**.

    Per OWASP: cookie-based auth requires CSRF protection for POST/PUT/PATCH/DELETE.
    SameSite=Lax is the baseline; this adds Origin validation as defense-in-depth.

    - Only applies to POST, PUT, PATCH, DELETE under /api/v1/**
    - Requires Origin header to match CSRF_TRUSTED_ORIGIN exactly
    - Fails closed: missing/wrong Origin = 403 Forbidden
    - Skips GET, HEAD, OPTIONS and OAuth endpoints
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.CSRF_ORIGIN_CHECK_ENABLED:
            return await call_next(request)

        # Only protect state-changing methods
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)

        # Only protect /api/v1/** paths
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        # Skip OAuth endpoints (they set cookies via redirect)
        if (
            request.url.path.startswith("/api/v1/auth/callback")
            or request.url.path.startswith("/api/v1/auth/login")
        ):
            return await call_next(request)

        # Require Origin or Referer header
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if not origin and not referer:
            return JSONResponse(
                content={"detail": "CSRF validation failed: missing Origin and Referer headers"},
                status_code=403,
            )

        # Use Origin if present, otherwise fall back to Referer
        request_origin = origin if origin else referer

        # Extract scheme + host from Referer if it's a full URL
        if not origin and referer:
            parsed = urlparse(referer)
            request_origin = f"{parsed.scheme}://{parsed.netloc}"

        # Validate origin matches trusted origin exactly
        if request_origin != settings.CSRF_TRUSTED_ORIGIN:
            return JSONResponse(
                content={"detail": "CSRF validation failed: origin not trusted"},
                status_code=403,
            )

        return await call_next(request)
