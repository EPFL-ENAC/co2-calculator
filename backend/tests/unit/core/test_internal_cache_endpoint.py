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
from app.core.config import get_settings
from app.core.factor_taxonomy_cache import taxonomy_cache
from app.core.internal_auth import (
    INTERNAL_AUTH_HEADER,
    internal_auth_ok,
    internal_auth_token,
)
from app.models.pod import Pod

_UNSET = object()


def _fake_request(host: str | None, *, auth: object = _UNSET) -> SimpleNamespace:
    """A request from ``host``, carrying a valid internal token by default.

    Pass ``auth=None`` for a caller that sends no token at all — the shape of
    a spoofed request, since the header is the one thing an outside caller
    cannot produce (#2530).
    """
    client = SimpleNamespace(host=host) if host is not None else None
    token = internal_auth_token() if auth is _UNSET else auth
    headers = {} if token is None else {INTERNAL_AUTH_HEADER: token}
    return SimpleNamespace(client=client, headers=headers)


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    taxonomy_cache.clear()
    yield
    taxonomy_cache.clear()


@pytest.mark.asyncio
async def test_clears_local_cache_when_called_from_a_live_pod(db_session):
    """A genuine in-cluster caller: live pod address *and* the shared secret
    ``_clear_remote`` sends. Both factors, or the request is refused.
    """
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
async def test_rejects_a_caller_whose_pod_ip_is_spoofed_via_proxy_headers(db_session):
    """The attack #2530 found: the deployed FORWARDED_ALLOW_IPS trusts the
    whole pod overlay subnet, so any in-cluster workload can put a live pod's
    address in ``request.client.host`` with one X-Forwarded-For header — see
    ``test_audit_helpers.py::test_a_caller_inside_the_pod_subnet_can_still_
    choose_its_own_ip``. The IP allowlist alone therefore proves nothing;
    what it cannot forge is the shared secret.
    """
    taxonomy_cache.set(("stale-key",), "stale-tree")
    now = datetime.now(UTC)
    db_session.add(
        Pod(
            pod_id="other-pod",
            pod_ip="10.20.4.4",
            started_at=now,
            last_heartbeat_at=now,
        )
    )
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await clear_taxonomy_cache(_fake_request("10.20.4.4", auth=None), db=db_session)

    assert exc.value.status_code == 403
    assert taxonomy_cache.get(("stale-key",)) == "stale-tree"


@pytest.mark.asyncio
async def test_rejects_a_wrong_internal_token(db_session):
    now = datetime.now(UTC)
    db_session.add(
        Pod(
            pod_id="other-pod",
            pod_ip="10.20.4.4",
            started_at=now,
            last_heartbeat_at=now,
        )
    )
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await clear_taxonomy_cache(
            _fake_request("10.20.4.4", auth="not-the-token"), db=db_session
        )

    assert exc.value.status_code == 403


def test_internal_auth_fails_closed_without_a_signing_key(monkeypatch):
    """An unset JWT_HMAC_KEY must reject, never derive a token from "" that
    anyone could compute. Outside local dev the key is required at boot.
    """
    token = internal_auth_token()
    monkeypatch.setattr(get_settings(), "JWT_HMAC_KEY", "")
    assert internal_auth_ok(token) is False


@pytest.mark.asyncio
async def test_caller_is_live_pod_helper_used_directly():
    """Exercises the gate helper standalone (MagicMock db, no real query)
    to pin its no-host short-circuit.
    """
    assert await _caller_is_live_pod(MagicMock(), None) is False


def test_non_ascii_token_is_rejected_not_a_crash():
    """A latin-1 header byte must fail closed, not raise.

    Starlette decodes headers as latin-1, and hmac.compare_digest raises
    TypeError on a str holding a codepoint above U+007F. Unhandled, that
    turned an unauthenticated request on a publicly reachable route into a
    500 instead of a 403 (review finding on PR #2542).
    """
    from app.core.internal_auth import internal_auth_ok

    assert internal_auth_ok("café") is False
    assert internal_auth_ok("\xff" * 64) is False
