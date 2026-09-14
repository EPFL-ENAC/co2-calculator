"""Integration tests for ``POST /v1/sync/admin/recompute-stats`` against a
real Postgres.

The admin backfill trigger for the stats-bucket refactor (#841): dispatches
one root ``aggregation`` job per ``(module_type_id, year)`` scope so every
``carbon_report_module.stats`` / ``carbon_report.stats`` row gets recomputed
under the current code, not whatever an older deploy last wrote.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.api.deps as deps_module
import app.core.security as security_module
from app.main import app
from app.models.carbon_project import CarbonProject
from app.models.carbon_report import (
    CarbonReport,
    CarbonReportModule,
    CarbonReportType,
)
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.unit import Unit
from app.repositories.carbon_report_module_repo import CarbonReportModuleRepository

_MT_A = 1  # ModuleTypeEnum.headcount
_MT_B = 2  # ModuleTypeEnum.professional_travel

_YEAR_2024 = 2024
_YEAR_2025 = 2025

# A Simulator Plan year report: its own ``year`` is the planning target,
# its entries price against ``reference_year`` (#2775).
_PLAN_YEAR = 2043


@pytest_asyncio.fixture
async def pg_app(pg_dsn, monkeypatch):
    """Wire the FastAPI app to the test Postgres + bypass auth.

    Mirrors ``test_stale_stats_endpoint_pg.py``'s ``pg_app`` fixture.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Sf() as session:
            yield session

    fake_user = MagicMock()
    fake_user.calculate_permissions = lambda: {
        "backoffice.pipeline_operations": ["view", "edit"],
    }
    fake_user.id = 1
    fake_user.email = "test@example.com"
    fake_user.institutional_id = "TEST-USER"
    fake_user.provider = 0

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


async def _seed_scope(
    Sf, *, module_type_id: int, year: int, with_factors: bool = True
) -> None:
    async with Sf() as s:
        unit = Unit(
            institutional_code=f"RC-{module_type_id}-{year}",
            institutional_id=f"RC-{module_type_id}-{year}-UNIT",
            name="Recompute Stats Test Unit",
            level=1,
        )
        s.add(unit)
        await s.commit()
        assert unit.id is not None

        report = CarbonReport(year=year, unit_id=unit.id)
        s.add(report)
        await s.commit()
        assert report.id is not None

        s.add(
            CarbonReportModule(
                carbon_report_id=report.id,
                module_type_id=module_type_id,
            )
        )
        await s.commit()

        if with_factors:
            # A successful, is_current FACTORS job is what
            # ``filter_scopes_with_current_factors`` treats as "this scope
            # has reference data to compute against" — mirrors the same
            # lookup ``get_recalculation_status_by_year`` uses.
            s.add(
                DataIngestionJob(
                    job_type="factor_ingest",
                    entity_type=EntityType.MODULE_PER_YEAR,
                    module_type_id=module_type_id,
                    year=year,
                    target_type=TargetType.FACTORS,
                    ingestion_method=IngestionMethod.csv,
                    is_current=True,
                    state=IngestionState.FINISHED,
                    result=IngestionResult.SUCCESS,
                )
            )
            await s.commit()


