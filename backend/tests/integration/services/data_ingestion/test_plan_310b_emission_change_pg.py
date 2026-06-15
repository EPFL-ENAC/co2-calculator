"""End-to-end Postgres test for Plan 310B Part 6.

The narrow recalc-fan-out test (test_plan_310b_recalc_fanout_pg.py)
proves that recalc jobs are *enqueued* with the right scope.  This file
goes one step further: it verifies that running the recalc workflow
against a real factor → data-entry → emission graph actually
**recomputes the emission** when the factor's values change.

Failure-mode this guards against: the previous code path silently
returned ("No stale combos to recalculate for year=2025") and emissions
in the DB stayed at the old value despite a successful factor reupload.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.workflows.emission_recalculation import EmissionRecalculationWorkflow


@pytest.mark.asyncio
async def test_factor_reupload_recomputes_emission_in_db(pg_dsn):
    """Equipment factor (it module, equipment_class=Laptop) seeded with
    ef_kg_co2eq_per_kwh=0.1.  After computing the initial emission for a
    matching data entry, change the factor's ef to 0.2 and run the recalc
    workflow.  Verify on a **separate engine** (different connection pool
    from the one that did the writes — proves cross-connection commit
    visibility, the diagnostic the user lost when checking the dev DB)
    that the persisted emission is exactly doubled.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ── 1. Seed the carbon-report graph + factor + data entry ──────────
    async with Sf() as s:
        unit = Unit(
            institutional_code="TEST",
            institutional_id="TEST-UNIT",
            name="Test Unit",
            level=1,
        )
        s.add(unit)
        await s.commit()
        unit_id = unit.id

        report = CarbonReport(year=2025, unit_id=unit_id)
        s.add(report)
        await s.commit()
        report_id = report.id

        module = CarbonReportModule(
            carbon_report_id=report_id,
            module_type_id=ModuleTypeEnum.equipment.value,
        )
        s.add(module)
        await s.commit()
        module_id = module.id

        factor = Factor(
            emission_type_id=EmissionType.equipment__it.value,
            data_entry_type_id=DataEntryTypeEnum.it.value,
            classification={
                "equipment_class": "Laptop",
                "sub_class": "Standard",
                "year": 2025,
            },
            values={
                "active_power_w": 100.0,
                "standby_power_w": 10.0,
                "ef_kg_co2eq_per_kwh": 0.1,
            },
            year=2025,
        )
        s.add(factor)
        await s.commit()
        factor_id = factor.id

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.it.value,
            carbon_report_module_id=module_id,
            data={
                "primary_factor_id": factor_id,
                "equipment_class": "Laptop",
                "sub_class": "Standard",
                "active_usage_hours_per_week": 40.0,
                "standby_usage_hours_per_week": 128.0,
                "name": "Test Laptop",
            },
        )
        s.add(entry)
        await s.commit()
        entry_id = entry.id

    # ── 2. Initial emission compute ────────────────────────────────────
    async with Sf() as s:
        entry = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        emission_svc = DataEntryEmissionService(s)
        await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(entry))
        await s.commit()

    async with Sf() as s:
        initial_rows = (
            (
                await s.execute(
                    select(DataEntryEmission).where(
                        col(DataEntryEmission.data_entry_id) == entry_id
                    )
                )
            )
            .scalars()
            .all()
        )
        initial_total = sum((r.kg_co2eq or 0.0) for r in initial_rows)
    assert initial_total > 0, "initial emission compute should produce a non-zero total"

    # ── 3. Update the factor — same identity, double the ef ────────────
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        f.values = {**f.values, "ef_kg_co2eq_per_kwh": 0.2}
        await s.commit()

    # ── 4. Run the recalc workflow ─────────────────────────────────────
    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)
        await s.commit()

    # ── 5. Verify on a SEPARATE engine ─────────────────────────────────
    # This is the key assertion: a fresh connection pool reads the
    # post-recalc state — proves the recompute committed and is visible
    # across connections (i.e. another process / pgcli session sees it).
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            new_rows = (
                (
                    await vs.execute(
                        select(DataEntryEmission).where(
                            col(DataEntryEmission.data_entry_id) == entry_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            new_total = sum((r.kg_co2eq or 0.0) for r in new_rows)
    finally:
        await verify_engine.dispose()
        await engine.dispose()

    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3), (
        "Doubling ef_kg_co2eq_per_kwh should double the persisted emission. "
        f"Initial={initial_total}, new={new_total}"
    )
