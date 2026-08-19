"""The simulator-plan prefill job, end to end through ``run_job`` (Track F4).

The unit tests around this handler mock ``SimulatorPlanService`` entirely,
so they pin the handler's contract but cannot catch the failure mode #1219
actually hit on stage: a handler that leaves its session unusable, so the
job never reaches FINISHED and the stall self-propagates. That needs the
real runner, a real database, and a real prefill.

What these pin:

A. A queued job dispatched through ``run_job`` reaches FINISHED/SUCCESS and
   the plan year really holds the copied rows afterwards. If prefill only
   worked when called directly — the way every measurement in plan #2050
   Track F6 called it — the feature would be silently broken in production
   while every unit test stayed green.
B. Re-running the same job converges instead of duplicating rows, the
   retry-safety property the 310-series requires of every handler.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionResult,
    IngestionState,
    TargetType,
)
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import GlobalScope, Role, RoleName, User, UserProvider
from app.modules.emissions.taxonomy import EmissionType
from app.repositories.data_entry_repo import DataEntryRepository
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.carbon_report import CarbonReportCreate
from app.schemas.simulator_plan import SimulatorPlanUpdate
from app.services.simulator_plan_service import SimulatorPlanService

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def Sf(pg_dsn):
    """Async sessionmaker pointed at the test PG (psycopg, like production)."""
    engine = create_async_engine(pg_dsn.replace("+asyncpg", "+psycopg"), future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed_plan_awaiting_prefill(Sf) -> tuple[int, list[int], int]:
    """A plan whose 2027 year is set to baseline 2024 but not yet prefilled.

    Returns ``(plan_id, report_ids_needing_prefill, plan_module_id)``.
    """
    async with Sf() as session:
        session.add(Unit(id=1, institutional_code="14270", name="U", level=1))
        await session.flush()
        user = User(institutional_id="1", email="a@b.c", display_name="R")
        user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
        session.add(user)
        await session.flush()

        svc = SimulatorPlanService(session)
        ref = await svc.report_service.create(CarbonReportCreate(year=2024, unit_id=1))
        modules = await svc.report_service.module_service.list_modules(ref.id)
        ref_module = next(
            m
            for m in modules
            if m.module_type_id == int(ModuleTypeEnum.process_emissions)
        )
        session.add(
            Factor(
                emission_type_id=int(EmissionType.process_emissions__co2),
                data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                classification={"category": "co2"},
                values={"ef_kg_co2eq_per_unit": 2.0},
                year=2024,
            )
        )
        for i in range(3):
            session.add(
                DataEntry(
                    data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
                    carbon_report_module_id=ref_module.id,
                    data={"category": "co2", "quantity_kg": float(i + 1)},
                )
            )
        await session.flush()

        # The reference year must actually hold computed emissions — that is
        # what a copied row's provenance points at.
        await svc._recalculate_report_emissions(ref)  # noqa: SLF001

        plan = await svc.create_plan(unit_id=1, user=user, name="p")
        updated = await svc.update_plan(
            plan.id, SimulatorPlanUpdate(start_year=2027, end_year=2027)
        )
        assert updated is not None
        out = await svc.set_reference_year(plan.id, 2027, 2024)
        assert out is not None
        year_read, needs_prefill = out
        assert needs_prefill, "rig is wrong: nothing was deferred"
        plan_module = next(
            m
            for m in year_read.modules
            if m.module_type_id == int(ModuleTypeEnum.process_emissions)
        )
        await session.commit()
        return plan.id, needs_prefill, plan_module.id


async def _queue_prefill_job(Sf, plan_id: int, report_ids: list[int]) -> int:
    async with Sf() as session:
        job = DataIngestionJob(
            job_type="simulator_plan_prefill",
            ingestion_method=IngestionMethod.computed,
            target_type=TargetType.DATA_ENTRIES,
            entity_type=EntityType.GLOBAL_PER_YEAR,
            state=IngestionState.NOT_STARTED,
            provider=UserProvider.DEFAULT,
            meta={"config": {"plan_id": plan_id, "report_ids": report_ids}},
        )
        created = await DataIngestionRepository(session).create_ingestion_job(job)
        await session.commit()
        assert created.id is not None
        return created.id


@pytest.mark.asyncio
async def test_prefill_job_runs_through_the_runner_and_copies_the_rows(
    Sf, pg_dsn, monkeypatch
):
    """The whole path: queued job -> run_job -> handler -> committed rows."""
    # runner.py does `from app.db import SessionLocal` at import time, so the
    # binding to replace lives on the runner module, not on app.db.
    import app.tasks.runner as runner_mod

    monkeypatch.setattr(runner_mod, "SessionLocal", Sf)
    run_job = runner_mod.run_job

    plan_id, report_ids, plan_module_id = await _seed_plan_awaiting_prefill(Sf)
    async with Sf() as session:
        assert (
            await DataEntryRepository(session).list_by_module(plan_module_id) == []
        ), "rig is wrong: the year was already prefilled"

    job_id = await _queue_prefill_job(Sf, plan_id, report_ids)
    await run_job(job_id)

    async with Sf() as session:
        job = await DataIngestionRepository(session).get_job_by_id(job_id)
        assert job is not None
        assert job.state == IngestionState.FINISHED, (
            f"job never reached FINISHED (state={job.state}) — the #1219 stall "
            f"shape: a handler that poisons its session leaves the job stuck"
        )
        assert job.result == IngestionResult.SUCCESS, f"job failed: {job.meta}"

        rows = await DataEntryRepository(session).list_by_module(plan_module_id)
        assert {r.data["quantity_kg"] for r in rows} == {1.0, 2.0, 3.0}, (
            "the runner reported success but the rows were never committed"
        )


@pytest.mark.asyncio
async def test_rerunning_the_prefill_job_converges(Sf, pg_dsn, monkeypatch):
    """A preempted job is re-dispatched; the second run must not duplicate."""
    # runner.py does `from app.db import SessionLocal` at import time, so the
    # binding to replace lives on the runner module, not on app.db.
    import app.tasks.runner as runner_mod

    monkeypatch.setattr(runner_mod, "SessionLocal", Sf)
    run_job = runner_mod.run_job

    plan_id, report_ids, plan_module_id = await _seed_plan_awaiting_prefill(Sf)

    first = await _queue_prefill_job(Sf, plan_id, report_ids)
    await run_job(first)
    # A fresh job row, as the poller's orphan recovery would produce.
    second = await _queue_prefill_job(Sf, plan_id, report_ids)
    await run_job(second)

    async with Sf() as session:
        rows = await DataEntryRepository(session).list_by_module(plan_module_id)
        assert len(rows) == 3, f"retry duplicated rows: {len(rows)} != 3"


@pytest.mark.asyncio
async def test_reports_survive_the_job_with_their_reference_year(Sf):
    """Sanity: the deferred metadata write is committed before the job runs.

    If the route's commit and the job's read ever drift apart, the handler
    would prefill against a report whose reference_year is still unset and
    silently produce nothing.
    """
    _plan_id, report_ids, _module_id = await _seed_plan_awaiting_prefill(Sf)
    async with Sf() as session:
        for report_id in report_ids:
            report = await session.get(CarbonReport, report_id)
            assert report is not None
            assert report.reference_year == 2024
            assert report.year == 2027


@pytest.mark.asyncio
async def test_prefilled_emissions_keep_the_source_factor_id(Sf):
    """A copied row's emissions must carry the source leaf's factor id.

    Not cosmetic. ``get_submodule_data`` joins ``primary_factor_id`` to
    ``Factor`` and spreads its values into ``enriched_data["primary_factor"]``,
    which each module's ``to_response`` reads to populate ordinary row
    fields. Equipment's ``active_power_w``/``standby_power_w`` have **no
    fallback to entry data**, so a NULL factor id makes them ``None`` and
    ``ModuleTable.isCompleteEquipement`` marks the row incomplete — the
    prefilled planner rows rendered as tinted "incomplete" before this fix
    (plan #2050 F3).
    """
    _plan_id, report_ids, plan_module_id = await _seed_plan_awaiting_prefill(Sf)

    async with Sf() as session:
        svc = SimulatorPlanService(session)
        await svc.prefill_reports(report_ids)
        await session.commit()

        entries = await DataEntryRepository(session).list_by_module(plan_module_id)
        assert entries, "nothing was prefilled — rig is wrong"
        for entry in entries:
            source_id = entry.data.get("source_data_entry_id")
            assert source_id is not None
            rows = (
                await session.exec(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id) == entry.id
                    )
                )
            ).all()
            assert rows, f"copied entry {entry.id} has no emissions"
            src_rows = (
                await session.exec(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id) == int(source_id)
                    )
                )
            ).all()
            assert src_rows, f"rig is wrong: source {source_id} has no emissions"
            expected = {r.primary_factor_id for r in src_rows}
            assert expected and expected != {None}, (
                f"rig is wrong: source {source_id} has no factor id: {expected}"
            )
            assert {r.primary_factor_id for r in rows} == expected, (
                f"copied entry {entry.id} lost its factor provenance: "
                f"{[r.primary_factor_id for r in rows]} != {expected}"
            )
