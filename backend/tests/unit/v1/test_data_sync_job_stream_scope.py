"""#1764 — job_stream_by_id gates cross-unit (MODULE_PER_YEAR) jobs behind
``backoffice.configuration``.

``_check_job_scope`` no-ops for jobs it can't narrow to a unit, relying on
an upstream backoffice gate that this route's actual gate
(``can_view_module_flow``) doesn't provide -- a plain unit-sync user could
stream an arbitrary shared job's full raw ``meta`` (``unit_id``/
``CarbonReport`` ids in ``stats.error_details``, uploader email/name in
``created_by``). Pins that the stream now hard-403s that case instead, and
that a ``backoffice.configuration`` viewer is unaffected.

Drives ``job_stream_by_id`` directly (no FastAPI dependency injection),
mirroring ``test_data_sync_job_stream_heartbeat.py``'s fake session/repo
harness.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.data_sync as data_sync_module
from app.models.data_ingestion import EntityType, IngestionState


class _FakeSharedJob:
    """A MODULE_PER_YEAR job -- ``_check_job_scope`` can't narrow this to a
    unit, so whether its stream opens now depends entirely on the new
    ``backoffice.configuration`` check (#1764).
    """

    id = 1
    module_type_id = 4
    entity_type = EntityType.MODULE_PER_YEAR
    entity_id = None
    target_type = "module"
    year = 2025
    state = IngestionState.RUNNING
    result = None
    status_message = "running"
    meta = {
        "created_by": {"email": "other-unit-user@example.org", "name": "Someone"},
        "stats": {"errors": 1, "error_details": [{"factor_id": 1, "error": "boom"}]},
    }


class _FakeRepo:
    def __init__(self, _session):
        pass

    async def get_job_by_id(self, _job_id):
        return _FakeSharedJob()


class _FakeSessionCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *_exc):
        return False


def _patch_session(monkeypatch):
    monkeypatch.setattr(data_sync_module, "DataIngestionRepository", _FakeRepo)
    monkeypatch.setattr(
        data_sync_module.db_module, "SessionLocal", lambda: _FakeSessionCM()
    )


@pytest.mark.asyncio
async def test_shared_job_stream_denied_without_backoffice_permission(monkeypatch):
    _patch_session(monkeypatch)

    fake_user = MagicMock()
    # Sync rights on their own unit's module -- enough for
    # can_view_module_flow to admit them into the route -- but no
    # backoffice.configuration.
    fake_user.calculate_permissions = lambda: {
        "modules.research_facilities/1234": ["view", "sync"]
    }

    with pytest.raises(HTTPException) as exc_info:
        await data_sync_module.job_stream_by_id(
            job_id=1, request=MagicMock(), current_user=fake_user
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_shared_job_stream_allowed_with_backoffice_permission(monkeypatch):
    _patch_session(monkeypatch)

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {"backoffice.configuration": ["view"]}

    response = await data_sync_module.job_stream_by_id(
        job_id=1, request=MagicMock(), current_user=fake_user
    )
    assert response.media_type == "text/event-stream"
