"""Regression tests for #2566 — the lifespan must release its DB pool.

Incident: dev's Postgres (`max_connections=100`) filled with 53 backends
belonging to pods that no longer existed, and every request 500'd with
"remaining connection slots are reserved for roles with the SUPERUSER
attribute". The pods exited without closing their pool; behind the
cluster's SNAT the FIN never reached Postgres, which then held those
sockets until TCP keepalives expired — ~10-20 slots per rollout, for
hours.

`engine.dispose()` closes them while the pod still has a network. It is
the graceful half of the fix; role-level `tcp_keepalives_*` on the server
covers the ungraceful half (OOMKill, SIGKILL past the grace period).
"""

import pytest
from fastapi import FastAPI

from app.db import engine
from app.main import lifespan
from app.tasks import _pod_heartbeat


@pytest.fixture
def quiet_lifespan(monkeypatch):
    """Run the real lifespan with its background loops and table
    bootstrap off — this asserts teardown, not startup.

    ``RUN_BACKGROUND_POLLER``/``RUN_DB_HEALTH_POLLER`` are already off via
    conftest's autouse ``disable_poller``.
    """
    for flag in (
        "RUN_PIPELINE_RECONCILER",
        "RUN_POD_HEARTBEAT",
        "RUN_EVENT_LOOP_LAG_PROBE",
    ):
        monkeypatch.setattr(f"app.main.settings.{flag}", False)

    async def _no_init_db() -> None:
        return None

    # Imported inside the lifespan body, so patching the source module is
    # what takes effect.
    monkeypatch.setattr("app.db.init_db", _no_init_db)


async def test_lifespan_disposes_the_connection_pool(quiet_lifespan):
    """Fails without `await engine.dispose()`: `dispose()` swaps in a
    fresh pool object, so an unchanged identity means every socket the
    pod opened was still open when it exited.
    """
    pool_before = engine.pool

    async with lifespan(FastAPI()):
        pass

    assert engine.pool is not pool_before


async def test_server_connection_count_is_skipped_off_postgres():
    """`pg_stat_activity` doesn't exist on sqlite — the guard keeps the
    heartbeat loop from failing every tick locally and in tests.
    """
    if engine.dialect.name == "postgresql":
        pytest.skip("asserts the sqlite guard; this run's DB is Postgres")
    _pod_heartbeat._server_connections = None

    await _pod_heartbeat._refresh_server_connection_count()

    assert _pod_heartbeat._server_connections is None


def test_server_connections_gauge_is_silent_before_the_first_tick():
    """The observable gauge reports nothing rather than 0 — a pod that
    hasn't ticked yet must not drag a `max()` aggregation down.
    """
    _pod_heartbeat._server_connections = None

    assert list(_pod_heartbeat._server_connections_callback(None)) == []
