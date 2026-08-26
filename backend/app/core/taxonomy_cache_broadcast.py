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

import httpx
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.factor_taxonomy_cache import taxonomy_cache
from app.core.logging import get_logger
from app.models.pod import Pod, is_live, live_cutoff
from app.tasks._background import fire_and_forget
from app.tasks._pod_id import POD_ID

logger = get_logger(__name__)

# ``Session.info`` key marking "a post-commit clear is already queued for
# this session" — collapses N writes in one transaction into one clear.
_PENDING_INFO_KEY = "taxonomy_cache_invalidation_pending"

# Bounds one write's added latency to ~one round trip no matter how many
# pods are live — see module docstring. The TTL is the fallback for
# whatever a pod this doesn't reach in time.
BROADCAST_TIMEOUT_SECONDS = 0.2

INTERNAL_CACHE_CLEAR_PATH = "/internal/cache/taxonomy/clear"


async def _live_other_pods(session: AsyncSession) -> list[Pod]:
    """Every other pod with a known IP, heartbeating within the same
    2x-interval live window the workers view uses (``GET /v1/sync/workers``).
    """
    cutoff = live_cutoff()
    result = await session.execute(select(Pod).where(col(Pod.pod_id) != POD_ID))
    return [
        pod
        for pod in result.scalars().all()
        if pod.pod_ip is not None and is_live(pod, cutoff)
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


async def _post_clear_to(live_others: list[Pod]) -> None:
    """POST the internal cache-clear endpoint to every pod in ``live_others``."""
    if not live_others:
        return
    async with httpx.AsyncClient(timeout=BROADCAST_TIMEOUT_SECONDS) as client:
        await asyncio.gather(
            *(_clear_remote(client, pod) for pod in live_others),
            return_exceptions=True,
        )


async def broadcast_taxonomy_cache_clear(session: AsyncSession) -> None:
    """Best-effort fan-out of a taxonomy-cache clear to every other live pod.

    Not called from production write paths — ``schedule_taxonomy_cache_
    invalidation`` below inlines the same ``_live_other_pods`` + ``_post_
    clear_to`` sequence itself, since it needs to snapshot live pods
    *before* commit but only fire the POSTs *after*. Kept as the tested
    unit for that pod-lookup + broadcast behavior in isolation (see
    ``test_taxonomy_cache_broadcast.py``); never raises — a broadcast
    failure must never fail a write.
    """
    await _post_clear_to(await _live_other_pods(session))


async def schedule_taxonomy_cache_invalidation(session: AsyncSession) -> None:
    """Clear the taxonomy cache (+ broadcast) once ``session`` actually
    commits — never at flush time.

    Clearing early is worse than not clearing at all: the write is
    still uncommitted, so a concurrent reader (this pod or another)
    still sees pre-write rows under READ COMMITTED and would repopulate
    the now-empty cache with stale data for a fresh TTL. Registering a
    one-shot ``after_commit`` hook on the session's underlying sync
    ``Session`` guarantees the clear only ever fires once the write is
    durable and visible to every other transaction.

    Who's live is read up front (a plain, unrelated-table lookup that's
    safe to run before commit — it doesn't depend on the pending write)
    so the deferred half needs no session of its own: only the actual
    clear + POSTs, which must reflect the write, wait for commit.

    ``FactorRepository`` may call this several times inside one
    transaction (e.g. an upsert followed by ``delete_stale_for_year``);
    the ``info`` flag collapses those into a single post-commit clear.
    A rollback never fires ``after_commit`` at all, so a rolled-back
    write correctly triggers no invalidation — the still-registered
    hook just waits for whatever commit eventually happens on this
    session, if any.

    Known latent gap: ``info`` and the ``live_others`` snapshot below
    both survive a rollback untouched (verified empirically — SQLAlchemy
    resets neither on rollback), and the ``once=True`` listener stays
    registered rather than firing. A session that rolled back a write
    here and then committed a *later*, unrelated write on the same
    session would broadcast to the first write's now-possibly-stale
    pod list. No current caller reuses a session this way (factor CSV
    ingestion rolls back and re-raises, ending that session's writes —
    see ``base_factor_csv_provider.py``), so this is parked rather than
    fixed: distinguishing "rolled back" from the flush-level rollbacks
    SQLAlchemy does internally needs ``after_rollback`` vs ``after_soft_
    rollback``, and picking the wrong one risks a double broadcast,
    which is worse than the staleness this would close.
    """
    sync_session = session.sync_session
    if sync_session.info.get(_PENDING_INFO_KEY):
        return
    sync_session.info[_PENDING_INFO_KEY] = True

    live_others = await _live_other_pods(session)

    def _on_commit(sync_sess: Session) -> None:
        sync_sess.info[_PENDING_INFO_KEY] = False
        taxonomy_cache.clear()
        # fire_and_forget, not app.tasks._chain's drain-after-commit queue:
        # that pattern exists to stop a child task from starting before its
        # parent transaction is visible, which an after_commit hook already
        # guarantees here by construction -- there's no separate drain point
        # an ordinary FastAPI route could call after its own commit.
        fire_and_forget(_post_clear_to(live_others), name="taxonomy-cache-broadcast")

    event.listen(sync_session, "after_commit", _on_commit, once=True)
