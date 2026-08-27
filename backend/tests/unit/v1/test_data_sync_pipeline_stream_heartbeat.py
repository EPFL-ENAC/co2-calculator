"""#2049 T7-followup — pipeline_stream_by_id's SSE heartbeat gap bound.

``pipeline_stream_by_id`` shipped its ``event: ping`` heartbeat before
#2049's T7 gave ``job_stream_by_id`` the same thing, but neither endpoint's
``seconds_since_heartbeat`` accumulator can land on the ``>= 15`` threshold
except at 16 (2s poll-interval steps: 14, then 16) -- silently reproducing
the exact 16s zero-byte gap the trace flagged as the keepalive risk. This
pins the fixed threshold (14) actually bounds the gap under 15s, the same
way ``test_data_sync_job_stream_heartbeat.py`` pins it for the job stream.

No PG integration test drives this generator today -- the pipeline-stream
PG test file explicitly defers streaming-body coverage (httpx/asyncpg
session teardown races with ``StreamingResponse``), so this direct
generator-drive is the only coverage of the heartbeat's timing at all.
Same rationale as the job-stream unit test: drive the generator directly,
monkeypatch ``asyncio.sleep`` to be instant, and fake the repository so
nothing here touches a real DB.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import app.api.v1.data_sync as data_sync_module
from app.models.data_ingestion import IngestionState


class _FakeJob:
    """A lone, never-finishing root job -- isolates the test to heartbeat
    timing, not snapshot-diffing or completion (covered elsewhere).
    """

    id = 1
    job_type = "csv_ingest"
    data_entry_type_id = None
    state = IngestionState.RUNNING
    result = None
    status_message = "running"
    started_at = None
    finished_at = None


class _FakeRepo:
    def __init__(self, _session):
        pass

    async def list_jobs_by_pipeline_id(self, _pipeline_id):
        return [_FakeJob()]

    async def get_pipeline_by_id(self, _pipeline_id):
        return None


class _FakeSessionCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_exc):
        return False


class _FakeRequest:
    """Disconnects after ``n_polls_before_disconnect`` polls."""

    def __init__(self, n_polls_before_disconnect: int):
        self._remaining = n_polls_before_disconnect

    async def is_disconnected(self) -> bool:
        if self._remaining <= 0:
            return True
        self._remaining -= 1
        return False


@pytest.mark.asyncio
async def test_pipeline_stream_heartbeat_fires_within_15s_not_16(monkeypatch):
    """See module docstring: the ping must fire by 14s of quiet, not 16s."""
    monkeypatch.setattr(data_sync_module, "DataIngestionRepository", _FakeRepo)
    monkeypatch.setattr(
        data_sync_module.db_module, "SessionLocal", lambda: _FakeSessionCM()
    )

    async def _allow_scope(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        data_sync_module, "_check_pipeline_scope_from_jobs", _allow_scope
    )

    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(data_sync_module.asyncio, "sleep", _instant_sleep)

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {
        "backoffice.pipeline_operations": ["view"]
    }

    # Poll 1 emits the real snapshot (last_snapshot starts None) and resets
    # the clock; every poll's 2s sleep then adds to it, including poll 1's
    # own -- 7 polls * 2s = 14, so the ping must fire by poll 7, the last
    # one that runs before the 8th ``is_disconnected()`` call ends the
    # stream. Mirrors test_job_stream_heartbeat_fires_within_15s_not_16.
    request = _FakeRequest(n_polls_before_disconnect=7)

    response = await data_sync_module.pipeline_stream_by_id(
        pipeline_id=uuid4(), request=request, current_user=fake_user
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
    # First event is the real initial snapshot (last_snapshot started None).
    assert events[0].startswith("event: pipeline-update")
