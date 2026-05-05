"""Integration test for ``GET /v1/factors/stale`` against a real Postgres.

Plan 310B Part 3 — operators see factors not present in the latest CSV
upload via this endpoint.  The endpoint round-trips through:

- ``FactorRepository.list_stale_for_year`` (covered separately by
  ``test_plan_310b_factor_pipeline_pg.py``)
- ``StaleFactorResponse`` model conversion
- FastAPI route + dependency injection wiring

This test exists primarily to cover the HTTP route + response-model code
in ``app/api/v1/factors.py`` that the repo-level tests don't touch.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
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
from app.repositories.factor_repo import FactorRepository
from tests.integration.services.data_ingestion.test_plan_310b_factor_pipeline_pg import (  # noqa: E501
    _make_factor,
    _seed_factor_job,
)


async def _install_indexes(engine) -> None:
    """Mirror migration b1f0a2c3d4e5's partial unique indexes — pg_dsn's
    SQLModel.metadata.create_all doesn't run Alembic, so the indexes
    aren't created automatically and ``upsert_factors`` would fail
    inferring its conflict target."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity "
                "ON factors (data_entry_type_id, year, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NOT NULL"
            )
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_factor_identity_no_year "
                "ON factors (data_entry_type_id, emission_type_id, "
                "(classification::text)) "
                "WHERE year IS NULL"
            )
        )


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth."""
    engine = create_async_engine(pg_dsn, future=True)
    await _install_indexes(engine)
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


@pytest.mark.asyncio
async def test_get_stale_factors_returns_only_outdated_rows(pg_app):
    """End-to-end: seed one stale + one fresh factor under different
    is_current FACTORS jobs and verify the endpoint returns just the
    stale one in StaleFactorResponse shape."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        old_job = _seed_factor_job()
        old_job.is_current = False
        latest_job = _seed_factor_job()
        session.add_all([old_job, latest_job])
        await session.commit()
        assert old_job.id is not None and latest_job.id is not None
        old_id: int = old_job.id
        latest_id: int = latest_job.id

        repo = FactorRepository(session)
        await repo.upsert_factors(
            [_make_factor({"kind": "food", "subkind": None})],
            current_job_id=old_id,
        )
        await repo.upsert_factors(
            [_make_factor({"kind": "waste", "subkind": None})],
            current_job_id=latest_id,
        )
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/factors/stale", params={"year": 2025})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1, f"Expected exactly 1 stale row, got {body!r}"
    row = body[0]
    # Verify the StaleFactorResponse shape — fields the operator UI relies on.
    assert row["classification"] == {"kind": "food", "subkind": None}
    assert row["last_seen_job_id"] == old_id
    assert row["year"] == 2025
    assert row["data_entry_type_id"] == 1
    assert row["emission_type_id"] == 10000
    assert isinstance(row["id"], int) and row["id"] > 0


@pytest.mark.asyncio
async def test_stale_endpoint_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """Plan 310C Unit 2 — ``GET /v1/factors/stale`` is gated behind
    ``backoffice.data_management.view``.  Users without that permission
    get HTTP 403, not the stale-factor list.

    This test deliberately bypasses ``pg_app`` (which monkeypatches
    ``is_permitted`` to always return True) so the real permission
    check fires.  We still need to override ``get_db`` and the
    auth dependencies so the route reaches the permission gate."""
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
            resp = await client.get("/v1/factors/stale", params={"year": 2025})
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_stale_endpoint_returns_200_for_permitted_user(pg_app):
    """Plan 310C Unit 2 — happy path of the permission gate.  When
    ``is_permitted`` returns True (via ``pg_app``'s monkeypatch), the
    endpoint reaches the repository and returns the StaleFactorResponse
    list shape — even when there's nothing to report."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/factors/stale", params={"year": 2025})

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_stale_factors_returns_empty_list_with_no_factor_jobs(pg_app):
    """No FACTORS jobs for the queried year → endpoint returns ``[]``,
    not an error and not the full factor table.  Confirms the empty-map
    short-circuit in ``list_stale_for_year`` propagates through the
    HTTP response model."""
    Sf = pg_app["factory"]

    async with Sf() as session:
        # Seed a non-current FACTORS job for a different year, just to prove
        # we're filtering by year and not "any FACTORS job ever exists".
        other_job = DataIngestionJob(
            entity_type=EntityType.MODULE_PER_YEAR,
            module_type_id=1,
            data_entry_type_id=1,
            year=2024,
            target_type=TargetType.FACTORS,
            ingestion_method=IngestionMethod.csv,
            provider=UserProvider.DEFAULT,
            state=IngestionState.FINISHED,
            result=IngestionResult.SUCCESS,
            is_current=True,
        )
        session.add(other_job)
        await session.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/v1/factors/stale", params={"year": 2025})

    assert resp.status_code == 200, resp.text
    assert resp.json() == []
