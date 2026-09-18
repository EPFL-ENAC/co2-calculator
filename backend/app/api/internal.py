"""Intra-cluster-only endpoints (#2258 follow-up).

Mounted directly on ``app.main``, outside ``settings.API_VERSION`` and never
proxied by the Route (``helm/templates/routes.yaml`` only proxies ``/api``,
``/docs`` and ``/``) — same trust boundary as ``/healthz``/``/ready``. Not
airtight alone (a Route ``path`` match is a *prefix* match), so every route
here also authenticates: shared secret (``app.core.internal_auth``) first,
then a live-pod IP check as a second factor. See the #2530 plan for why both.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_db
from app.core.factor_taxonomy_cache import taxonomy_cache
from app.core.internal_auth import INTERNAL_AUTH_HEADER, internal_auth_ok
from app.models.pod import Pod, is_live, live_cutoff

# include_in_schema=False: pod-to-pod only, never called by a browser. Keeping
# it out of the public schema stops it appearing in /api/docs and in the
# generated frontend client, where it would be noise at best and a hint at a
# cache-clearing endpoint at worst.
router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


async def _authorize(request: Request, db: AsyncSession) -> None:
    """Raise 403 unless the caller proves it is another pod of this deployment.

    Both factors from the module docstring, secret first so a caller that
    can't produce it never costs a DB round trip.
    """
    if not internal_auth_ok(request.headers.get(INTERNAL_AUTH_HEADER)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    client_host = request.client.host if request.client else None
    if not await _caller_is_live_pod(db, client_host):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def _caller_is_live_pod(db: AsyncSession, host: str | None) -> bool:
    """True when ``host`` matches a currently-live pod's IP.

    The only intended caller is another pod's
    ``broadcast_taxonomy_cache_clear`` — see module docstring for why
    this check exists at all.
    """
    if not host:
        return False
    cutoff = live_cutoff()
    result = await db.execute(select(Pod).where(col(Pod.pod_ip) == host))
    return any(is_live(pod, cutoff) for pod in result.scalars().all())


@router.post("/cache/taxonomy/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_taxonomy_cache(
    request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    """Clear this pod's local taxonomy cache.

    Called by ``broadcast_taxonomy_cache_clear`` on every OTHER live pod
    right after a factor write clears the caller's own cache — closes the
    cross-pod staleness window the TTL alone would otherwise leave open
    for as long as the cache's TTL (see ``app.core.factor_taxonomy_cache``,
    now sized for hit rate rather than staleness since this broadcast is
    the correctness mechanism, #2391).
    """
    await _authorize(request, db)
    taxonomy_cache.clear()
