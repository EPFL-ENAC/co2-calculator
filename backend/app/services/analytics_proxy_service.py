"""Same-origin proxy for the Matomo tracker (#2649).

Content blockers match the tracker by filename — ``matomo.js`` and
``matomo.php`` are on the default EasyPrivacy/uBlock lists whatever host serves
them — so a direct call to the ENAC Matomo is dropped in a large share of
browsers (confirmed in the dev deployment). Serving both from our own origin
under neutral paths is Matomo's documented proxy setup, and it keeps the
upstream URL server-side, where the source of truth belongs.

Nothing here touches the database: the service owns the outbound HTTP and the
tracker-script cache, the route owns the status translation.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TRACKER_SCRIPT_FILE = "matomo.js"
TRACKER_ENDPOINT_FILE = "matomo.php"

UPSTREAM_TIMEOUT_SECONDS = 5.0
# The tracker changes only when Matomo is upgraded, so serve it from memory and
# let browsers cache it for the same window.
SCRIPT_CACHE_TTL_SECONDS = 3600
# A tracking hit is a few hundred bytes; the cap stops the endpoint being used
# as a general-purpose relay.
MAX_HIT_BODY_BYTES = 64 * 1024


@dataclass(frozen=True)
class TrackerScript:
    body: bytes
    content_type: str


@dataclass(frozen=True)
class TrackingHit:
    """One tracking request, as the browser sent it to us.

    Cookies and Authorization are absent by construction: our session cookie
    must never reach the analytics server. What is forwarded is what Matomo
    derives browser, OS and language from, plus the client IP.
    """

    params: dict[str, str]
    body: bytes | None
    content_type: str | None
    user_agent: str | None
    accept_language: str | None
    client_ip: str | None


def _new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=UPSTREAM_TIMEOUT_SECONDS)


_cached_script: TrackerScript | None = None
_cached_at: float = 0.0


class AnalyticsProxyService:
    """Fetches the Matomo tracker and forwards tracking hits upstream."""

    def __init__(
        self, client_factory: Callable[[], httpx.AsyncClient] = _new_client
    ) -> None:
        self._client_factory = client_factory

    def _upstream_url(self, filename: str) -> str:
        """Absolute upstream URL, or ValueError when MATOMO_URL is unusable.

        Loud rather than silently disabled: an operator who sets a bad URL
        should see 503s on the analytics path, not an app that quietly stops
        collecting.
        """
        base = get_settings().MATOMO_URL.strip()
        if not base:
            raise ValueError("MATOMO_URL is not configured")
        if urlparse(base).scheme != "https":
            raise ValueError("MATOMO_URL must use https")
        return f"{base.rstrip('/')}/{filename}"

    async def fetch_script(self) -> TrackerScript:
        """The tracker JS, from the in-process cache when it is still fresh."""
        global _cached_script, _cached_at
        if _cached_script and time.monotonic() - _cached_at < SCRIPT_CACHE_TTL_SECONDS:
            return _cached_script

        url = self._upstream_url(TRACKER_SCRIPT_FILE)
        async with self._client_factory() as client:
            response = await client.get(url)
        response.raise_for_status()

        _cached_script = TrackerScript(
            body=response.content,
            content_type=response.headers.get("content-type", "application/javascript"),
        )
        _cached_at = time.monotonic()
        return _cached_script

    async def forward_hit(self, hit: TrackingHit) -> httpx.Response:
        """Forward one tracking hit to Matomo and return its raw response."""
        if "token_auth" in hit.params:
            # An authenticated write (overriding the IP, backdating a hit) is
            # never something the browser tracker needs, and this endpoint is
            # unauthenticated — refuse rather than relay the privilege.
            raise ValueError("token_auth is not accepted by the tracking proxy")

        url = self._upstream_url(TRACKER_ENDPOINT_FILE)
        headers = _forward_headers(hit)
        async with self._client_factory() as client:
            if hit.body is None:
                return await client.get(url, params=hit.params, headers=headers)
            return await client.post(
                url, params=hit.params, content=hit.body, headers=headers
            )


def _forward_headers(hit: TrackingHit) -> dict[str, str]:
    """Only what Matomo needs to attribute the hit.

    X-Forwarded-For carries the real client IP. Matomo honours it only when its
    own config trusts the header (``proxy_client_headers``); without that,
    every hit is attributed to this pod's egress IP and — since we track
    cookieless, where the visitor id is derived from IP + user agent — the
    visitor counts collapse into one.
    """
    headers: dict[str, str] = {}
    if hit.client_ip:
        headers["X-Forwarded-For"] = hit.client_ip
    if hit.user_agent:
        headers["User-Agent"] = hit.user_agent
    if hit.accept_language:
        headers["Accept-Language"] = hit.accept_language
    if hit.content_type:
        headers["Content-Type"] = hit.content_type
    return headers
