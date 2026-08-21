"""Tests for the cross-pod taxonomy-cache invalidation broadcast (#2258
follow-up).

Uses the real ``db_session`` (in-memory SQLite) fixture to exercise the
``pods`` table query end to end, and monkeypatches ``httpx.AsyncClient.post``
so no real network call happens.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.taxonomy_cache_broadcast import (
    INTERNAL_CACHE_CLEAR_PATH,
    broadcast_taxonomy_cache_clear,
)
from app.models.pod import Pod
from app.tasks._pod_id import POD_ID


async def _add_pod(
    db_session,
    pod_id: str,
    *,
    pod_ip: str | None,
    heartbeat_age_seconds: float = 0.0,
) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Pod(
            pod_id=pod_id,
            pod_ip=pod_ip,
            started_at=now,
            last_heartbeat_at=now - timedelta(seconds=heartbeat_age_seconds),
        )
    )
    await db_session.flush()


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_broadcasts_to_every_other_live_pod_but_not_itself(
    db_session, monkeypatch
):
    await _add_pod(db_session, POD_ID, pod_ip="10.0.0.1")
    await _add_pod(db_session, "other-pod-a", pod_ip="10.0.0.2")
    await _add_pod(db_session, "other-pod-b", pod_ip="10.0.0.3")

    calls: list[str] = []

    async def fake_post(self, url, *args, **kwargs):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await broadcast_taxonomy_cache_clear(db_session)

    assert sorted(calls) == [
        f"http://10.0.0.2:8000{INTERNAL_CACHE_CLEAR_PATH}",
        f"http://10.0.0.3:8000{INTERNAL_CACHE_CLEAR_PATH}",
    ]


@pytest.mark.asyncio
async def test_skips_a_stale_pod(db_session, monkeypatch):
    """A pod whose heartbeat is older than the 2x-interval live window
    (see ``GET /v1/sync/workers``) is presumed dead, not just a broadcast
    target that happens to be unreachable.
    """
    await _add_pod(db_session, POD_ID, pod_ip="10.0.0.1")
    await _add_pod(db_session, "dead-pod", pod_ip="10.0.0.9", heartbeat_age_seconds=999)

    calls: list[str] = []

    async def fake_post(self, url, *args, **kwargs):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await broadcast_taxonomy_cache_clear(db_session)

    assert calls == []


@pytest.mark.asyncio
async def test_skips_a_pod_with_no_known_ip(db_session, monkeypatch):
    """Local dev / non-Kubernetes pods never set POD_IP — must never be
    dialled with a literal ``None`` host.
    """
    await _add_pod(db_session, POD_ID, pod_ip="10.0.0.1")
    await _add_pod(db_session, "no-ip-pod", pod_ip=None)

    async def fake_post(self, url, *args, **kwargs):
        raise AssertionError(f"should not have POSTed to {url}")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await broadcast_taxonomy_cache_clear(db_session)


@pytest.mark.asyncio
async def test_one_pod_failure_does_not_stop_the_others_or_raise(
    db_session, monkeypatch
):
    await _add_pod(db_session, POD_ID, pod_ip="10.0.0.1")
    await _add_pod(db_session, "flaky-pod", pod_ip="10.0.0.2")
    await _add_pod(db_session, "healthy-pod", pod_ip="10.0.0.3")

    calls: list[str] = []

    async def fake_post(self, url, *args, **kwargs):
        calls.append(url)
        if "10.0.0.2" in url:
            raise httpx.ConnectError("connection refused", request=None)
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Must not raise even though one of the two pods fails.
    await broadcast_taxonomy_cache_clear(db_session)

    assert sorted(calls) == [
        f"http://10.0.0.2:8000{INTERNAL_CACHE_CLEAR_PATH}",
        f"http://10.0.0.3:8000{INTERNAL_CACHE_CLEAR_PATH}",
    ]


@pytest.mark.asyncio
async def test_no_other_live_pods_is_a_no_op(db_session, monkeypatch):
    await _add_pod(db_session, POD_ID, pod_ip="10.0.0.1")

    post_mock = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", post_mock)

    await broadcast_taxonomy_cache_clear(db_session)

    post_mock.assert_not_awaited()
