"""Cross-pod invalidation broadcast for the taxonomy cache (#2258 follow-up).

``factor_taxonomy_cache.taxonomy_cache.clear()`` is exact and immediate
*within one process*, but ingestion runs in a separate worker deployment
from the API pods serving ``GET /v1/taxonomies/*`` (see that module's
docstring) — a local ``clear()`` never reaches them. Worst case was ~120s
of staleness (60s cache TTL + 60s ``Cache-Control`` header) before this
module existed.

This closes that gap actively: after a write clears its own process'
cache, it also POSTs to every OTHER live pod's internal cache-clear
endpoint (``app.api.internal``), read from the ``pods`` heartbeat table
(``app.tasks._pod_heartbeat``). Best-effort by design — a short per-call
timeout and ``asyncio.gather(..., return_exceptions=True)`` mean one dead
or slow pod can never make a factors write hang, and a broadcast that
misses a pod (network blip, pod mid-restart) is caught by the 60s TTL,
which stays in place as the fallback, not a replacement.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.pod import Pod
from app.tasks._pod_id import POD_ID
from app.utils.datetime_utc import as_utc

logger = get_logger(__name__)

# Bounds one write's added latency to ~one round trip no matter how many
# pods are live — see module docstring. The TTL is the fallback for
# whatever a pod this doesn't reach in time.
BROADCAST_TIMEOUT_SECONDS = 0.2

INTERNAL_CACHE_CLEAR_PATH = "/internal/cache/taxonomy/clear"


async def _live_other_pods(session: AsyncSession) -> list[Pod]:
    """Every other pod with a known IP, heartbeating within the same
    2x-interval live window the workers view uses (``GET /v1/sync/workers``).
    """
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(
        seconds=2 * settings.POD_HEARTBEAT_INTERVAL_SECONDS
    )
    result = await session.execute(select(Pod).where(col(Pod.pod_id) != POD_ID))
    return [
        pod
        for pod in result.scalars().all()
        if pod.pod_ip is not None and as_utc(pod.last_heartbeat_at) >= cutoff
    ]


async def _clear_remote(client: httpx.AsyncClient, pod: Pod) -> None:
    """POST to one pod's internal cache-clear endpoint.

    Best-effort: any failure (timeout, connection refused, non-2xx) is
    logged and swallowed, never raised — see module docstring.
    """
    settings = get_settings()
    url = f"http://{pod.pod_ip}:{settings.PORT}{INTERNAL_CACHE_CLEAR_PATH}"
    try:
        response = await client.post(url)
        response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "taxonomy cache broadcast: pod %s (%s) unreachable: %s",
            pod.pod_id,
            pod.pod_ip,
            exc,
        )


async def broadcast_taxonomy_cache_clear(session: AsyncSession) -> None:
    """Best-effort fan-out of a taxonomy-cache clear to every other live pod.

    Call this right after the local ``taxonomy_cache.clear()`` at a
    ``FactorRepository`` write site. Never raises — a broadcast failure
    must never fail the write itself.
    """
    live_others = await _live_other_pods(session)
    if not live_others:
        return

    async with httpx.AsyncClient(timeout=BROADCAST_TIMEOUT_SECONDS) as client:
        await asyncio.gather(
            *(_clear_remote(client, pod) for pod in live_others),
            return_exceptions=True,
        )
