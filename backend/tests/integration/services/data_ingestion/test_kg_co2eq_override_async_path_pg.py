"""End-to-end Postgres test for the B-H1 kg_co2eq override carrier.

Pin: under ``BULK_PATH_PURE_ASYNC`` the bulk-path providers persist the
ingestion-time ``kg_co2eq`` override (Tableau's ``OUT_CO2_CORRECTED`` for
the travel API; the parsed CSV value for ``base_csv_provider``) into
``DataEntry.data`` under the reserved ``__kg_co2eq_override__`` key.

The runner-driven recalc workflow then reads ``data_entries`` and calls
``DataEntryEmissionService.upsert_by_data_entry``, which has no
``kg_co2eq_override`` parameter — without the carrier this test was
guarding the regression where every async-path emission silently came out
formula-recomputed.

This test bypasses the actual ingest providers (their full transactional
machinery is exercised elsewhere) and seeds a ``DataEntry`` shaped exactly
like the one the providers persist post-fix: payload includes
``__kg_co2eq_override__``.  Running ``upsert_by_data_entry`` against it
must yield an emission row whose ``kg_co2eq`` equals the override —
provably *not* the formula-derived value.

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
async def test_kg_co2eq_override_survives_async_recalc(pg_dsn):
    """B-H1 — a DataEntry persisted with ``__kg_co2eq_override__`` survives
    the async path: ``EmissionRecalculationWorkflow`` →
    ``upsert_by_data_entry`` produces an emission whose ``kg_co2eq`` equals
    the override, NOT the value the formula would have yielded.

    Uses an IT/equipment factor + entry where the formula yields a
    deterministic, distinguishable value (~50.0) so the override (999.0)
    cannot accidentally collide with the formula's output.
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
            module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        )
        s.add(module)
        await s.commit()
        module_id = module.id

        # Factor whose formula yields a small, deterministic value:
        #   ef_kg_co2eq_per_kwh=0.1, active_power_w=100, standby_power_w=10,
        #   active=40h/wk, standby=128h/wk → ~50 kg over the year.
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

        # Persist the override on the data entry under the reserved carrier
        # — exactly the shape the bulk-path providers use under
        # ``BULK_PATH_PURE_ASYNC`` after the B-H1 fix.
        override_value = 999.0
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
                "__kg_co2eq_override__": override_value,
            },
        )
        s.add(entry)
        await s.commit()
        entry_id = entry.id

    # ── 2. Direct ``upsert_by_data_entry`` — pins the prepare_create path
    # ────────────────────────────────────────────────────────────────────
    async with Sf() as s:
        entry = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        emission_svc = DataEntryEmissionService(s)
        await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(entry))
        await s.commit()

    # Read back on a separate engine — proves the override-derived emission
    # committed and is visible across connections.
    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            rows = (
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
        assert len(rows) >= 1, "expected at least one emission row after upsert"
        kg_values = [r.kg_co2eq for r in rows]
        # Override short-circuits the formula: every (non-rollup) row carries
        # the override exactly.  No row should carry the ~50 formula value.
        assert override_value in kg_values, (
            f"override {override_value} missing from persisted emissions: {kg_values}"
        )
        for kg in kg_values:
            assert kg == pytest.approx(override_value, rel=1e-6), (
                f"emission kg_co2eq={kg} differs from override "
                f"{override_value} — formula leaked through B-H1 carrier"
            )
        # Rows produced by the override branch carry no ``primary_factor_id``
        # — pin the contract from prepare_create's short-circuit.
        assert all(r.primary_factor_id is None for r in rows), (
            f"override rows must have primary_factor_id=None, got: "
            f"{[r.primary_factor_id for r in rows]}"
        )
    finally:
        await verify_engine.dispose()

    await engine.dispose()


@pytest.mark.asyncio
async def test_kg_co2eq_override_survives_recalc_workflow(pg_dsn):
    """B-H1 — covers the exact call-path the runner-driven chain takes:
    ``EmissionRecalculationWorkflow.recalculate_for_data_entry_type`` →
    ``upsert_by_data_entry`` → ``prepare_create``.  The persisted
    ``__kg_co2eq_override__`` carrier must survive that hop and produce
    emissions whose ``kg_co2eq`` equals the override.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    override_value = 777.0

    async with Sf() as s:
        unit = Unit(
            institutional_code="WF",
            institutional_id="WF-UNIT",
            name="Workflow Test Unit",
            level=1,
        )
        s.add(unit)
        await s.commit()

        report = CarbonReport(year=2025, unit_id=unit.id)
        s.add(report)
        await s.commit()

        module = CarbonReportModule(
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        )
        s.add(module)
        await s.commit()

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

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.it.value,
            carbon_report_module_id=module.id,
            data={
                "primary_factor_id": factor.id,
                "equipment_class": "Laptop",
                "sub_class": "Standard",
                "active_usage_hours_per_week": 40.0,
                "standby_usage_hours_per_week": 128.0,
                "name": "Workflow Laptop",
                "__kg_co2eq_override__": override_value,
            },
        )
        s.add(entry)
        await s.commit()
        entry_id = entry.id

    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        result = await wf.recalculate_for_data_entry_type(DataEntryTypeEnum.it, 2025)
        await s.commit()

    assert result["recalculated"] >= 1, (
        f"recalc workflow processed no entries: {result}"
    )

    verify_engine = create_async_engine(pg_dsn, future=True)
    Vf = async_sessionmaker(verify_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Vf() as vs:
            rows = (
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
        assert len(rows) >= 1, "expected emissions after recalc workflow"
        for r in rows:
            assert r.kg_co2eq == pytest.approx(override_value, rel=1e-6), (
                f"recalc workflow dropped the override: "
                f"emission_id={r.id} kg_co2eq={r.kg_co2eq}"
            )
    finally:
        await verify_engine.dispose()
        await engine.dispose()


@pytest.mark.asyncio
async def test_kg_co2eq_override_function_arg_takes_precedence(pg_dsn):
    """B-H1 — when both the function-arg ``kg_co2eq_override`` and the
    persisted ``__kg_co2eq_override__`` carrier are present, the function
    arg wins.  Pins the legacy inline-path semantics so existing
    ``_process_batch`` tests stay green.
    """
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Sf() as s:
        unit = Unit(
            institutional_code="T2",
            institutional_id="T2-UNIT",
            name="Test Unit 2",
            level=1,
        )
        s.add(unit)
        await s.commit()

        report = CarbonReport(year=2025, unit_id=unit.id)
        s.add(report)
        await s.commit()

        module = CarbonReportModule(
            carbon_report_id=report.id,
            module_type_id=ModuleTypeEnum.equipment_electric_consumption.value,
        )
        s.add(module)
        await s.commit()

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

        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.it.value,
            carbon_report_module_id=module.id,
            data={
                "primary_factor_id": factor.id,
                "equipment_class": "Laptop",
                "sub_class": "Standard",
                "active_usage_hours_per_week": 40.0,
                "standby_usage_hours_per_week": 128.0,
                "name": "Test Laptop",
                "__kg_co2eq_override__": 999.0,  # carrier value
            },
        )
        s.add(entry)
        await s.commit()
        entry_id = entry.id

    arg_override = 42.0  # function-arg value — must win over the carrier

    async with Sf() as s:
        entry = (
            await s.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
        ).scalar_one()
        emission_svc = DataEntryEmissionService(s)
        emissions = await emission_svc.prepare_create(
            DataEntryResponse.model_validate(entry),
            kg_co2eq_override=arg_override,
        )

    try:
        assert emissions, "expected at least one prepared emission"
        for em in emissions:
            assert em.kg_co2eq == pytest.approx(arg_override, rel=1e-6), (
                f"function-arg override should win — got kg_co2eq={em.kg_co2eq}, "
                f"expected {arg_override}"
            )
    finally:
        await engine.dispose()
