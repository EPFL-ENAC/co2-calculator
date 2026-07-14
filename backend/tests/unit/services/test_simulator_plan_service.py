import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession as SAAsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.models.user import User
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_service import CarbonReportService
from app.services.simulator_plan_service import (
    SimulatorPlanService,
    _next_available_name,
)

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)  # Ensure a clean slate
        await conn.run_sync(SQLModel.metadata.create_all)
    async_session = sessionmaker(engine, class_=SAAsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(async_session):
    db_user = User(
        institutional_id="100001",
        email="ada@example.com",
        display_name="Ada Lovelace",
    )
    async_session.add(db_user)
    await async_session.flush()
    return db_user


# ── _next_available_name (pure function) ──────────────────────────────────────


def test_next_available_name_returns_base_when_free():
    assert _next_available_name("new-project", set()) == "new-project"


def test_next_available_name_appends_suffixes():
    assert _next_available_name("new-project", {"new-project"}) == "new-project-2"
    assert (
        _next_available_name("new-project", {"new-project", "new-project-2"})
        == "new-project-3"
    )


def test_next_available_name_fills_gaps():
    assert (
        _next_available_name("new-project", {"new-project", "new-project-3"})
        == "new-project-2"
    )


# ── create_plan ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_plan_default_name_sequence(async_session, user):
    service = SimulatorPlanService(async_session)
    first = await service.create_plan(unit_id=1, user=user)
    second = await service.create_plan(unit_id=1, user=user)

    assert first.name == "new-project"
    assert second.name == "new-project-2"
    assert first.unit_id == 1
    assert first.created_by == user.id
    assert first.created_at is not None
    assert first.creator_name == "Ada Lovelace"


@pytest.mark.asyncio
async def test_create_plan_default_names_are_per_unit(async_session, user):
    service = SimulatorPlanService(async_session)
    first = await service.create_plan(unit_id=1, user=user)
    other_unit = await service.create_plan(unit_id=2, user=user)

    assert first.name == "new-project"
    assert other_unit.name == "new-project"


@pytest.mark.asyncio
async def test_create_plan_explicit_name_collision_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await service.create_plan(unit_id=1, user=user, name="my-plan")
    with pytest.raises(ValueError):
        await service.create_plan(unit_id=1, user=user, name="my-plan")


# ── get_plan_by_name / list_plans ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_plan_by_name(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="my-plan")
    fetched = await service.get_plan_by_name(1, "my-plan")

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.creator_name == "Ada Lovelace"
    assert await service.get_plan_by_name(1, "unknown") is None
    assert await service.get_plan_by_name(2, "my-plan") is None


@pytest.mark.asyncio
async def test_list_plans_scoped_to_unit(async_session, user):
    service = SimulatorPlanService(async_session)
    await service.create_plan(unit_id=1, user=user, name="a")
    await service.create_plan(unit_id=1, user=user, name="b")
    await service.create_plan(unit_id=2, user=user, name="c")

    plans = await service.list_plans(1)
    assert {p.name for p in plans} == {"a", "b"}


# ── rename_plan ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_plan(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="old-name")
    renamed = await service.rename_plan(created.id, "new-name")

    assert renamed is not None
    assert renamed.name == "new-name"
    assert renamed.creator_name == "Ada Lovelace"
    assert await service.get_plan_by_name(1, "old-name") is None
    assert await service.get_plan_by_name(1, "new-name") is not None


@pytest.mark.asyncio
async def test_rename_plan_same_name_is_noop(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="same")
    renamed = await service.rename_plan(created.id, "same")
    assert renamed is not None
    assert renamed.name == "same"


@pytest.mark.asyncio
async def test_rename_plan_collision_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await service.create_plan(unit_id=1, user=user, name="taken")
    created = await service.create_plan(unit_id=1, user=user, name="mine")
    with pytest.raises(ValueError):
        await service.rename_plan(created.id, "taken")


@pytest.mark.asyncio
async def test_rename_plan_missing_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    assert await service.rename_plan(9999, "whatever") is None


# ── duplicate_plan ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_plan_suffix_chain(async_session, user):
    service = SimulatorPlanService(async_session)
    original = await service.create_plan(unit_id=1, user=user, name="foo")

    first_copy = await service.duplicate_plan(original.id, user)
    second_copy = await service.duplicate_plan(original.id, user)

    assert first_copy is not None and first_copy.name == "foo-2"
    assert second_copy is not None and second_copy.name == "foo-3"
    assert first_copy.created_by == user.id
    assert first_copy.creator_name == "Ada Lovelace"


@pytest.mark.asyncio
async def test_duplicate_plan_missing_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    assert await service.duplicate_plan(9999, user) is None


# ── delete_plan ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_plan(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="doomed")

    assert await service.delete_plan(created.id) is True
    assert await service.get_plan_by_name(1, "doomed") is None
    assert await service.delete_plan(created.id) is False


@pytest.mark.asyncio
async def test_delete_plan_cascades_attached_reports(async_session, user):
    """A plan with carbon reports attached deletes them (and their modules)."""
    plan_service = SimulatorPlanService(async_session)
    report_service = CarbonReportService(async_session)

    plan = await plan_service.create_plan(unit_id=1, user=user, name="with-report")
    report = await report_service.create(
        CarbonReportCreate(year=2026, unit_id=1, carbon_project_id=plan.id)
    )

    assert await plan_service.delete_plan(plan.id) is True
    assert await report_service.get(report.id) is None
    modules = await report_service.module_service.list_modules(report.id)
    assert len(modules) == 0