@pytest.mark.asyncio
async def test_recompute_stats_dispatches_one_job_per_scope(pg_app):
    """Two distinct scopes → two dispatched aggregation jobs, one each."""
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2025)
    await _seed_scope(Sf, module_type_id=_MT_B, year=_YEAR_2025)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/v1/sync/admin/recompute-stats")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] == 2
    assert body["skipped"] == 0
    assert len(body["job_ids"]) == 2

    async with Sf() as s:
        jobs = (
            (
                await s.execute(
                    select(DataIngestionJob).where(
                        DataIngestionJob.id.in_(body["job_ids"])  # type: ignore[union-attr]
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {j.module_type_id for j in jobs} == {_MT_A, _MT_B}
    assert all(j.job_type == "aggregation" for j in jobs)
    assert all(j.year == _YEAR_2025 for j in jobs)
    # NOT_STARTED (not yet claimed), RUNNING, or already FINISHED by the
    # fire-and-forget runner racing this assertion — any of these is proof
    # of dispatch, not a fail-fast rejection.
    assert all(
        j.state
        in (IngestionState.NOT_STARTED, IngestionState.RUNNING, IngestionState.FINISHED)
        for j in jobs
    )


@pytest.mark.asyncio
async def test_recompute_stats_filters_by_year(pg_app):
    """``year`` query param limits dispatch to that year's scopes only."""
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2024)
    await _seed_scope(Sf, module_type_id=_MT_B, year=_YEAR_2025)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/v1/sync/admin/recompute-stats", params={"year": _YEAR_2025}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] == 1

    async with Sf() as s:
        job = (
            await s.execute(
                select(DataIngestionJob).where(
                    DataIngestionJob.id == body["job_ids"][0]
                )
            )
        ).scalar_one()
    assert job.module_type_id == _MT_B
    assert job.year == _YEAR_2025


@pytest.mark.asyncio
async def test_recompute_stats_skips_scope_with_active_aggregation(pg_app):
    """An in-flight aggregation for a scope → dedup skip, not a duplicate."""
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2025)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        first = await client.post("/v1/sync/admin/recompute-stats")
        assert first.json()["dispatched"] == 1

        second = await client.post("/v1/sync/admin/recompute-stats")

    assert second.status_code == 200, second.text
    body = second.json()
    # The first call's job is still NOT_STARTED/RUNNING (nothing in this
    # test claims/finishes it), so the dedup index skips the re-trigger.
    assert body["dispatched"] == 0
    assert body["skipped"] == 1


@pytest.mark.asyncio
async def test_recompute_stats_skips_scope_with_no_factors(pg_app):
    """A scope with no successful FACTORS job → skipped, no job dispatched.

    Recomputing against missing reference data just writes zeros, so it
    isn't worth a job (or a pooled DB connection).
    """
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2025, with_factors=False)
    await _seed_scope(Sf, module_type_id=_MT_B, year=_YEAR_2025, with_factors=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/v1/sync/admin/recompute-stats")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] == 1
    assert body["skipped_no_factors"] == 1
    assert len(body["job_ids"]) == 1

    async with Sf() as s:
        job = (
            await s.execute(
                select(DataIngestionJob).where(
                    DataIngestionJob.id == body["job_ids"][0]
                )
            )
        ).scalar_one()
    assert job.module_type_id == _MT_B


@pytest.mark.asyncio
async def test_recompute_stats_filters_by_module_type_id(pg_app):
    """``module_type_id`` query param limits dispatch to that module type."""
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2025)
    await _seed_scope(Sf, module_type_id=_MT_B, year=_YEAR_2025)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/v1/sync/admin/recompute-stats", params={"module_type_id": _MT_A}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dispatched"] == 1

    async with Sf() as s:
        job = (
            await s.execute(
                select(DataIngestionJob).where(
                    DataIngestionJob.id == body["job_ids"][0]
                )
            )
        ).scalar_one()
    assert job.module_type_id == _MT_A
    assert job.year == _YEAR_2025


