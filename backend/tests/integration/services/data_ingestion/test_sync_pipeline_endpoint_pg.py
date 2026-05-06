"""Integration test for ``GET /v1/sync/pipelines/{pipeline_id}`` against PG.

Plan 310C — surfaces every job in a multi-step pipeline (parent FACTORS
job + the fan-out DATA_ENTRIES recalc children seeded by 310B's
``_enqueue_stale_recalculations``) so the dashboard can render the chain.

Why a real Postgres (not SQLite):

- ``DataIngestionJob.pipeline_id`` is a native ``UUID`` column.  SQLite
  doesn't enforce UUID typing — testing against PG verifies the round-trip
  through asyncpg, the column type, and the FastAPI ``UUID`` path-param
  parse all line up.
- The endpoint exposes enum columns (``state``, ``result``,
  ``target_type``).  The PG enum types must round-trip through the
  response_model serialisation; SQLite stores them as plain strings and
  hides any mismatch.

Mirrors the auth / dependency-override pattern in
``test_factors_stale_endpoint_pg.py`` (the canonical 310-series example).

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
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
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    ``is_permitted`` is monkeypatched to always-True so tests reach the
    endpoint body.  The 403 test below deliberately bypasses this fixture
    to exercise the real permission gate.
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


def _make_parent_factor_job(pipeline_id) -> DataIngestionJob:
    """FACTORS / FINISHED / SUCCESS — the chain head."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=1,
        year=2025,
        target_type=TargetType.FACTORS,
        ingestion_method=IngestionMethod.csv,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
        pipeline_id=pipeline_id,
        job_type="factor_ingest",
    )


def _make_child_data_entries_job(
    pipeline_id, *, data_entry_type_id: int
) -> DataIngestionJob:
    """DATA_ENTRIES recalc child — fan-out from the parent."""
    return DataIngestionJob(
        entity_type=EntityType.MODULE_PER_YEAR,
        module_type_id=1,
        data_entry_type_id=data_entry_type_id,
        year=2025,
        target_type=TargetType.DATA_ENTRIES,
        ingestion_method=IngestionMethod.computed,
        provider=UserProvider.DEFAULT,
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        is_current=True,
        pipeline_id=pipeline_id,
        job_type="data_entry_recalc",
    )


@pytest.mark.asyncio
async def test_get_pipeline_returns_ordered_jobs(pg_app):
    """End-to-end: seed a parent + 2 children sharing a pipeline_id and
    verify the endpoint returns all 3 jobs ordered by id ASC, with the
    enum columns serialised to their integer values."""
    Sf = pg_app["factory"]
    pipeline_id = uuid4()

    async with Sf() as session:
        parent = _make_parent_factor_job(pipeline_id)
        child_a = _make_child_data_entries_job(pipeline_id, data_entry_type_id=2)
        child_b = _make_child_data_entries_job(pipeline_id, data_entry_type_id=3)
        # Insert sequentially so ids are deterministic (parent first).
        session.add(parent)
        await session.flush()
        session.add(child_a)
        await session.flush()
        session.add(child_b)
        await session.commit()
        assert parent.id is not None
        assert child_a.id is not None
        assert child_b.id is not None
        expected_order = [parent.id, child_a.id, child_b.id]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/sync/pipelines/{pipeline_id}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pipeline_id"] == str(pipeline_id)
    jobs = body["jobs"]
    assert isinstance(jobs, list)
    actual_ids = [j["job_id"] for j in jobs]
    assert actual_ids == expected_order, (
        f"Expected ASC-id ordering {expected_order}, got {actual_ids!r}"
    )

    # Verify the parent shape — proves enum and Optional columns serialise.
    parent_row = jobs[0]
    assert parent_row["job_type"] == "factor_ingest"
    assert parent_row["state"] == IngestionState.FINISHED.value
    assert parent_row["result"] == IngestionResult.SUCCESS.value
    assert parent_row["target_type"] == TargetType.FACTORS.value
    assert parent_row["module_type_id"] == 1
    assert parent_row["data_entry_type_id"] == 1
    assert parent_row["year"] == 2025

    # And one child — different job_type, different data_entry_type_id,
    # different target_type (DATA_ENTRIES rather than parent's FACTORS).
    child_row = jobs[1]
    assert child_row["job_type"] == "data_entry_recalc"
    assert child_row["data_entry_type_id"] == 2
    assert child_row["target_type"] == TargetType.DATA_ENTRIES.value


@pytest.mark.asyncio
async def test_get_pipeline_does_not_leak_jobs_from_other_pipelines(pg_app):
    """Filtering bug regression — two unrelated pipelines should not
    cross-contaminate.  Catches a ``SELECT *`` that forgot the WHERE
    clause."""
    Sf = pg_app["factory"]
    target_pipeline = uuid4()
    other_pipeline = uuid4()

    async with Sf() as session:
        ours = _make_parent_factor_job(target_pipeline)
        theirs = _make_parent_factor_job(other_pipeline)
        # Different combo so the partial unique is_current index doesn't trip.
        theirs.module_type_id = 2
        theirs.data_entry_type_id = 2
        session.add_all([ours, theirs])
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/sync/pipelines/{target_pipeline}")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["module_type_id"] == 1


@pytest.mark.asyncio
async def test_get_pipeline_unknown_uuid_returns_404(pg_app):
    """No rows for the given pipeline_id → 404.  Matches the
    ``cancel_job`` / ``recover_job`` not-found convention in this module
    so the frontend can distinguish 'pipeline does not exist' from
    'pipeline exists but is empty' (which is impossible by construction —
    310B always seeds the parent)."""
    unknown_pipeline = uuid4()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/v1/sync/pipelines/{unknown_pipeline}")

    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_pipeline_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """``GET /v1/sync/pipelines/{id}`` is gated behind
    ``backoffice.data_management.view``.  Users without that permission
    get HTTP 403.

    Deliberately bypasses ``pg_app`` (which monkeypatches ``is_permitted``
    to always-True) so the real permission check fires.  We still need to
    override ``get_db`` and the auth dependencies so the route reaches the
    permission gate."""
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
            resp = await client.get(f"/v1/sync/pipelines/{uuid4()}")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text
