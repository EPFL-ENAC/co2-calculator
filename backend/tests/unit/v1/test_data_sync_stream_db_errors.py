"""#2956 — a DB error mid-stream ends the SSE stream and logs the real cause.

Once a response has started, Starlette re-raises an exception that has a
registered handler as ``RuntimeError("Caught handled exception, but response
already started.")``, which hid the DB error behind ``__cause__``. These tests
drive the generators directly with a repository that fails on the second
poll, the same way the heartbeat tests do.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

import app.api.v1.data_sync as data_sync_module
from app.models.data_ingestion import EntityType, IngestionState

DB_ERRORS = [
    OperationalError(
        "SELECT 1", {}, psycopg.OperationalError("server closed the connection")
    ),
    SQLAlchemyTimeoutError("QueuePool limit reached, connection timed out"),
]


class _FakeJob:
    id = 1
    module_type_id = None  # _check_job_scope no-ops on this
    entity_type = EntityType.GLOBAL_PER_YEAR
    entity_id = None
    target_type = "module"
    year = 2025
    job_type = "csv_ingest"
    data_entry_type_id = None
    state = IngestionState.RUNNING
    result = None
    status_message = "running"
    meta = None
    started_at = None
    finished_at = None


def _failing_repo(error: Exception):
    """Reads succeed twice (pre-stream check, first poll), then raise."""
    calls = {"n": 0}

    def _read() -> _FakeJob:
        calls["n"] += 1
        if calls["n"] > 2:
            raise error
        return _FakeJob()

    class _Repo:
        def __init__(self, _session):
            pass

        async def get_job_by_id(self, _job_id):
            return _read()

        async def list_jobs_by_pipeline_id(self, _pipeline_id):
            return [_read()]

        async def get_pipeline_by_id(self, _pipeline_id):
            return None

    return _Repo


class _FakeSessionCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_exc):
        return False


class _FakeRequest:
    url = SimpleNamespace(path="/api/v1/sync/stream")

    async def is_disconnected(self) -> bool:
        return False


def _user() -> MagicMock:
    user = MagicMock()
    user.calculate_permissions = lambda: {"backoffice.configuration": ["view"]}
    return user


async def _drain(response) -> list[str]:
    events: list[str] = []
    async for chunk in response.body_iterator:
        events.append(chunk if isinstance(chunk, str) else chunk.decode())
        if len(events) > 10:  # safety valve: the stream must end on its own
            break
    return events


@pytest.fixture
def fake_db(monkeypatch):
    monkeypatch.setattr(
        data_sync_module.db_module, "SessionLocal", lambda: _FakeSessionCM()
    )

    async def _instant_sleep(_seconds):
        return None

    async def _allow_scope(*_args, **_kwargs):
        return None

    monkeypatch.setattr(data_sync_module.asyncio, "sleep", _instant_sleep)
    monkeypatch.setattr(
        data_sync_module, "_check_pipeline_scope_from_jobs", _allow_scope
    )


def _logged_errors(caplog) -> list[BaseException | None]:
    return [r.exc_info[1] for r in caplog.records if r.exc_info]


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_db")
@pytest.mark.parametrize("error", DB_ERRORS, ids=lambda e: type(e).__name__)
async def test_job_stream_ends_with_terminal_event_on_db_error(
    monkeypatch, caplog, error
):
    monkeypatch.setattr(
        data_sync_module, "DataIngestionRepository", _failing_repo(error)
    )
    response = await data_sync_module.job_stream_by_id(
        job_id=1, request=_FakeRequest(), current_user=_user()
    )

    with caplog.at_level("ERROR", logger="app.api.v1.data_sync"):
        events = await _drain(response)

    assert len(events) == 2, events
    first = json.loads(events[0].removeprefix("data: "))
    assert first["state"] == IngestionState.RUNNING
    # Same shape as the stream's "Job not found" event: no state/result, so
    # the frontend doesn't record a fake finished job.
    assert json.loads(events[1].removeprefix("data: ")) == {
        "job_id": 1,
        "status_message": "Job status unavailable: database error",
    }
    assert _logged_errors(caplog) == [error]


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_db")
async def test_pipeline_stream_closes_without_event_on_db_error(monkeypatch, caplog):
    error = DB_ERRORS[0]
    monkeypatch.setattr(
        data_sync_module, "DataIngestionRepository", _failing_repo(error)
    )
    response = await data_sync_module.pipeline_stream_by_id(
        pipeline_id=uuid4(), request=_FakeRequest(), current_user=_user()
    )

    with caplog.at_level("ERROR", logger="app.api.v1.data_sync"):
        events = await _drain(response)

    assert len(events) == 1, events
    assert events[0].startswith("event: pipeline-update")
    assert _logged_errors(caplog) == [error]


@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_db")
async def test_stream_does_not_swallow_non_db_errors(monkeypatch):
    monkeypatch.setattr(
        data_sync_module, "DataIngestionRepository", _failing_repo(ValueError("bug"))
    )
    response = await data_sync_module.job_stream_by_id(
        job_id=1, request=_FakeRequest(), current_user=_user()
    )

    with pytest.raises(ValueError, match="bug"):
        await _drain(response)