@pytest.mark.asyncio
async def test_recompute_stats_returns_403_for_user_without_permission(
    pg_dsn, monkeypatch
):
    """Permission gate — behind ``backoffice.pipeline_operations.edit``."""
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
            resp = await client.post("/v1/sync/admin/recompute-stats")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_recompute_stats_returns_zero_with_no_modules(pg_app):
    """No ``carbon_report_modules`` rows → nothing to dispatch."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/v1/sync/admin/recompute-stats")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == {
        "dispatched": 0,
        "skipped": 0,
        "skipped_no_factors": 0,
        "job_ids": [],
    }


async def _seed_plan_scope(
    Sf, *, module_type_id: int, plan_year: int, reference_year: int
) -> int:
    """Seed a Simulator Plan year report and return its module id.

    The report's own ``year`` is the planning target; ``reference_year`` is
    the baseline its entries price against. No FACTORS job is seeded for the
    planning year — by construction there is never one, which is exactly why
    scoping on that year stranded the plan (#2775).
    """
    async with Sf() as s:
        unit = Unit(
            institutional_code=f"RC-PLAN-{module_type_id}-{plan_year}",
            institutional_id=f"RC-PLAN-{module_type_id}-{plan_year}-UNIT",
            name="Recompute Stats Plan Unit",
            level=1,
        )
        s.add(unit)
        await s.commit()
        assert unit.id is not None

        project = CarbonProject(
            unit_id=unit.id,
            carbon_report_type=CarbonReportType.SIMULATOR_PLAN,
        )
        s.add(project)
        await s.commit()
        assert project.id is not None

        report = CarbonReport(
            year=plan_year,
            reference_year=reference_year,
            unit_id=unit.id,
            carbon_project_id=project.id,
        )
        s.add(report)
        await s.commit()
        assert report.id is not None

        module = CarbonReportModule(
            carbon_report_id=report.id,
            module_type_id=module_type_id,
        )
        s.add(module)
        await s.commit()
        assert module.id is not None
        return module.id


@pytest.mark.asyncio
async def test_recompute_stats_scopes_plan_by_reference_year(pg_app):
    """#2775 — a plan folds into its reference-year scope, not its own year.

    Before the fix the plan raised a ``(module_type, 2043)`` scope; 2043 has
    no FACTORS job, so it was counted in ``skipped_no_factors`` and no job
    ever reached the plan's modules. After it, the plan shares the 2025
    scope the Calculator report already dispatches — same job count.
    """
    Sf = pg_app["factory"]
    await _seed_scope(Sf, module_type_id=_MT_A, year=_YEAR_2025)
    await _seed_plan_scope(
        Sf,
        module_type_id=_MT_A,
        plan_year=_PLAN_YEAR,
        reference_year=_YEAR_2025,
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post("/v1/sync/admin/recompute-stats")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # The plan adds no scope of its own: one job, and nothing stranded.
    assert body["dispatched"] == 1
    assert body["skipped_no_factors"] == 0

    async with Sf() as s:
        jobs = (
            (
                await s.execute(
                    select(DataIngestionJob).where(
                        DataIngestionJob.id.in_(body["job_ids"])  # type: ignore[union-attr]
                    )
                )
            )
            .scalars()
            .all()
        )
    assert [j.year for j in jobs] == [_YEAR_2025]
    # The flag is what lets the handler widen its module slice to reach the
    # plan; without it a dispatched job still collects nothing for it.
    assert all((j.meta or {})["config"]["include_reference_year_reports"] for j in jobs)


@pytest.mark.asyncio
async def test_reference_year_slice_collects_plan_modules(pg_app):
    """#2775 — the admin trigger's module query collects the plan's modules.

    ``list_by_module_type_and_year`` is what ``aggregation_handler`` calls to
    turn its ``(module_type_id, year)`` job into a module list. Matching on
    the report's own year left the plan out of every slice, so even a
    dispatched job recomputed nothing for it. Only the admin trigger opts
    into the widened slice, via ``include_reference_year``.
    """
    Sf = pg_app["factory"]
    plan_module_id = await _seed_plan_scope(
        Sf,
        module_type_id=_MT_A,
        plan_year=_PLAN_YEAR,
        reference_year=_YEAR_2025,
    )

    async with Sf() as s:
        repo = CarbonReportModuleRepository(s)
        widened = await repo.list_by_module_type_and_year(
            module_type_id=_MT_A, year=_YEAR_2025, include_reference_year=True
        )
        narrow = await repo.list_by_module_type_and_year(
            module_type_id=_MT_A, year=_YEAR_2025
        )
        planning_slice = await repo.list_by_module_type_and_year(
            module_type_id=_MT_A, year=_PLAN_YEAR, include_reference_year=True
        )

    assert plan_module_id in [m.id for m in widened]
    # The recalc-chained aggregation keeps the narrow slice: widening it would
    # route plan modules through ``emptied_module_ids`` and bump validated
    # plans to IN_PROGRESS on every factor upload (#2775).
    assert plan_module_id not in [m.id for m in narrow]
    # The planning year is not a slice key at all once the reference year is set.
    assert plan_module_id not in [m.id for m in planning_slice]
