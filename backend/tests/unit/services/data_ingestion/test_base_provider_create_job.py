"""``create_job`` must persist the unit scope it is handed (#2654).

Every ``/sync`` read gate resolves a job's unit from
``DataIngestionJob.entity_id``.  From the day that column was added until
this test, nothing wrote it: unit-pinned jobs looked unscoped, the per-job
gate no-op'd for everyone, and the job stream 403'd principals on their
own uploads.  This pins the write; the seeded Postgres tests in
``tests/integration/services/data_ingestion/test_sync_pipeline_stream_endpoint_pg.py``
pin the read.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.data_ingestion.base_provider as base_provider_module
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.user import UserProvider
from tests.unit.services.data_ingestion.test_base_provider import ConcreteProvider


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 1
    user.email = "principal@example.org"
    user.display_name = "Principal"
    user.institutional_id = "1111"
    user.provider = UserProvider.DEFAULT
    return user


def _capture_repo(monkeypatch) -> list:
    created: list = []

    class _Repo:
        def __init__(self, _db):
            pass

        async def create_ingestion_job(self, job):
            job.id = 42
            created.append(job)
            return job

    monkeypatch.setattr(base_provider_module, "DataIngestionRepository", _Repo)
    audit = MagicMock()
    audit.create_version = AsyncMock()
    monkeypatch.setattr(
        "app.services.audit_service.AuditDocumentService", lambda _db: audit
    )
    return created


@pytest.mark.asyncio
async def test_unit_specific_job_carries_carbon_report_module_id(monkeypatch):
    created = _capture_repo(monkeypatch)
    provider = ConcreteProvider({}, user=_user(), data_session=None)

    await provider.create_job(
        ingestion_method=IngestionMethod.csv,
        entity_type=EntityType.MODULE_UNIT_SPECIFIC,
        target_type=TargetType.DATA_ENTRIES,
        config={"carbon_report_module_id": 123},
        db=MagicMock(),
    )

    assert created[0].entity_id == 123


@pytest.mark.asyncio
async def test_per_year_job_has_no_entity_id(monkeypatch):
    created = _capture_repo(monkeypatch)
    provider = ConcreteProvider({}, user=_user(), data_session=None)

    await provider.create_job(
        ingestion_method=IngestionMethod.csv,
        entity_type=EntityType.MODULE_PER_YEAR,
        target_type=TargetType.DATA_ENTRIES,
        config={},
        db=MagicMock(),
    )

    assert created[0].entity_id is None
