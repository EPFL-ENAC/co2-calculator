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


async def _set_ref(service, plan_id, year, reference_year, *, is_grant=False):
    """``set_reference_year`` plus the prefill its job now runs (Track F4).

    The route defers prefill to ``simulator_plan_prefill``; these tests
    exercise the combined effect, so they run both halves and re-read the
    year afterwards (the first read is built before prefill happens).
    """
    out = await service.set_reference_year(
        plan_id, year, reference_year, is_grant=is_grant
    )
    if out is None:
        return None
    _, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    years = await service.list_plan_years(plan_id)
    return next(
        (y for y in years or [] if y.year == year and y.is_grant == is_grant), None
    )


async def _update_plan(service, plan_id, update):
    """``update_plan`` plus the prefill its job now runs (Track F4)."""
    out = await service.update_plan(plan_id, update)
    if out is None:
        return None
    result, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    return result


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


# ── get_plan / list_plans ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_plan(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="my-plan")
    fetched = await service.get_plan(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.creator_name == "Ada Lovelace"
    assert await service.get_plan(9999) is None


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
    renamed = await _update_plan(
        service, created.id, SimulatorPlanUpdate(name="new-name")
    )

    assert renamed is not None
    assert renamed.name == "new-name"
    assert renamed.creator_name == "Ada Lovelace"
    refetched = await service.get_plan(created.id)
    assert refetched is not None
    assert refetched.name == "new-name"


@pytest.mark.asyncio
async def test_rename_plan_same_name_is_noop(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="same")
    renamed = await _update_plan(service, created.id, SimulatorPlanUpdate(name="same"))
    assert renamed is not None
    assert renamed.name == "same"


@pytest.mark.asyncio
async def test_rename_plan_collision_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await service.create_plan(unit_id=1, user=user, name="taken")
    created = await service.create_plan(unit_id=1, user=user, name="mine")
    with pytest.raises(ValueError):
        await _update_plan(service, created.id, SimulatorPlanUpdate(name="taken"))


@pytest.mark.asyncio
async def test_rename_plan_missing_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    assert (
        await _update_plan(service, 9999, SimulatorPlanUpdate(name="whatever")) is None
    )


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
    assert await service.get_plan(created.id) is None
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

    updated = await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2029)
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
async def test_year_range_defaults_reference_year_on_new_reports(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")

    await _update_plan(
        service,
        created.id,
        SimulatorPlanUpdate(
            start_year=2027, end_year=2028, default_reference_year=2026
        ),
    )
    years = await service.list_plan_years(created.id)
    assert years is not None
    assert [y.reference_year for y in years] == [2026, 2026]

    # Growing the range only defaults the new report; 2027-2028 keep theirs.
    await _update_plan(
        service,
        created.id,
        SimulatorPlanUpdate(end_year=2029, default_reference_year=2025),
    )
    years = await service.list_plan_years(created.id)
    assert years is not None
    assert [(y.year, y.reference_year) for y in years] == [
        (2027, 2026),
        (2028, 2026),
        (2029, 2025),
    ]


@pytest.mark.asyncio
async def test_year_range_without_default_leaves_reference_unset(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")

    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    years = await service.list_plan_years(created.id)
    assert years is not None
    assert [y.reference_year for y in years] == [None]


@pytest.mark.asyncio
async def test_shrinking_year_range_deletes_out_of_range_reports(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2030)
    )

    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2028, end_year=2029)
    )
    assert await _plan_years(service, created.id) == [2028, 2029]


