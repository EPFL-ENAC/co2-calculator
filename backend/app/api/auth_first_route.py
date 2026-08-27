"""Route class that runs the body-independent checks before FastAPI reads the body."""

from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from opentelemetry import trace

from app.core.config import get_settings
from app.core.security import decode_jwt

settings = get_settings()

# Coarse pre-filter, deliberately not the real limit: FILES_MAX_SIZE_MB is a
# *per-file* cap while Content-Length covers the whole multipart body, so a
# legitimate multi-file upload can exceed the per-file cap in total. This
# bounds the transfer at a generous multiple; the exact per-file check still
# runs after parsing.
MAX_UPLOAD_FILES = 20
MAX_REQUEST_BODY_BYTES = settings.FILES_MAX_SIZE_MB * 1024 * 1024 * MAX_UPLOAD_FILES

AUTH_COOKIE_NAME = "auth_token"


def _reject_unauthenticated(request: Request) -> None:
    """Require a correctly-signed, unexpired JWT cookie.

    Deliberately *not* a second implementation of authentication — it proves
    only that the caller holds a valid token, so there is no copy of the auth
    rules here to drift out of sync. The endpoint's own
    ``Depends(get_current_user)`` still enforces the access-token contract and
    loads the user, and its permission check still decides what that user may
    do.
    """
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    decode_jwt(token)


def _reject_oversized(request: Request) -> None:
    """Reject on the *declared* body size, before a byte is read.

    Best-effort by nature: a missing or malformed ``Content-Length`` (or a
    chunked upload, which has none) just means this check doesn't apply, never
    a failed upload. It is a cheap early exit, not the enforcement point.
    """
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        size = int(content_length)
    except ValueError:
        return
    # Lets slow-client-vs-large-file be told apart in traces (#2261).
    trace.get_current_span().set_attribute("http.request_content_length", size)
    if size > MAX_REQUEST_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Request body exceeds {MAX_REQUEST_BODY_BYTES} bytes",
        )


class AuthFirstRoute(APIRoute):
    """Reject unauthenticated and oversized requests before the body is read.

    For any route declaring a ``File``/``Form`` parameter, FastAPI reads the
    *entire* request body (``body = await request.form()`` in
    ``fastapi/routing.py``) before it resolves a single dependency. Dependency
    order in the signature makes no difference, so an unauthenticated caller
    could push an arbitrary payload through before the 401 (#2261).

    A route's handler runs *before* that parsing. Putting the two checks that
    don't need the body here closes the hole while endpoints keep ordinary,
    readable ``File(...)``/``Form(...)`` signatures and their automatically
    generated OpenAPI schema.

    Apply it to a whole router only when every route on it already requires
    authentication — it makes the auth cookie mandatory for all of them.
    """

    def get_route_handler(self):
        original_route_handler = super().get_route_handler()

        async def auth_first(request: Request) -> Response:
            _reject_unauthenticated(request)
            _reject_oversized(request)
            return await original_route_handler(request)

        return auth_first
