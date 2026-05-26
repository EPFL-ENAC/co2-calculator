"""Integration test for POST /v1/sync/units against a real Postgres.

Plan 310B Part 5 changed the endpoint from a fire-and-forget background
task (``job_id=0``) to a tracked DataIngestionJob with
``entity_type=GLOBAL_PER_YEAR`` and ``target_type=REFERENCE_DATA``.

Production failure observed: ``invalid input value for enum
target_type_enum: "REFERENCE_DATA"`` — the Postgres enum type was missing
the ``REFERENCE_DATA`` label.  Migration ``c2d4e6f8a012`` adds it.

This test exercises the full endpoint round-trip against PG:

- POSTing ``{"target_year": 2025}`` returns 200 with a non-zero ``job_id``.
- A ``DataIngestionJob`` row is committed to the DB with the expected
  ``job_type='unit_sync'``, ``entity_type=GLOBAL_PER_YEAR``,
  ``target_type=REFERENCE_DATA`` shape.
- Verification reads the row on a **separate engine** so the assertion
  only passes if the insert is committed and visible cross-connection.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionState,
    TargetType,
)
from app.models.user import UserProvider


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"
    fake_user.provider = UserProvider.DEFAULT

    app.dependency_overrides[deps_module.get_db] = override_get_db
    app.dependency_overrides[deps_module.get_current_user] = lambda: fake_user
    app.dependency_overrides[security_module.get_current_active_user] = lambda: (
        fake_user
    )

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr("app.core.security.is_permitted", _allow)

    yield {"factory": Sf, "dsn": pg_dsn}

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_post_sync_units_creates_tracked_job(pg_app):
    """POST /v1/sync/units commits a real DataIngestionJob and returns its
    id; the row's enum-typed columns survive the round-trip (specifically
    target_type=REFERENCE_DATA, the column that tripped production)."""
    pg_dsn = pg_app["dsn"]

    # Use httpx.AsyncClient + ASGITransport so the request runs on the same
    # event loop as the pg_dsn fixture's async engine — TestClient spins up
    # its own anyio portal, which would conflict with asyncpg connections
    # bound to the test loop.
    #
    # Plan 310-C cutover: the endpoint now fires ``run_job(job_id)``
    # via ``fire_and_forget``.  Patch ``run_job`` to a noop coroutine
    # so the request returns synchronously (no Accred fetch, no DB
    # writes from the runner), while still asserting the dispatch
    # site fired with the right job id.
    runner_calls: list[int] = []

    async def _noop_run_job(job_id: int):
        runner_calls.append(job_id)

    with patch("app.api.v1.data_sync.run_job", _noop_run_job):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post("/v1/sync/units", json={"target_year": 2025})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["state"] == IngestionState.NOT_STARTED.value
    job_id = body["job_id"]
    assert job_id and job_id > 0, (
        f"Expected a non-zero job_id (Plan 310B replaced the placeholder 0), "
        f"got {body!r}"
    )

    # The endpoint should have scheduled the noop runner with the job_id
    # it just created.
    assert runner_calls == [job_id]

    # Verify on a fresh engine — proves cross-connection commit visibility.
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            row = (
                await vs.execute(
                    select(DataIngestionJob).where(col(DataIngestionJob.id) == job_id)
                )
            ).scalar_one()
    finally:
        await verify_engine.dispose()

    assert row.job_type == "unit_sync"
    assert row.entity_type == EntityType.GLOBAL_PER_YEAR
    assert row.target_type == TargetType.REFERENCE_DATA
    assert row.year == 2025
    assert row.module_type_id is None
    assert row.data_entry_type_id is None
    assert row.state == IngestionState.NOT_STARTED
    assert row.meta is not None
    assert row.meta["config"]["target_year"] == 2025
