"""Tests for the internal taxonomy cache-clear endpoint (#2258 follow-up).

Calls the route function directly (see ``test_active_pipelines_endpoint.py``
for the established pattern) rather than through a TestClient, since the
gate depends on ``request.client.host`` and the ``pods`` table.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.internal import _caller_is_live_pod, clear_taxonomy_cache
from app.core.factor_taxonomy_cache import taxonomy_cache
from app.models.pod import Pod


def _fake_request(host: str | None) -> SimpleNamespace:
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(client=client)


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    taxonomy_cache.clear()
    yield
    taxonomy_cache.clear()


@pytest.mark.asyncio
async def test_clears_local_cache_when_called_from_a_live_pod(db_session):
    taxonomy_cache.set(("stale-key",), "stale-tree")
    now = datetime.now(UTC)
    db_session.add(
        Pod(
            pod_id="other-pod", pod_ip="10.0.0.2", started_at=now, last_heartbeat_at=now
        )
    )
    await db_session.flush()

    await clear_taxonomy_cache(_fake_request("10.0.0.2"), db=db_session)

    assert taxonomy_cache.get(("stale-key",)) is None


@pytest.mark.asyncio
async def test_rejects_a_caller_whose_ip_is_not_a_live_pod(db_session):
    """A public request that reaches this path via ``/api/internal/...``
    (see module docstring — the OpenShift Route match is a prefix match)
    must not be able to clear the cache on demand.
    """
    taxonomy_cache.set(("stale-key",), "stale-tree")

    with pytest.raises(HTTPException) as exc:
        await clear_taxonomy_cache(_fake_request("203.0.113.5"), db=db_session)

    assert exc.value.status_code == 403
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"


@pytest.mark.asyncio
async def test_rejects_a_request_with_no_client_info(db_session):
    with pytest.raises(HTTPException) as exc:
        await clear_taxonomy_cache(_fake_request(None), db=db_session)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_rejects_a_stale_pods_ip(db_session):
    """The IP once belonged to a live pod, but its heartbeat is long gone —
    e.g. the pod was rescheduled and that IP was reassigned elsewhere.
    """
    old = datetime(2020, 1, 1, tzinfo=UTC)
    db_session.add(
        Pod(pod_id="gone-pod", pod_ip="10.0.0.2", started_at=old, last_heartbeat_at=old)
    )
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await clear_taxonomy_cache(_fake_request("10.0.0.2"), db=db_session)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_caller_is_live_pod_helper_used_directly():
    """Exercises the gate helper standalone (MagicMock db, no real query)
    to pin its no-host short-circuit.
    """
    assert await _caller_is_live_pod(MagicMock(), None) is False
