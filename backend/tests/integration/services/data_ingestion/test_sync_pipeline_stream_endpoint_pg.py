"""Integration test for ``GET /v1/sync/pipelines/{pipeline_id}/stream`` (PG).

Plan 310D — backend half of the stale-stats UX.  Mirrors the read endpoint
test in ``test_sync_pipeline_endpoint_pg.py``: same auth fixture pattern,
same pipeline-id seeding, same Postgres rationale (native ``UUID`` column,
enum types, asyncpg round-trip).

Coverage scope: the *contract* assertions (404 short-circuit before the
stream opens, 403 permission gate) — not the streaming body.

**Streaming-body coverage is deferred.**  The pre-existing
``GET /sync/jobs/{job_id}/stream`` endpoint (which this one mirrors) also
ships without integration coverage — running ``StreamingResponse`` through
``httpx.ASGITransport`` against an asyncpg-backed test engine triggers
``InterfaceError: connection is closed`` when the FastAPI dep teardown
races with the generator's queries on the same engine, regardless of pool
class.  Producing a stable streaming-body test would require either
extracting the snapshot/poll logic for direct unit-testing or moving the
session lifetime out of ``Depends(get_db)`` for SSE endpoints — a
codebase-wide refactor not in this PR's scope.  The repo-level unit tests
in ``tests/unit/repositories/test_data_ingestion_repo.py`` cover the data
shape; the contract tests below cover gating and not-found.
"""

from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    Same shape as ``test_sync_pipeline_endpoint_pg.py``: the 403 test
    bypasses this fixture so the real permission gate fires.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)

    yield {"factory": Sf, "engine": engine}

    app.dependency_overrides.clear()
    await engine.dispose()


def _make_pending_factor_job(pipeline_id) -> DataIngestionJob:
    """Active (NOT_STARTED) parent — the chain head, not yet picked up."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=1,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.NOT_STARTED,
        is_current=True,
        pipeline_id=pipeline_id,
        job_type="factor_ingest",
    )


@pytest.mark.asyncio
async def test_pipeline_stream_unknown_pipeline_returns_404(pg_app):
    """Unknown pipeline_id → 404 *before* the stream opens.

    The endpoint short-circuits with ``HTTPException`` so SSE clients see
    a proper HTTP error, not a 200-with-empty-body that they would
    interpret as an aborted connection.  Symmetric with the
    not-found contract on the read endpoint.
    """
    unknown = uuid4()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/sync/pipelines/{unknown}/stream")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_pipeline_stream_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """Permission gate matches the read endpoint's
    ``backoffice.data_management.view``.

    Bypasses ``pg_app`` (which monkeypatches ``is_permitted`` to True)
    so the real ``require_permission`` dependency fires.  We still seed
    a job so a permitted user *would* have hit a 200 — proves the 403
    stems from the gate, not from the not-found short-circuit running
    first.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    pipeline_id = uuid4()
    async with Sf() as session:
        session.add(_make_pending_factor_job(pipeline_id))
        await session.commit()

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.core.security.is_permitted", _deny)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/v1/sync/pipelines/{pipeline_id}/stream")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text