@pytest.mark.asyncio
async def test_growing_year_range_keeps_existing_reports(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    first = await service.list_plan_years(created.id)
    assert first is not None

    await _update_plan(service, created.id, SimulatorPlanUpdate(end_year=2028))
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
        await _update_plan(
            service, created.id, SimulatorPlanUpdate(start_year=2030, end_year=2027)
        )


# ── set_reference_year ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_reference_year(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )

    result = await _set_ref(service, created.id, 2027, 2024)
    assert result is not None
    assert result.reference_year == 2024

    years = await service.list_plan_years(created.id)
    assert years is not None
    assert years[0].reference_year == 2024


@pytest.mark.asyncio
async def test_set_reference_year_missing_year_returns_none(async_session, user):
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    assert await _set_ref(service, created.id, 2031, 2024) is None


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
async def test_remove_reference_year_wipes_prefilled_modules(async_session, user):
    """Removing the baseline empties the prefilled modules, same as a change."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session)
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id)

    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    entry_repo = DataEntryRepository(async_session)
    assert len(await entry_repo.list_by_module(plan_module.id)) == 2

    result = await _set_ref(service, plan.id, 2027, None)
    assert result is not None and result.reference_year is None
    assert await entry_repo.list_by_module(plan_module.id) == []


@pytest.mark.asyncio
async def test_set_reference_year_grant_clears_but_does_not_rebuild_rf_and_travel(
    async_session, user
):
    """Grant reports never prefill research_facilities/professional_travel
    (#1980/#2018 — left empty for the user's own selection), but stale rows
    from a previous baseline must still be cleared out.

    Regression test for plan #2050 Track D finding 1: the upfront
    ``_clear_module_entries`` call now only covers modules that won't
    self-clear when rebuilt below. These two module types never reach that
    rebuild step for a grant report (skipped in the loop), so if the
    upfront-clear exclusion logic doesn't account for that, their old
    entries would never get cleared at all. The reference-year Calculator
    report also carries RF/travel entries here — if the exclusion instead
    broke by *including* these two in ``will_rebuild`` (so they wrongly
    self-clear-then-rebuild via ``prefill_module_from_reference`` like an
    ordinary module), the test's own fixture would populate them right back
    up, catching that failure mode too, not just an unfixed stale-row one.
    """
    service = SimulatorPlanService(async_session)
    ref_report, _, _ = await _calculator_report_with_process_entries(
        service, async_session
    )
    ref_modules = await service.report_service.module_service.list_modules(
        ref_report.id
    )
    ref_rf_module = next(
        m
        for m in ref_modules
        if m.module_type_id == int(ModuleTypeEnum.research_facilities)
    )
    ref_travel_module = next(
        m
        for m in ref_modules
        if m.module_type_id == int(ModuleTypeEnum.professional_travel)
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            carbon_report_module_id=ref_rf_module.id,
            data={"name": "reference platform"},
        )
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=ref_travel_module.id,
            data={"name": "reference trip"},
        )
    )
    await async_session.flush()

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    grant_report = await service.report_service.create(
        CarbonReportCreate(
            year=2027, unit_id=1, carbon_project_id=plan.id, is_grant=True
        )
    )
    modules = await service.report_service.module_service.list_modules(grant_report.id)
    rf_module = next(
        m
        for m in modules
        if m.module_type_id == int(ModuleTypeEnum.research_facilities)
    )
    travel_module = next(
        m
        for m in modules
        if m.module_type_id == int(ModuleTypeEnum.professional_travel)
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            carbon_report_module_id=rf_module.id,
            data={"name": "stale"},
        )
    )
    async_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=travel_module.id,
            data={"name": "stale trip"},
        )
    )
    await async_session.flush()

    result = await _set_ref(service, plan.id, 2027, 2024, is_grant=True)
    assert result is not None

    entry_repo = DataEntryRepository(async_session)
    assert await entry_repo.list_by_module(rf_module.id) == [], (
        "stale research_facilities rows survived a reference-year change on "
        "a grant report — the upfront clear must still cover modules that "
        "are excluded from rebuild, not just modules absent from `rebuilt`"
    )
    assert await entry_repo.list_by_module(travel_module.id) == [], (
        "stale professional_travel rows survived a reference-year change "
        "on a grant report"
    )


@pytest.mark.asyncio
async def test_set_reference_year_without_calc_report_is_noop(async_session, user):
    """A reference year with no Calculator report still sets, prefilling nothing."""
    service = SimulatorPlanService(async_session)
    created = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, created.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
    )
    result = await _set_ref(service, created.id, 2027, 2024)
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
            data={"category": "co2", "quantity_kg": quantity},
        )
        async_session.add(entry)
        entries.append(entry)
    await async_session.flush()
    return report, module, entries


async def _plan_year_report(service, plan_id, year=2027, reference_year=2024):
    await _update_plan(
        service, plan_id, SimulatorPlanUpdate(start_year=year, end_year=year)
    )
    await _set_ref(service, plan_id, year, reference_year)
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
    assert all(r.data["percentage_of_reference_year"] == 100 for r in rows)
    assert {r.data["source_data_entry_id"] for r in rows} == {e.id for e in src_entries}
    # Snapshot keeps the reference quantities.
    assert {r.data["quantity_kg"] for r in rows} == {5.0, 7.0}


@pytest.mark.asyncio
async def test_prefill_rebuilds_the_module(async_session, user):
    """A prefill empties the module first, so it never mixes two baselines."""
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
        data={"category": "ch4", "quantity_kg": 1.0},
    )
    async_session.add(user_row)
    await async_session.flush()

    copied = await service.prefill_module_from_reference(
        report, int(ModuleTypeEnum.process_emissions)
    )
    assert copied == 2

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 2  # the previous rows are gone, not duplicated
    assert all(r.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value for r in rows)


@pytest.mark.asyncio
async def test_prefill_without_reference_year_raises(async_session, user):
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session)
    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
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
        data={"category": "n2o", "quantity_kg": 3.0},
    )
    async_session.add(entry)
    await async_session.flush()
    return entry


async def _plan_module_rows(service, async_session, report):
    """The process-emissions rows of a plan-year report."""
    plan_module = await service.report_service.module_service.get_module(
        report.id, int(ModuleTypeEnum.process_emissions)
    )
    return await DataEntryRepository(async_session).list_by_module(plan_module.id)


@pytest.mark.asyncio
async def test_reference_year_change_wipes_the_previous_baseline_rows(
    async_session, user
):
    """The module is emptied and rebuilt from the new baseline."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    entry_2025 = await _second_calculator_year(service, async_session)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)

    await _set_ref(service, plan.id, 2027, 2025)

    rows = await _plan_module_rows(service, async_session, report)
    assert len(rows) == 1
    assert rows[0].data["quantity_kg"] == 3.0
    assert rows[0].data["source_data_entry_id"] == entry_2025.id


@pytest.mark.asyncio
async def test_switching_back_reprefills_at_100_percent(async_session, user):
    """Coming back to a baseline starts over: the earlier edits are gone."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)
    await _second_calculator_year(service, async_session)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)
    rows_2024 = await _plan_module_rows(service, async_session, report)
    rows_2024[0].data = {
        **rows_2024[0].data,
        "percentage_of_reference_year": 40,
        "quantity_kg": 99.0,
    }
    async_session.add(rows_2024[0])
    await async_session.flush()

    await _set_ref(service, plan.id, 2027, 2025)
    await _set_ref(service, plan.id, 2027, 2024)

    rows = await _plan_module_rows(service, async_session, report)
    assert len(rows) == 2
    assert all(r.data["percentage_of_reference_year"] == 100 for r in rows)
    assert {r.data["quantity_kg"] for r in rows} == {5.0, 7.0}


@pytest.mark.asyncio
async def test_hand_added_rows_are_wiped_on_switch(async_session, user):
    """A prefilled module is rebuilt whole — hand-added rows go too."""
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
            data={"category": "ch4", "quantity_kg": 1.0},
        )
    )
    await async_session.flush()

    await _set_ref(service, plan.id, 2027, 2025)

    rows = await _plan_module_rows(service, async_session, report)
    assert [r.source for r in rows] == [DataEntrySourceEnum.PLANNER_SNAPSHOT.value]


@pytest.mark.asyncio
async def test_switch_to_a_year_without_calculator_data_empties_the_modules(
    async_session, user
):
    """No baseline to copy is still a wipe: stale rows would misreport the year."""
    service = SimulatorPlanService(async_session)
    await _calculator_report_with_process_entries(service, async_session, year=2024)

    plan = await service.create_plan(unit_id=1, user=user, name="proj")
    report = await _plan_year_report(service, plan.id, reference_year=2024)

    await _set_ref(service, plan.id, 2027, 2025)

    assert await _plan_module_rows(service, async_session, report) == []


@pytest.mark.asyncio
async def test_duplicate_plan_syncs_year_reports(async_session, user):
    """A duplicated plan opens with the same year sections as its source."""
    service = SimulatorPlanService(async_session)
    source = await service.create_plan(unit_id=1, user=user, name="source")
    await _update_plan(
        service, source.id, SimulatorPlanUpdate(start_year=2027, end_year=2029)
    )

    copy = await service.duplicate_plan(source.id, user)
    assert copy is not None
    assert (copy.start_year, copy.end_year) == (2027, 2029)

    years = await service.list_plan_years(copy.id)
    assert years is not None
    assert [y.year for y in years] == [2027, 2028, 2029]
    assert all(len(y.modules) > 0 for y in years)
