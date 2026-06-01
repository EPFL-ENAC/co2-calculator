"""Integration test for ``GET /v1/sync/active-pipelines/year/{year}`` against PG.

Issue #867 — year-level (``entity_type=GLOBAL_PER_YEAR``) sibling of
the module-scoped ``GET /sync/active-pipelines`` endpoint.  Backs the
``DataManagementPage.vue`` reload-rehydrate path: the SSE watcher
re-attaches to in-flight unit-sync (or any future GLOBAL_PER_YEAR)
pipelines after a hard reload.

Mirrors the auth / dependency-override pattern in
``test_active_pipelines_endpoint_pg.py``.  Postgres is required because
``DataIngestionJob.pipeline_id`` is a native ``UUID`` column; SQLite
doesn't enforce UUID typing and would hide a serialisation regression.
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

    The 403 test below deliberately bypasses this fixture to exercise
    the real permission gate on the endpoint.
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

    yield {"factory": Sf}

    app.dependency_overrides.clear()
    await engine.dispose()


def _make_year_level_job(
    *,
    year: int,
    pipeline_id,
    state: IngestionState = IngestionState.RUNNING,
) -> DataIngestionJob:
    """Active year-level (``GLOBAL_PER_YEAR``) job carrying a
    ``pipeline_id`` — what the new helper picks as 'currently in
    flight' for this year.

    Mirrors the unit-sync job shape in
    ``app/api/v1/data_sync.py::sync_units_from_accred`` plus the
    ``pipeline_id`` U1 stamps onto these chains.
    """
    return DataIngestionJob(
        entity_type=EntityType.GLOBAL_PER_YEAR,
        module_type_id=None,
        data_entry_type_id=None,
        year=year,
        target_type=TargetType.REFERENCE_DATA,
        ingestion_method=IngestionMethod.api,
        provider=UserProvider.DEFAULT,
        state=state,
        pipeline_id=pipeline_id,
        job_type="unit_sync",
        meta={"config": {"target_year": year}},
    )


@pytest.mark.asyncio
async def test_year_level_active_pipelines_returns_running_pipeline_id(pg_app):
    """A single in-flight year-level chain → endpoint returns its
    pipeline_id as the only entry.  This is the canonical case for
    the reload-rehydrate flow: operator triggers a unit-sync, hard
    reloads the page, the page re-attaches to the live stream."""
    Sf = pg_app["factory"]
    pipeline = uuid4()

    async with Sf() as session:
        session.add(_make_year_level_job(year=2025, pipeline_id=pipeline))
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == [str(pipeline)]


@pytest.mark.asyncio
async def test_year_level_active_pipelines_omits_finished(pg_app):
    """Finished year-level jobs must NOT appear — the watcher would
    open an SSE stream that immediately resolves to ``stream_closed``,
    wasting a request and momentarily flickering UI."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        session.add(
            _make_year_level_job(
                year=2025,
                pipeline_id=uuid4(),
                state=IngestionState.FINISHED,
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_year_level_active_pipelines_filters_by_year(pg_app):
    """A 2024 chain must not surface in 2025's response — guards the
    watcher from cross-year bleed when the operator is viewing one
    year while a chain runs for another."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        session.add(_make_year_level_job(year=2024, pipeline_id=uuid4()))
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_year_level_active_pipelines_omits_jobs_without_pipeline_id(pg_app):
    """Year-level jobs with ``pipeline_id IS NULL`` (legacy / U1
    not-yet-shipped) must not appear.  Without a pipeline_id the SSE
    stream endpoint has nothing to subscribe to — including these
    would mean the watcher opens a 404 stream.  This is what makes
    the U1-independence guarantee in the unit's spec hold."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        # Same shape as a real unit_sync job pre-U1 — note no pipeline_id.
        session.add(
            DataIngestionJob(
                entity_type=EntityType.GLOBAL_PER_YEAR,
                year=2025,
                target_type=TargetType.REFERENCE_DATA,
                ingestion_method=IngestionMethod.api,
                provider=UserProvider.DEFAULT,
                state=IngestionState.RUNNING,
                pipeline_id=None,
                job_type="unit_sync",
                meta={"config": {"target_year": 2025}},
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_year_level_active_pipelines_omits_module_scoped(pg_app):
    """Module-scoped (``MODULE_PER_YEAR``) pipelines are the
    sibling endpoint's concern — they must NOT leak into the
    year-level endpoint, even when ``year`` matches.  Otherwise the
    watcher would double-subscribe (ModuleConfig.vue already covers
    these via the per-module endpoint)."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        session.add(
            DataIngestionJob(
                entity_type=EntityType.MODULE_PER_YEAR,
                module_type_id=1,
                year=2025,
                target_type=TargetType.DATA_ENTRIES,
                ingestion_method=IngestionMethod.computed,
                provider=UserProvider.DEFAULT,
                state=IngestionState.RUNNING,
                is_current=True,
                pipeline_id=uuid4(),
                job_type="aggregation",
                meta={},
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_year_level_active_pipelines_dedupes_pipeline_ids(pg_app):
    """A pipeline can have multiple jobs sharing one ``pipeline_id``
    (parent + fan-out children).  The endpoint returns each
    pipeline_id once — the frontend treats the result as a set."""
    Sf = pg_app["factory"]
    shared_pipeline = uuid4()

    async with Sf() as session:
        # Two jobs in the same pipeline (e.g. parent + a fan-out child).
        session.add(_make_year_level_job(year=2025, pipeline_id=shared_pipeline))
        session.add(
            _make_year_level_job(
                year=2025,
                pipeline_id=shared_pipeline,
                state=IngestionState.QUEUED,
            )
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == [str(shared_pipeline)]


@pytest.mark.asyncio
async def test_year_level_active_pipelines_returns_empty_when_no_jobs(pg_app):
    """Steady state: no year-level pipelines anywhere → empty list.
    The watcher idles, no SSE streams open."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/sync/active-pipelines/year/2025")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_year_level_active_pipelines_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """``GET /v1/sync/active-pipelines/year/{year}`` is gated behind
    ``backoffice.data_management.view``.  Users without that permission
    get HTTP 403.

    Deliberately bypasses ``pg_app`` (which monkeypatches ``is_permitted``
    to always-True) so the real permission check fires.
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

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.core.security.is_permitted", _deny)

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/v1/sync/active-pipelines/year/2025")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text
