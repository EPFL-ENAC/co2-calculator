from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.carbon_project import CarbonProject
from app.models.carbon_report import CarbonReport, CarbonReportType
from app.models.user import User, UserProvider
from app.models.year_configuration import YearConfiguration
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


# ── Simulator Explore (#2656): always the latest started year, never its own ──


async def _add_explore_user(session, provider: UserProvider = UserProvider.DEFAULT):
    user = User(institutional_id="explore-user", email="explore@x", provider=provider)
    session.add(user)
    await session.flush()
    return user


async def _add_year_config(
    session, year: int, provider: UserProvider, is_started: bool
):
    session.add(YearConfiguration(year=year, provider=provider, is_started=is_started))
    await session.flush()


@pytest.mark.asyncio
async def test_explore_uses_last_year_when_started(async_session):
    this_year = datetime.now(UTC).year
    user = await _add_explore_user(async_session)
    explore = await _add_project(async_session, CarbonReportType.SIMULATOR_EXPLORE)
    explore.created_by = user.id
    await async_session.flush()
    await _add_year_config(async_session, this_year - 1, user.provider, True)
    # Own year (the sandbox's creation year) must be ignored.
    report = await _add_report(async_session, explore, this_year)

    assert await resolve_factor_year(async_session, report) == this_year - 1


@pytest.mark.asyncio
async def test_explore_falls_back_two_years_when_last_year_not_started(async_session):
    this_year = datetime.now(UTC).year
    user = await _add_explore_user(async_session)
    explore = await _add_project(async_session, CarbonReportType.SIMULATOR_EXPLORE)
    explore.created_by = user.id
    await async_session.flush()
    await _add_year_config(async_session, this_year - 1, user.provider, False)
    await _add_year_config(async_session, this_year - 2, user.provider, True)
    report = await _add_report(async_session, explore, this_year)

    assert await resolve_factor_year(async_session, report) == this_year - 2


@pytest.mark.asyncio
async def test_explore_raises_when_neither_year_started(async_session):
    this_year = datetime.now(UTC).year
    user = await _add_explore_user(async_session)
    explore = await _add_project(async_session, CarbonReportType.SIMULATOR_EXPLORE)
    explore.created_by = user.id
    await async_session.flush()
    report = await _add_report(async_session, explore, this_year)

    with pytest.raises(ValueError, match=f"{this_year - 1}.*{this_year - 2}"):
        await resolve_factor_year(async_session, report)
