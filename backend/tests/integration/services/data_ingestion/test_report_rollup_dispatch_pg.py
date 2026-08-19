"""The report rollup runs after the response, not inside it (#2050 J4).

A report's stats scan every module in the report, so the work grows with the
report rather than with the entry a user just created — and nothing the caller
reads back depends on it. Interactive writes therefore defer it; background
jobs, which have nobody waiting, keep rolling up inline.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport
from app.models.module_type import ModuleTypeEnum
from app.services.carbon_report_module_service import CarbonReportModuleService

pytestmark = pytest.mark.asyncio


async def _seed(session, make_unit, make_carbon_report, make_carbon_report_module):
    unit = await make_unit(session)
    report = await make_carbon_report(session, unit_id=unit.id, year=2025)
    module = await make_carbon_report_module(
        session,
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.headcount.value,
    )
    await session.commit()
    return report.id, module.id


async def test_deferred_rollup_leaves_the_report_for_the_caller(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module, monkeypatch
):
    """With ``defer_report_rollup``, module stats are written and the report is
    left untouched — with its id reported back so the caller can dispatch.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            report_id, module_id = await _seed(
                session, make_unit, make_carbon_report, make_carbon_report_module
            )

        async with Sf() as session:
            service = CarbonReportModuleService(session)
            await service.recompute_stats(module_id, defer_report_rollup=True)
            await session.commit()
            assert service.stale_report_ids == {report_id}

        async with Sf() as session:
            report = await session.get(CarbonReport, report_id)
            assert report is not None
            # Deliberately not rolled up yet.
            assert report.last_updated is None

        # And the detached task closes the gap. It opens its own session via
        # app.db.SessionLocal (the request's is gone by then), which points at
        # the configured database — so the test has to aim it at the container.
        from app.tasks import report_rollup

        monkeypatch.setattr(report_rollup, "SessionLocal", Sf)
        await report_rollup.recompute_report_stats_detached([report_id])

        async with Sf() as session:
            report = await session.get(CarbonReport, report_id)
            assert report is not None
            assert report.last_updated is not None
    finally:
        await engine.dispose()


async def test_background_callers_still_roll_up_inline(
    pg_dsn, make_unit, make_carbon_report, make_carbon_report_module
):
    """The default is unchanged: a caller with nobody waiting on it keeps
    rolling the report up in the same transaction.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            report_id, module_id = await _seed(
                session, make_unit, make_carbon_report, make_carbon_report_module
            )

        async with Sf() as session:
            await CarbonReportModuleService(session).recompute_stats(module_id)
            await session.commit()

        async with Sf() as session:
            report = await session.get(CarbonReport, report_id)
            assert report is not None
            assert report.last_updated is not None
    finally:
        await engine.dispose()
