"""Same-origin Matomo tracker proxy (#2649).

Public on purpose: the tracker loads on the login page too, before any session
exists. ``include_in_schema=False`` keeps browser-only endpoints out of
/api/docs and the generated frontend client — nothing calls them through the ky
client; a ``<script>`` tag and the tracker's own XHR do.
"""

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.logging import get_logger
from app.services.analytics_proxy_service import (
    MAX_HIT_BODY_BYTES,
    SCRIPT_CACHE_TTL_SECONDS,
    AnalyticsProxyService,
    TrackingHit,
)
from app.utils.request_context import extract_ip_address

logger = get_logger(__name__)

router = APIRouter(include_in_schema=False)


@router.get("/js")
async def tracker_script() -> Response:
    """Serve Matomo's tracker from our own origin, under a neutral path."""
    try:
        script = await AnalyticsProxyService().fetch_script()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)
        ) from e
    except httpx.HTTPError as e:
        logger.warning("Matomo tracker fetch failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Matomo tracker is unreachable",
        ) from e
    return Response(
        content=script.body,
        media_type=script.content_type,
        headers={"Cache-Control": f"public, max-age={SCRIPT_CACHE_TTL_SECONDS}"},
    )


@router.api_route("/track", methods=["GET", "POST"])
async def track(request: Request) -> Response:
    """Forward one tracking hit to Matomo, carrying the real client IP."""
    body = await request.body() if request.method == "POST" else None
    if body is not None and len(body) > MAX_HIT_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Tracking payload too large",
        )

    hit = TrackingHit(
        params=dict(request.query_params),
        body=body,
        content_type=request.headers.get("content-type"),
        user_agent=request.headers.get("user-agent"),
        accept_language=request.headers.get("accept-language"),
        client_ip=extract_ip_address(request),
    )
    try:
        upstream = await AnalyticsProxyService().forward_hit(hit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except httpx.HTTPError as e:
        logger.warning("Matomo tracking hit failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Matomo is unreachable",
        ) from e

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )
