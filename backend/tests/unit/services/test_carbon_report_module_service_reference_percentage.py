"""Regression tests for the equipment global-percentage aggregate rewrite (#2783).

Per the Option B decision (#2749), applying the equipment module's global
percentage now collapses the reference-year snapshot into one aggregate line
per equipment type (scientific/it/other), instead of rewriting every
prefilled line individually (~5,700 queries for 950 lines on the old path).
See docs/src/implementation-plans/2783-equipment-global-percentage-aggregate-line.md.

Mirrors ``tests/unit/services/test_simulator_plan_service.py``'s in-memory
sqlite fixture. The reference module's ``stats`` are set directly rather
than derived from real factor-priced entries: ``_equipment_reference_totals``
only reads ``stats["by_emission_type"]`` (already covered, keys and values,
by ``compute_module_stats``'s own tests), so this isolates the code under
test from the unrelated factor-resolution pipeline.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReportModule, CarbonReportType
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import GlobalScope, Role, RoleName, User
from app.modules.emissions.taxonomy import EmissionType
from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.simulator_plan import SimulatorPlanUpdate
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.simulator_plan_service import SimulatorPlanService

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

SCIENTIFIC_ET = EmissionType.equipment__scientific.value  # 80100
IT_ET = EmissionType.equipment__it.value  # 80200
OTHER_ET = EmissionType.equipment__other.value  # 80300


async def _set_ref(service, plan_id, year, reference_year):
    """``set_reference_year`` plus the prefill its job now runs (Track F4)."""
    out = await service.set_reference_year(
        plan_id, year, reference_year, is_grant=False
    )
    if out is None:
        return None
    _, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    years = await service.list_plan_years(plan_id)
    return next((y for y in years or [] if y.year == year), None)


async def _update_plan(service, plan_id, update):
    out = await service.update_plan(plan_id, update)
    if out is None:
        return None
    result, needs_prefill = out
    await service.prefill_reports(needs_prefill)
    return result


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def async_session(engine):
    async_session = sessionmaker(
        engine, class_=SQLModelAsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def user(async_session):
    db_user = User(
        institutional_id="100001", email="ada@example.com", display_name="Ada Lovelace"
    )
    db_user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
    async_session.add(db_user)
    await async_session.flush()
    return db_user


@dataclass
class StatementLog:
    statements: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)


@contextmanager
def count_statements(engine):
    """Count SQL statements issued by the wrapped block (mirrors the #2050
    perf tests' ``before_cursor_execute`` listener).
    """
    log = StatementLog()

    def listener(conn, cursor, statement, parameters, context, executemany):
        log.statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield log
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


async def _reference_calculator_report(service, async_session, unit_id, year):
    """A validated Calculator report for the reference year (empty modules).

    Validated so ``prefill_reports`` is willing to copy from it — mirrors
    ``_validate_modules`` in ``test_simulator_plan_service.py``.
    """
    project = await service.report_service._get_project(
        unit_id, CarbonReportType.CALCULATOR
    ) or await service.report_service._create_project(
        unit_id, CarbonReportType.CALCULATOR
    )
    report = await service.report_service.create(
        CarbonReportCreate(year=year, unit_id=unit_id, carbon_project_id=project.id)
    )
    await async_session.execute(
        update(CarbonReportModule)
        .where(CarbonReportModule.carbon_report_id == report.id)
        .values(status=ModuleStatus.VALIDATED)
    )
    return report


async def _plan_report_with_equipment(
    async_session, user, *, unit_id=1, plan_year=2027, reference_year=2024
):
    """A plan-year report + equipment module, reference year set.

    The reference year's own equipment module is empty (no real entries) —
    tests set its ``stats`` directly, see module docstring.
    """
    service = SimulatorPlanService(async_session)
    ref_report = await _reference_calculator_report(
        service, async_session, unit_id, reference_year
    )
    plan = await service.create_plan(unit_id=unit_id, user=user, name="proj")
    await _update_plan(
        service, plan.id, SimulatorPlanUpdate(start_year=plan_year, end_year=plan_year)
    )
    await _set_ref(service, plan.id, plan_year, reference_year)
    reports = await service.repo.list_reports_for_project(plan.id)
    report = next(r for r in reports if r.year == plan_year)
    module_service = service.report_service.module_service
    plan_module = await module_service.get_module(
        report.id, int(ModuleTypeEnum.equipment)
    )
    ref_module = await module_service.get_module(
        ref_report.id, int(ModuleTypeEnum.equipment)
    )
    return report, plan_module, ref_module


async def _set_stats(async_session, module_id, by_emission_type: dict[int, float]):
    db_module = await async_session.get(CarbonReportModule, module_id)
    db_module.stats = {
        "by_emission_type": {str(k): v for k, v in by_emission_type.items()}
    }
    async_session.add(db_module)
    await async_session.flush()


async def _legacy_row(async_session, module_id, data_entry_type, *, source_id=1, pct=0):
    row = DataEntry(
        data_entry_type_id=data_entry_type.value,
        carbon_report_module_id=module_id,
        source=DataEntrySourceEnum.PLANNER_SNAPSHOT.value,
        data={"source_data_entry_id": source_id, "percentage_of_reference_year": pct},
    )
    async_session.add(row)
    await async_session.flush()
    return row


async def _manual_row(async_session, module_id, data_entry_type):
    row = DataEntry(
        data_entry_type_id=data_entry_type.value,
        carbon_report_module_id=module_id,
        source=DataEntrySourceEnum.USER_MANUAL.value,
        data={"equipment_name": "Hand-added scope"},
    )
    async_session.add(row)
    await async_session.flush()
    return row


async def _reference_equipment_row(async_session, ref_module_id, unit_id, year):
    """A real reference-year equipment entry to restore into per-line mode.

    No matching factor exists in this lightweight sqlite fixture, so the
    recompute after copying prices it at 0 kg — irrelevant here, this only
    exercises row restoration (``source_data_entry_id``/reset), not pricing.
    """
    row = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        carbon_report_module_id=ref_module_id,
        unit_id=unit_id,
        year=year,
        data={"active_usage_hours": 40, "passive_usage_hours": 128},
    )
    async_session.add(row)
    await async_session.flush()
    return row


@pytest.mark.asyncio
async def test_aggregate_lines_written_per_type_present(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(
        async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0, IT_ET: 500.0}
    )

    module_service = CarbonReportModuleService(async_session)
    written = await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )
    assert written == 2

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 2
    by_type = {r.data_entry_type_id: r for r in rows}
    assert set(by_type) == {
        DataEntryTypeEnum.scientific.value,
        DataEntryTypeEnum.it.value,
    }
    for row in rows:
        assert row.data["source_data_entry_id"] is None
        assert row.data["percentage_of_reference_year"] == 25.0
        assert row.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value

    emissions = await DataEntryEmissionRepository(async_session).get_stats_pair_many(
        [plan_module.id]
    )
    leaf_emissions, _, _ = emissions[plan_module.id]
    assert leaf_emissions[str(SCIENTIFIC_ET)] == pytest.approx(250.0)  # 1000 * 25%
    assert leaf_emissions[str(IT_ET)] == pytest.approx(125.0)  # 500 * 25%
    assert str(OTHER_ET) not in leaf_emissions


@pytest.mark.asyncio
async def test_repeat_patch_updates_in_place(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    module_service = CarbonReportModuleService(async_session)

    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 10.0
    )
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 1
    first_id = rows[0].id

    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 40.0
    )
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 1  # no duplicate row
    assert rows[0].id == first_id  # same row, updated in place
    assert rows[0].data["percentage_of_reference_year"] == 40.0

    emissions = await DataEntryEmissionRepository(async_session).get_stats_pair_many(
        [plan_module.id]
    )
    leaf_emissions, _, _ = emissions[plan_module.id]
    assert leaf_emissions[str(SCIENTIFIC_ET)] == pytest.approx(400.0)  # 1000 * 40%


@pytest.mark.asyncio
async def test_manual_entries_untouched(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    manual = await _manual_row(async_session, plan_module.id, DataEntryTypeEnum.other)

    module_service = CarbonReportModuleService(async_session)
    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    kept = next(r for r in rows if r.id == manual.id)
    assert kept.data == {"equipment_name": "Hand-added scope"}
    assert kept.source == DataEntrySourceEnum.USER_MANUAL.value


@pytest.mark.asyncio
async def test_legacy_per_line_rows_collapse_on_first_patch(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    legacy = [
        await _legacy_row(
            async_session, plan_module.id, DataEntryTypeEnum.scientific, source_id=i
        )
        for i in range(1, 6)
    ]

    module_service = CarbonReportModuleService(async_session)
    written = await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )
    assert written == 1

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 1  # the 5 legacy rows are gone, replaced by 1 aggregate
    assert rows[0].id not in {r.id for r in legacy}
    assert rows[0].data["source_data_entry_id"] is None


@pytest.mark.asyncio
async def test_statement_count_is_flat_regardless_of_legacy_row_count(
    async_session, engine, user
):
    """#2783's own regression guard, mirroring the #2050 perf tests' pattern:
    the write no longer scales with how many rows it touches.

    Two independent reports (own unit each), both on their first-ever
    PATCH (the aggregate-create path), differing only in how many legacy
    per-line rows sit in the module beforehand — 5 vs 500. Comparing two
    *first* patches, rather than patching the same module twice, keeps
    this from also measuring the unrelated create-vs-update delta.
    """
    small_report, small_module, small_ref = await _plan_report_with_equipment(
        async_session, user, unit_id=1
    )
    await _set_stats(async_session, small_ref.id, {SCIENTIFIC_ET: 1000.0, IT_ET: 500.0})
    for i in range(1, 6):
        await _legacy_row(
            async_session, small_module.id, DataEntryTypeEnum.scientific, source_id=i
        )

    large_report, large_module, large_ref = await _plan_report_with_equipment(
        async_session, user, unit_id=2
    )
    await _set_stats(async_session, large_ref.id, {SCIENTIFIC_ET: 1000.0, IT_ET: 500.0})
    for i in range(1, 501):
        await _legacy_row(
            async_session, large_module.id, DataEntryTypeEnum.scientific, source_id=i
        )

    module_service = CarbonReportModuleService(async_session)
    with count_statements(engine) as log_small:
        await module_service.set_reference_percentage_all(
            small_report.id, int(ModuleTypeEnum.equipment), 10.0
        )
    with count_statements(engine) as log_large:
        await module_service.set_reference_percentage_all(
            large_report.id, int(ModuleTypeEnum.equipment), 10.0
        )

    assert log_large.total == log_small.total, (
        f"query count grew with row count: {log_small.total} -> {log_large.total}\n"
        f"small={log_small.statements}\nlarge={log_large.statements}"
    )


@pytest.mark.asyncio
async def test_reset_restores_per_line_rows_from_reference(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    ref_row = await _reference_equipment_row(
        async_session, ref_module.id, unit_id=1, year=2024
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    module_service = CarbonReportModuleService(async_session)
    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )
    manual = await _manual_row(async_session, plan_module.id, DataEntryTypeEnum.other)

    restored = await module_service.reset_equipment_to_per_line(
        report.id, int(ModuleTypeEnum.equipment)
    )
    assert restored == 1

    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.id != manual.id
    assert row.data["source_data_entry_id"] == ref_row.id
    assert row.data["percentage_of_reference_year"] == 0
    assert row.source == DataEntrySourceEnum.PLANNER_SNAPSHOT.value


@pytest.mark.asyncio
async def test_reset_with_no_reference_entries_empties_module(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    module_service = CarbonReportModuleService(async_session)
    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )

    restored = await module_service.reset_equipment_to_per_line(
        report.id, int(ModuleTypeEnum.equipment)
    )
    assert restored == 0
    rows = await DataEntryRepository(async_session).list_by_module(plan_module.id)
    assert rows == []


@pytest.mark.asyncio
async def test_reset_rejects_non_equipment_module(async_session, user):
    report, _, _ = await _plan_report_with_equipment(async_session, user)
    module_service = CarbonReportModuleService(async_session)
    with pytest.raises(ValueError, match="equipment"):
        await module_service.reset_equipment_to_per_line(
            report.id, int(ModuleTypeEnum.headcount)
        )


@pytest.mark.asyncio
async def test_equipment_stats_extras_after_patch(async_session, user):
    """#2783: the frontend reads reference total + applied % from stats,
    not from a client-side sum of snapshot rows (broken for aggregate rows,
    which have no single source).
    """
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(
        async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0, IT_ET: 500.0}
    )
    module_service = CarbonReportModuleService(async_session)
    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )

    db_module = await async_session.get(CarbonReportModule, plan_module.id)
    assert db_module.stats["equipment_reference_total_kg"] == pytest.approx(1500.0)
    assert db_module.stats["equipment_applied_percentage"] == 25.0


@pytest.mark.asyncio
async def test_equipment_applied_percentage_null_without_aggregate(async_session, user):
    report, plan_module, _ = await _plan_report_with_equipment(async_session, user)
    module_service = CarbonReportModuleService(async_session)
    await module_service.recompute_stats_many([plan_module.id])

    db_module = await async_session.get(CarbonReportModule, plan_module.id)
    assert db_module.stats["equipment_applied_percentage"] is None
    assert db_module.stats["equipment_reference_total_kg"] == 0.0


@pytest.mark.asyncio
async def test_equipment_stats_extras_cleared_after_reset(async_session, user):
    report, plan_module, ref_module = await _plan_report_with_equipment(
        async_session, user
    )
    await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
    module_service = CarbonReportModuleService(async_session)
    await module_service.set_reference_percentage_all(
        report.id, int(ModuleTypeEnum.equipment), 25.0
    )

    await module_service.reset_equipment_to_per_line(
        report.id, int(ModuleTypeEnum.equipment)
    )

    db_module = await async_session.get(CarbonReportModule, plan_module.id)
    assert db_module.stats["equipment_applied_percentage"] is None


@pytest.mark.asyncio
async def test_equipment_reference_totals_by_report_is_batched(
    async_session, engine, user
):
    """#2783's own second-order regression guard: the stats-extras prefetch
    inside ``recompute_stats_many`` must not scale with how many equipment
    modules share one reference year (mirrors
    ``test_statement_count_is_flat_regardless_of_legacy_row_count``'s
    pattern, but for the batched *read* path added in this commit rather
    than the write path).
    """
    module_service = CarbonReportModuleService(async_session)

    few_reports = []
    for unit_id in (101, 102):
        report, _, ref_module = await _plan_report_with_equipment(
            async_session, user, unit_id=unit_id, reference_year=2024
        )
        await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
        few_reports.append(report)

    many_reports = []
    for unit_id in range(201, 221):
        report, _, ref_module = await _plan_report_with_equipment(
            async_session, user, unit_id=unit_id, reference_year=2024
        )
        await _set_stats(async_session, ref_module.id, {SCIENTIFIC_ET: 1000.0})
        many_reports.append(report)

    with count_statements(engine) as log_few:
        await module_service._equipment_reference_totals_by_report(  # noqa: SLF001
            few_reports
        )
    with count_statements(engine) as log_many:
        await module_service._equipment_reference_totals_by_report(  # noqa: SLF001
            many_reports
        )

    assert log_many.total == log_few.total, (
        f"prefetch query count grew with report count: "
        f"{log_few.total} (2 reports) -> {log_many.total} (20 reports)\n"
        f"few={log_few.statements}\nmany={log_many.statements}"
    )


@pytest.mark.asyncio
async def test_only_equipment_module_is_supported(async_session, user):
    report, _, _ = await _plan_report_with_equipment(async_session, user)
    module_service = CarbonReportModuleService(async_session)
    with pytest.raises(ValueError, match="equipment"):
        await module_service.set_reference_percentage_all(
            report.id, int(ModuleTypeEnum.headcount), 10.0
        )
