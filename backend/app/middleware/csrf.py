"""CSRF protection middleware: Origin header validation for state-changing requests."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.CSRF_ORIGIN_CHECK_ENABLED:
            return await call_next(request)

        # Only protect state-changing methods
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await call_next(request)

        # Only protect /api/v1/** paths
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        # Skip OAuth endpoints (they set cookies via redirect)
        if "/auth/callback" in request.url.path or "/auth/login" in request.url.path:
            return await call_next(request)

        # Require Origin header
        origin = request.headers.get("origin")
        if not origin:
            return Response(
                content="CSRF validation failed: missing Origin header",
                status_code=403,
            )

        # Validate Origin matches trusted origin exactly
        if origin != settings.CSRF_TRUSTED_ORIGIN:
            return Response(
                content="CSRF validation failed: Origin not trusted",
                status_code=403,
            )

        return await call_next(request)
