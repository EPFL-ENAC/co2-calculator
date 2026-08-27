import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.utils.factor_year import resolve_factor_year

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

UNIT_ID = 1


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(
        engine, class_=SQLModelAsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
    await engine.dispose()


async def _add_project(session, report_type: CarbonReportType) -> CarbonProject:
    project = CarbonProject(unit_id=UNIT_ID, carbon_report_type=report_type)
    session.add(project)
    await session.flush()
    return project


async def _add_report(session, project: CarbonProject, year: int, **kw) -> CarbonReport:
    report = CarbonReport(
        unit_id=UNIT_ID, year=year, carbon_project_id=project.id, **kw
    )
    session.add(report)
    await session.flush()
    return report


@pytest.mark.asyncio
async def test_reference_year_wins(async_session):
    plan = await _add_project(async_session, CarbonReportType.SIMULATOR_PLAN)
    report = await _add_report(async_session, plan, 2030, reference_year=2024)

    assert await resolve_factor_year(async_session, report) == 2024


@pytest.mark.asyncio
async def test_plan_without_reference_year_uses_latest_calculator_year(async_session):
    calculator = await _add_project(async_session, CarbonReportType.CALCULATOR)
    await _add_report(async_session, calculator, 2023)
    await _add_report(async_session, calculator, 2025)
    plan = await _add_project(async_session, CarbonReportType.SIMULATOR_PLAN)
    report = await _add_report(async_session, plan, 2030)

    assert await resolve_factor_year(async_session, report) == 2025


@pytest.mark.asyncio
async def test_plan_without_any_calculator_report_uses_own_year(async_session):
    plan = await _add_project(async_session, CarbonReportType.SIMULATOR_PLAN)
    report = await _add_report(async_session, plan, 2030)

    assert await resolve_factor_year(async_session, report) == 2030


@pytest.mark.asyncio
async def test_calculator_report_uses_own_year(async_session):
    calculator = await _add_project(async_session, CarbonReportType.CALCULATOR)
    await _add_report(async_session, calculator, 2025)
    report = await _add_report(async_session, calculator, 2023)

    assert await resolve_factor_year(async_session, report) == 2023
