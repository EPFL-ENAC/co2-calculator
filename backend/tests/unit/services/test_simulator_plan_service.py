import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.simulator_plan import SimulatorPlanUpdate
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
    async_session = sessionmaker(
        engine, class_=SQLModelAsyncSession, expire_on_commit=False
    )
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


# ── update_plan (rename) ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rename_plan(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="old-name")
    renamed = await service.update_plan(
        created.id, SimulatorPlanUpdate(name="new-name")
    )

    assert renamed is not None
    assert renamed.name == "new-name"
    assert renamed.creator_name == "Ada Lovelace"
    assert await service.get_plan_by_name(1, "old-name") is None
    assert await service.get_plan_by_name(1, "new-name") is not None


@pytest.mark.asyncio
async def test_rename_plan_same_name_is_noop(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="same")
    renamed = await service.update_plan(created.id, SimulatorPlanUpdate(name="same"))
    assert renamed is not None
    assert renamed.name == "same"


@pytest.mark.asyncio
async def test_rename_plan_collision_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await service.create_plan(unit_id=1, user=user, name="taken")
    created = await service.create_plan(unit_id=1, user=user, name="mine")
    with pytest.raises(ValueError):
        await service.update_plan(created.id, SimulatorPlanUpdate(name="taken"))


@pytest.mark.asyncio
async def test_rename_plan_missing_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    assert await service.update_plan(9999, SimulatorPlanUpdate(name="whatever")) is None


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


# ── update_plan (year range sync) ─────────────────────────────────────────────


async def _plan_years(service, plan_id):
    years = await service.list_plan_years(plan_id)
    assert years is not None
    return [y.year for y in years]


@pytest.mark.asyncio
async def test_setting_year_range_creates_reports_with_modules(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")

    updated = await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2027, end_year=2029)
    )
    assert updated is not None
    assert (updated.start_year, updated.end_year) == (2027, 2029)

    years = await service.list_plan_years(created.id)
    assert years is not None
    assert [y.year for y in years] == [2027, 2028, 2029]
    # Each plan-year report gets its full module set.
    assert all(len(y.modules) > 0 for y in years)
    assert all(m.is_active for y in years for m in y.modules)


@pytest.mark.asyncio
async def test_shrinking_year_range_deletes_out_of_range_reports(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2027, end_year=2030)
    )

    await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2028, end_year=2029)
    )
    assert await _plan_years(service, created.id) == [2028, 2029]


@pytest.mark.asyncio
async def test_growing_year_range_keeps_existing_reports(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    first = await service.list_plan_years(created.id)
    assert first is not None

    await service.update_plan(created.id, SimulatorPlanUpdate(end_year=2028))
    years = await service.list_plan_years(created.id)
    assert years is not None
    assert [y.year for y in years] == [2027, 2028]
    # The pre-existing 2027 report survives (same id).
    assert years[0].id == first[0].id


@pytest.mark.asyncio
async def test_inverted_year_range_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    with pytest.raises(ValueError):
        await service.update_plan(
            created.id, SimulatorPlanUpdate(start_year=2030, end_year=2027)
        )


# ── set_reference_year ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_reference_year(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )

    result = await service.set_reference_year(created.id, 2027, 2024)
    assert result is not None
    assert result.reference_year == 2024

    years = await service.list_plan_years(created.id)
    assert years is not None
    assert years[0].reference_year == 2024


@pytest.mark.asyncio
async def test_set_reference_year_missing_year_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    assert await service.set_reference_year(created.id, 2031, 2024) is None


# ── prefill_module_from_reference (snapshot copy) ─────────────────────────────


async def _calculator_report_with_process_entries(service, async_session, year=2024):
    """Calculator report for unit 1 with two process-emissions entries."""
    report = await service.report_service.create(
        CarbonReportCreate(year=year, unit_id=1)
    )
    modules = await service.report_service.module_service.list_modules(report.id)
    module = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entries = []
    for quantity in (5.0, 7.0):
        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            carbon_report_module_id=module.id,
            data={"category": "co2", "quantity": quantity},
        )
        async_session.add(entry)
        entries.append(entry)
    await async_session.flush()
    return report, module, entries


async def _plan_year_report(service, plan_id, year=2027, reference_year=2024):
    await service.update_plan(
        plan_id, SimulatorPlanUpdate(start_year=year, end_year=year)
    )
    await service.set_reference_year(plan_id, year, reference_year)
    reports = await service.repo.list_reports_for_project(plan_id)
    return next(r for r in reports if r.year == year)


@pytest.mark.asyncio
async def test_prefill_copies_reference_entries_at_100_percent(async_session, user):
    service = SimulatorPlanService(async_session)
    _, _, src_entries = await _calculator_report_with_process_entries(
        service, async_session
    )
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id)

    copied = await service.prefill_module_from_reference(
        report, int(ModuleTypeEnum.process_emissions)
    )
    assert copied == 2

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 2
    assert all(r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value for r in rows)
    assert all(r.data["percentage_of_last_year"] == 100 for r in rows)
    assert {r.data["source_data_entry_id"] for r in rows} == {e.id for e in src_entries}
    # Snapshot keeps the reference quantities.
    assert {r.data["quantity"] for r in rows} == {5.0, 7.0}


@pytest.mark.asyncio
async def test_prefill_is_idempotent_and_keeps_user_rows(async_session, user):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session)
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id)
    await service.prefill_module_from_reference(
        report, int(ModuleTypeEnum.process_emissions)
    )

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    user_row = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        carbon_report_module_id=plan_module.id,
        source=DataEntrySourceEnum.USER_MANUAL.value,
        data={"category": "ch4", "quantity": 1.0},
    )
    async_session.add(user_row)
    await async_session.flush()

    copied = await service.prefill_module_from_reference(
        report, int(ModuleTypeEnum.process_emissions)
    )
    assert copied == 2

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    snapshots = [
        r for r in rows if r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value
    ]
    manuals = [r for r in rows if r.source == DataEntrySourceEnum.USER_MANUAL.value]
    assert len(snapshots) == 2  # replaced, not accumulated
    assert len(manuals) == 1  # user rows survive


@pytest.mark.asyncio
async def test_prefill_without_reference_year_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session)
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    await service.update_plan(
        plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    reports = await service.repo.list_reports_for_project(plan.id)
    with pytest.raises(ValueError, match="reference year"):
        await service.prefill_module_from_reference(
            reports[0], int(ModuleTypeEnum.process_emissions)
        )


@pytest.mark.asyncio
async def test_reference_year_change_resnapshots_prefilled_modules(async_session, user):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    # Second Calculator year with a single, different entry.
    report_2025 = await service.report_service.create(
        CarbonReportCreate(year=2025, unit_id=1)
    )
    modules_2025 = await service.report_service.module_service.list_modules(
        report_2025.id
    )
    module_2025 = next(
        m
        for m in modules_2025
        if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entry_2025 = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        carbon_report_module_id=module_2025.id,
        data={"category": "n2o", "quantity": 3.0},
    )
    async_session.add(entry_2025)
    await async_session.flush()

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)
    await service.prefill_module_from_reference(
        report, int(ModuleTypeEnum.process_emissions)
    )

    await service.set_reference_year(plan.id, 2027, 2025)

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 1
    assert rows[0].data["quantity"] == 3.0
    assert rows[0].data["source_data_entry_id"] == entry_2025.id
