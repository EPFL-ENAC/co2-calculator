"""#2049 T7 — job_stream_by_id's SSE heartbeat.

The pipeline stream already emits an ``event: ping`` heartbeat every
~15s so a proxy idle-timeout doesn't cut a quiet connection; the job
stream never had one (the trace investigation found 16s gaps with zero
bytes sent). This pins that job_stream_by_id now emits the same
heartbeat, and mirrors pipeline_stream_by_id's shape: a real state
change resets the heartbeat clock instead of double-emitting.

Drives the generator directly (not via httpx) and monkeypatches
``asyncio.sleep`` to be instant, so the test doesn't wait out 15+ real
seconds -- same rationale as ``test_disconnect_releases_pool_slot`` in
the pipeline-stream PG integration test, minus the real Postgres
dependency: nothing here touches the DB, so a fake repository is enough.
"""

from unittest.mock import MagicMock

import pytest

import app.api.v1.data_sync as data_sync_module
from app.models.data_ingestion import IngestionState


class _FakeJob:
    """A job that never changes and never finishes -- isolates the test
    to heartbeat behavior, not the state-change or completion paths
    (those are covered elsewhere).
    """

    id = 1
    module_type_id = None  # _check_job_scope no-ops on this
    target_type = "module"
    year = 2025
    state = IngestionState.RUNNING
    result = None
    status_message = "running"
    meta = None


class _FakeRepo:
    def __init__(self, _session):
        pass

    async def get_job_by_id(self, _job_id):
        return _FakeJob()


class _FakeSessionCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_exc):
        return False


class _FakeRequest:
    """Disconnects after ``n_polls_before_disconnect`` polls."""

    def __init__(self, n_polls_before_disconnect: int):
        self._remaining = n_polls_before_disconnect
        self.calls = 0

    async def is_disconnected(self) -> bool:
        self.calls += 1
        if self._remaining <= 0:
            return True
        self._remaining -= 1
        return False


@pytest.mark.asyncio
async def test_job_stream_emits_heartbeat_on_quiet_connection(monkeypatch):
    monkeypatch.setattr(data_sync_module, "DataIngestionRepository", _FakeRepo)
    monkeypatch.setattr(
        data_sync_module.db_module, "SessionLocal", lambda: _FakeSessionCM()
    )

    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(data_sync_module.asyncio, "sleep", _instant_sleep)

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {"backoffice.configuration": ["view"]}

    # 14s heartbeat / 2s poll interval = one real state-change event
    # (poll 1, resets the clock) then several identical polls before
    # disconnecting -- enough for exactly one heartbeat to fire.
    request = _FakeRequest(n_polls_before_disconnect=9)

    response = await data_sync_module.job_stream_by_id(
        job_id=1, request=request, current_user=fake_user
    )

    events: list[str] = []
    async for chunk in response.body_iterator:
        events.append(chunk if isinstance(chunk, str) else chunk.decode())
        if len(events) > 15:  # safety valve, don't loop forever on a regression
            break

    assert any(e.startswith("event: ping") for e in events), (
        "No heartbeat emitted on a quiet connection -- job_stream_by_id "
        "regressed back to having no keepalive."
    )
    # First event is the real initial state (job just appeared as RUNNING).
    assert events[0].startswith("data: ")


@pytest.mark.asyncio
async def test_job_stream_heartbeat_fires_within_15s_not_16(monkeypatch):
    """#2049 T7-followup: the heartbeat must fire in <15s of quiet, not 16s.

    ``seconds_since_heartbeat`` only advances in 2s (poll interval) steps,
    so a ``>= 15`` threshold's first reachable value is 16 -- silently
    reproducing the exact 16s gap the trace flagged as the keepalive risk
    (t+68.5 -> t+84.6 in the #2049 trace). Disconnecting after exactly 7
    quiet polls (14s elapsed since the one real event) proves the bound:
    under the old threshold=15 the ping would not have fired yet at this
    point (next multiple of 2 reaching 15 is 16, one poll later); under
    the fixed threshold=14 it must already have fired.
    """
    monkeypatch.setattr(data_sync_module, "DataIngestionRepository", _FakeRepo)
    monkeypatch.setattr(
        data_sync_module.db_module, "SessionLocal", lambda: _FakeSessionCM()
    )

    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(data_sync_module.asyncio, "sleep", _instant_sleep)

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {"backoffice.configuration": ["view"]}

    # Poll 1 emits the real state-change event and resets the clock, then
    # every poll's 2s sleep (including poll 1's own) adds to it: 7 polls *
    # 2s = 14, so the ping must fire by poll 7 -- the last one that runs
    # before the 8th ``is_disconnected()`` call ends the stream.
    request = _FakeRequest(n_polls_before_disconnect=7)

    response = await data_sync_module.job_stream_by_id(
        job_id=1, request=request, current_user=fake_user
    )

    events: list[str] = []
    async for chunk in response.body_iterator:
        events.append(chunk if isinstance(chunk, str) else chunk.decode())
        if len(events) > 15:  # safety valve, don't loop forever on a regression
            break

    assert any(e.startswith("event: ping") for e in events), (
        "Heartbeat did not fire within 14s of quiet -- "
        "heartbeat_interval_seconds regressed to a value only reachable "
        "at 16s (e.g. 15), reproducing the gap #2049's trace flagged."
    )
