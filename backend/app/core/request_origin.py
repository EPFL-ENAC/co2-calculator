"""Fail-closed request-origin check for cookie-authenticated writes.

See ``docs/src/implementation-plans/89-security-in-depth.md``.

All authentication in this app is cookie-based (``auth_token`` /
``refresh_token``, ``SameSite=Lax``, host-only). ``SameSite`` is evaluated
against the *registrable domain*, so on a shared institutional domain like
``epfl.ch`` every sibling application is "same-site" to us and ``Lax`` will
happily attach the auth cookie to their state-changing requests. This
middleware is the control that actually distinguishes *us* from a sibling.

It is deliberately *not* a CORS policy: CORS is disabled on this instance
and stays disabled — preflights already block every JSON-body and
``PUT``/``PATCH``/``DELETE`` forgery. This closes what is left: ``POST``
requests whose body type is CORS-simple (``multipart/form-data``, or no body
at all), which reach the app without a preflight.

Written as raw ASGI rather than ``BaseHTTPMiddleware`` so it cannot interfere
with the streaming responses the pipeline SSE endpoint depends on.
"""

from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Methods that must not carry side effects. Audited (#89): the only
# state-changing GET in the app is the OAuth callback, which protects itself
# with the OAuth `state` parameter.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Presence of any of these is what makes a request carry ambient authority,
# and therefore what makes it forgeable. `session` is Starlette's OAuth-flow
# cookie — short-lived, but it authorizes the callback, so it counts.
AUTH_COOKIE_NAMES = ("auth_token", "refresh_token", "session")

# `Sec-Fetch-Site` values that identify the request as genuinely ours.
# `none` is a user-initiated navigation (typed URL, bookmark); `same-site` is
# excluded on purpose — a sibling subdomain is exactly the attacker here.
TRUSTED_FETCH_SITES = frozenset({"same-origin", "none"})

# Attacker-controlled header values reach the log; bound them.
_MAX_LOGGED_VALUE = 256


def _safe_for_log(value: str) -> str:
    """Bound and flatten an attacker-controlled header value."""
    stripped = "".join(c for c in value if c.isprintable())
    return stripped[:_MAX_LOGGED_VALUE]


def _normalize_origin(value: str) -> str | None:
    """Reduce a URL or Origin to ``scheme://host[:port]``, or None if it isn't one.

    Returns None for anything without both a scheme and a host — which is what
    makes the literal ``Origin: null`` (an opaque origin, sent by sandboxed
    iframes and some redirects) fall through to a rejection rather than
    accidentally matching an entry.
    """
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.hostname:
        return None

    scheme = parts.scheme.lower()
    host = parts.hostname.lower()
    try:
        port = parts.port
    except ValueError:
        return None

    default_port = {"http": 80, "https": 443}.get(scheme)
    if port is None or port == default_port:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def build_allowed_origins(settings: Settings) -> frozenset[str]:
    """The origins a cookie-authenticated write may come from.

    ``FRONTEND_URL`` is the real answer in every environment; the extra
    origins exist only so a genuine second host (a migration, say) doesn't
    need a code change. An unparseable entry is dropped rather than
    normalized into something permissive.
    """
    candidates = [settings.FRONTEND_URL, *settings.csrf_additional_origins]
    return frozenset(
        normalized
        for normalized in (_normalize_origin(c) for c in candidates)
        if normalized is not None
    )


def check_request_origin(
    request: Request, allowed_origins: frozenset[str]
) -> str | None:
    """Return a rejection reason, or None when the request may proceed.

    First match wins, in order.
    """
    if request.method in SAFE_METHODS:
        return None

    # CSRF rides ambient credentials. A request with no auth cookie has no
    # victim's authority to borrow, so it is not a CSRF vector — it falls
    # through to normal authentication and 401s there. A request carrying
    # both a cookie and a bearer token is still checked: the cookie is the
    # part the browser attaches on the attacker's behalf.
    if not any(name in request.cookies for name in AUTH_COOKIE_NAMES):
        return None

    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        if fetch_site.lower() in TRUSTED_FETCH_SITES:
            return None
        return f"sec-fetch-site={_safe_for_log(fetch_site)}"

    # Fallback only. Note for local dev: Quasar's proxy sets `changeOrigin`,
    # so `Origin` arrives rewritten to the proxy target rather than the page's
    # own origin. Harmless in practice — every browser we support sends
    # `Sec-Fetch-Site` and returns above — but it is why the header order
    # matters here.
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value is None:
            continue
        if _normalize_origin(value) in allowed_origins:
            return None
        return f"{header}={_safe_for_log(value)}"

    return "no Sec-Fetch-Site, Origin or Referer"


class RequestOriginMiddleware:
    """Reject cookie-authenticated writes that did not come from our own origin."""

    def __init__(
        self,
        app: ASGIApp,
        allowed_origins: frozenset[str] | None = None,
    ) -> None:
        self.app = app
        if allowed_origins is None:
            allowed_origins = build_allowed_origins(get_settings())
        self.allowed_origins = allowed_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Header- and cookie-only; the body is never read here, so an
        # oversized or streaming payload costs nothing to reject.
        request = Request(scope)
        reason = check_request_origin(request, self.allowed_origins)
        if reason is None:
            await self.app(scope, receive, send)
            return

        logger.warning(
            "Blocked cross-origin request",
            extra={
                "method": request.method,
                "route_path": request.url.path,
                "reason": reason,
                "csrf_blocked": True,
            },
        )
        response = JSONResponse(
            status_code=403,
            content={"detail": "Request origin not allowed"},
        )
        await response(scope, receive, send)
