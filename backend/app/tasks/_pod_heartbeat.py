"""In-process pod heartbeat writer (#1080 sprint-9).

Backs the workers view that lets operators answer "who's claiming
work right now" without `kubectl`.  Motivated by 2026-05-21: a dev
running a local branch against the stage DB silently collided with
the deployed stage app — two pods on different code paths, both
holding claims on ``data_ingestion_jobs``, no signal in any UI.

Lifecycle:

* On app startup the loop registers (INSERT-or-UPDATE) a ``pods``
  row keyed by ``POD_ID`` (``$HOSTNAME`` in Kubernetes, hostname
  locally — same value the runner already uses for ``locked_by``,
  so JOINs against ``data_ingestion_jobs.locked_by`` work natively).
* Every ``POD_HEARTBEAT_INTERVAL_SECONDS`` it refreshes
  ``last_heartbeat_at``.
* On graceful shutdown (lifespan teardown) the row is deleted so
  the workers view immediately drops the gone-pod.  Ungraceful
  shutdowns (pod kill / OOM) leave the row behind; the read
  endpoint filters by ``last_heartbeat_at > now() - 2 ×
  interval`` so dead pods drop off within ~1 minute.

Multi-pod safety: the upsert is idempotent (``ON CONFLICT
(pod_id) DO UPDATE``), so two replicas with the same POD_ID
(should never happen in K8s — pod names are unique) would just
overwrite each other's last_heartbeat_at without crashing.  Errors
are logged-and-skipped per tick so a transient DB hiccup doesn't
kill the heartbeat (mirrors ``_pipeline_reconciler``).
"""

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime

from opentelemetry.metrics import CallbackOptions, Observation, get_meter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal, engine
from app.tasks._pod_id import POD_ID, POD_IP

logger = get_logger(__name__)

# Total backends on the Postgres *server*, refreshed on each heartbeat tick.
# #2566: connections left behind by a pod that died ungracefully outlive the
# pod, so no pod-local pool gauge can ever see them -- this is the only
# in-app signal that does. Every pod reports the same server-wide number:
# aggregate with max(), never sum().
_server_connections: int | None = None


async def _upsert_pod_row(*, started_at: datetime) -> None:
    """Insert-or-update the current pod's row.  Bumps
    ``last_heartbeat_at`` to now; preserves ``started_at`` across
    upserts (the original startup time stays — useful for "pod
    uptime" in the UI).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        # Raw SQL because SQLModel doesn't expose a portable
        # ON CONFLICT path that works across Postgres and SQLite
        # (asyncpg dialect + SQLite differ in conflict-target
        # syntax).  Postgres is the production target; SQLite is
        # only exercised by unit tests and never hits this loop in
        # practice.  Bind parameters via ``text(...).bindparams``
        # would require importing ``bindparam`` — keep the raw
        # form with ``:name`` placeholders, which both dialects
        # accept.
        stmt = text(
            """
            INSERT INTO pods (
                pod_id, git_sha, app_version, pod_ip, started_at,
                last_heartbeat_at
            )
            VALUES (
                :pod_id, :git_sha, :app_version, :pod_ip, :started_at,
                :last_heartbeat_at
            )
            ON CONFLICT (pod_id) DO UPDATE SET
                git_sha = EXCLUDED.git_sha,
                app_version = EXCLUDED.app_version,
                pod_ip = EXCLUDED.pod_ip,
                last_heartbeat_at = EXCLUDED.last_heartbeat_at
            """
        )
        await session.execute(
            stmt,
            {
                "pod_id": POD_ID,
                "git_sha": settings.GIT_SHA,
                "app_version": settings.APP_VERSION,
                # Refreshed on every tick (unlike started_at) — a Deployment
                # (no stable network identity like a StatefulSet) can reuse
                # a POD_ID only by coincidence, and its IP changes across
                # restarts, so a stale value here would silently misdirect
                # every other pod's broadcast POST (#2258 follow-up).
                "pod_ip": POD_IP,
                # ``started_at`` is the loop's first-tick value;
                # the ON CONFLICT clause deliberately omits it so a
                # subsequent heartbeat doesn't reset it.
                "started_at": started_at,
                "last_heartbeat_at": now,
            },
        )
        await session.commit()


async def _delete_pod_row() -> None:
    """Drop the current pod's row on graceful shutdown so the
    workers view doesn't show a phantom 'live' pod between
    shutdown and the read filter's stale window.

    Best-effort: shutdown-time DB errors are logged-and-skipped
    (the read filter is the durable backstop).
    """
    try:
        async with SessionLocal() as session:
            await session.execute(
                text("DELETE FROM pods WHERE pod_id = :pod_id"),
                {"pod_id": POD_ID},
            )
            await session.commit()
    except Exception:
        logger.exception("pod heartbeat: shutdown delete failed for %s", POD_ID)


async def _refresh_server_connection_count() -> None:
    """Cache ``count(*)`` over ``pg_stat_activity`` for the OTel gauge.

    Postgres-only: sqlite (local, tests) has no such view, and the gauge
    reports nothing there rather than the loop failing every tick.
    """
    global _server_connections
    if engine.dialect.name != "postgresql":
        return
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT count(*) FROM pg_stat_activity"))
        _server_connections = result.scalar_one()


def _server_connections_callback(options: CallbackOptions) -> Iterable[Observation]:
    """Report the cached server-wide count; silent until the first tick."""
    if _server_connections is None:
        return
    yield Observation(_server_connections)


get_meter(__name__).create_observable_gauge(
    "db.server.connections",
    callbacks=[_server_connections_callback],
    unit="{connection}",
    description="Backends open on the Postgres server, all clients",
)


async def pod_heartbeat_loop() -> None:
    """Run the heartbeat writer on the configured cadence forever.

    Cancellation: ``asyncio.CancelledError`` propagates out of the
    sleep — the lifespan shutdown awaits this loop's cancellation
    and then calls ``_delete_pod_row`` to clean up.
    """
    settings = get_settings()
    interval = settings.POD_HEARTBEAT_INTERVAL_SECONDS
    started_at = datetime.now(UTC)
    # First tick BEFORE the sleep so the row is registered as soon
    # as the loop starts — operators get the new pod in the
    # workers view immediately, not ``interval`` seconds later.
    try:
        await _upsert_pod_row(started_at=started_at)
        await _refresh_server_connection_count()
        logger.info(
            "pod heartbeat: registered pod_id=%s git_sha=%s version=%s",
            POD_ID,
            settings.GIT_SHA,
            settings.APP_VERSION,
        )
    except Exception:
        logger.exception("pod heartbeat: initial registration failed")
    while True:
        try:
            await asyncio.sleep(interval)
            await _upsert_pod_row(started_at=started_at)
            await _refresh_server_connection_count()
        except asyncio.CancelledError:
            await _delete_pod_row()
            raise
        except Exception as exc:
            logger.warning(f"pod heartbeat iteration failed: {exc}", exc_info=True)
