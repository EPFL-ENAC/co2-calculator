import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.repositories.data_entry_repo import (
    DataEntryRepository,
    reference_year_filter,
)
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


@pytest.mark.asyncio
async def test_set_reference_year_auto_prefills_prefilled_modules(async_session, user):
    """Setting the reference year auto-prefills prefilled modules; others stay empty.

    There is no manual prefill trigger anymore — set_reference_year is the only
    entry point, and it must snapshot every prefilled-behavior module.
    """
    service = SimulatorPlanService(async_session)
    ref_report, _, _ = await _calculator_report_with_process_entries(
        service, async_session
    )
    # A non-prefilled module (purchase) with a reference entry that must NOT copy.
    modules = await service.report_service.module_service.list_modules(ref_report.id)
    purchase_module = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.purchase)
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.scientific_equipment.value,
            carbon_report_module_id=purchase_module.id,
            data={"amount": 10.0},
        )
    )
    await async_session.flush()

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    # No manual prefill call: the reference-year set is the only trigger.
    report = await _plan_year_report(service, plan.id, reference_year=2024)

    module_service = service.report_service.module_service
    entry_repo = DataEntryRepository(async_session)

    process_module = await module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    process_rows = await entry_repo.list_by_module(process_module.id)
    assert len(process_rows) == 2
    assert all(
        r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value for r in process_rows
    )

    plan_purchase = await module_service.get_module(
        report.id, int(ModuleTypeEnum.purchase)
    )
    assert await entry_repo.list_by_module(plan_purchase.id) == []


@pytest.mark.asyncio
async def test_set_reference_year_without_calc_report_is_noop(async_session, user):
    """A reference year with no Calculator report still sets, prefilling nothing."""
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await service.update_plan(
        created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    result = await service.set_reference_year(created.id, 2027, 2024)
    assert result is not None and result.reference_year == 2024


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
    # Setting the reference year already prefills every prefilled module.
    report = await _plan_year_report(service, plan.id)

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 2
    assert all(r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value for r in rows)
    assert all(r.data["reference_year"] == 2024 for r in rows)
    assert all(r.data["percentage_of_reference_year"] == 100 for r in rows)
    assert {r.data["source_data_entry_id"] for r in rows} == {e.id for e in src_entries}
    # Snapshot keeps the reference quantities.
    assert {r.data["quantity"] for r in rows} == {5.0, 7.0}


@pytest.mark.asyncio
async def test_prefill_leaves_an_already_prefilled_baseline_alone(async_session, user):
    """Re-copying a baseline would discard the sliders set under it."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session)
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id)

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
    assert copied == 0

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    snapshots = [
        r for r in rows if r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value
    ]
    manuals = [r for r in rows if r.source == DataEntrySourceEnum.USER_MANUAL.value]
    assert len(snapshots) == 2  # not duplicated
    assert len(manuals) == 1  # user rows survive
    # A hand-added row belongs to the plan, not to a baseline.
    assert "reference_year" not in manuals[0].data


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


async def _second_calculator_year(service, async_session):
    """A 2025 Calculator report for unit 1 with a single process entry."""
    report = await service.report_service.create(
        CarbonReportCreate(year=2025, unit_id=1)
    )
    modules = await service.report_service.module_service.list_modules(report.id)
    module = next(
        m for m in modules if m.module_type_id == int(ModuleTypeEnum.process_emissions)
    )
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        carbon_report_module_id=module.id,
        data={"category": "n2o", "quantity": 3.0},
    )
    async_session.add(entry)
    await async_session.flush()
    return entry


async def _visible_rows(async_session, plan_module_id, reference_year):
    """The module's rows as the table, the totals and the chart see them.

    Applies the same filter the repo applies when a caller passes the report's
    live baseline.
    """
    result = await async_session.execute(
        select(DataEntry).where(
            col(DataEntry.carbon_report_module_id) == plan_module_id,
            reference_year_filter(reference_year),
        )
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_reference_year_change_keeps_the_previous_baseline_rows(
    async_session, user
):
    """Nothing is deleted: the old baseline's rows stay, dormant."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    entry_2025 = await _second_calculator_year(service, async_session)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)

    await service.set_reference_year(plan.id, 2027, 2025)

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    stored = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert sorted(r.data["reference_year"] for r in stored) == [2024, 2024, 2025]

    visible = await _visible_rows(async_session, plan_module.id, 2025)
    assert len(visible) == 1
    assert visible[0].data["quantity"] == 3.0
    assert visible[0].data["source_data_entry_id"] == entry_2025.id


@pytest.mark.asyncio
async def test_switching_back_restores_the_sliders_of_that_baseline(
    async_session, user
):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    await _second_calculator_year(service, async_session)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)
    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    rows_2024 = await _visible_rows(async_session, plan_module.id, 2024)
    rows_2024[0].data = {
        **rows_2024[0].data,
        "percentage_of_reference_year": 40,
        "quantity": 99.0,
    }
    async_session.add(rows_2024[0])
    await async_session.flush()

    await service.set_reference_year(plan.id, 2027, 2025)
    await service.set_reference_year(plan.id, 2027, 2024)

    visible = await _visible_rows(async_session, plan_module.id, 2024)
    assert len(visible) == 2
    edited = next(r for r in visible if r.id == rows_2024[0].id)
    assert edited.data["percentage_of_reference_year"] == 40
    assert edited.data["quantity"] == 99.0


@pytest.mark.asyncio
async def test_hand_added_rows_show_under_every_baseline(async_session, user):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    await _second_calculator_year(service, async_session)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)
    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            carbon_report_module_id=plan_module.id,
            source=DataEntrySourceEnum.USER_MANUAL.value,
            data={"category": "ch4", "quantity": 1.0},
        )
    )
    await async_session.flush()

    await service.set_reference_year(plan.id, 2027, 2025)

    visible = await _visible_rows(async_session, plan_module.id, 2025)
    manual = [r for r in visible if r.source == DataEntrySourceEnum.USER_MANUAL.value]
    assert len(manual) == 1
    assert len(visible) == 2  # the manual row + the 2025 snapshot


@pytest.mark.asyncio
async def test_calculator_rows_are_never_hidden(async_session, user):
    """Outside the planner the filter is a no-op: no row carries a baseline."""
    service = SimulatorPlanService(async_session)
    _, calc_module, _ = await _calculator_report_with_process_entries(
        service, async_session, year=2024
    )

    visible = await _visible_rows(async_session, calc_module.id, None)

    assert len(visible) == 2


@pytest.mark.asyncio
async def test_duplicate_plan_syncs_year_reports(async_session, user):
    """A duplicated plan opens with the same year sections as its source."""
    service = SimulatorPlanService(async_session)
    source = await service.create_plan(unit_id=1, user=user, name="source")
    await service.update_plan(
        source.id, SimulatorPlanUpdate(start_year=2027, end_year=2029)
    )

    copy = await service.duplicate_plan(source.id, user)
    assert copy is not None
    assert (copy.start_year, copy.end_year) == (2027, 2029)

    years = await service.list_plan_years(copy.id)
    assert years is not None
    assert [y.year for y in years] == [2027, 2028, 2029]
    assert all(len(y.modules) > 0 for y in years)
