"""Plan 310-D follow-up — Strategy A (JSON-link) rematch regression net.

The JSON-link path is the original Plan 310-D rematch surface (PR #1027):
``EmissionRecalculationWorkflow`` walks ``factor_lookup`` and rewrites
``entry.data['primary_factor_id']`` for handlers whose ``kind_field`` (and
optional ``subkind_field``) live on ``entry.data``.  Modules covered:

- equipment_electric_consumption (it / scientific / other)
- purchase (purchase_common / purchase_additional)
- external_cloud_and_ai (external_cloud / external_ai)
- process_emissions (process_emission)
- buildings — energy_combustion (building_energy_combustion)

This file is the regression net for the strict-drop bulk-prefetch path:
each test seeds → computes → mutates ``factor.values`` → recalcs → asserts
``kg_co2eq`` reflects the new factor.  Combined with the per-module
strategy B coverage in ``test_strategy_b_rematch_pg.py``, this completes
Plan 310-D's 14-row IT matrix.

Pattern note: each test stays inside a single ``create_async_engine``
plus one ``verify_engine`` for the cross-connection read.  Engine churn
is intentionally kept low because asyncpg pools occasionally close
connections out from under SQLAlchemy when many engines are created
back-to-back inside a single test session, producing flaky
``InterfaceError: connection is closed`` failures.

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

# ── Helpers ────────────────────────────────────────────────────────────


async def _seed_unit_and_module(
    session: AsyncSession,
    *,
    module_type: ModuleTypeEnum,
    year: int = 2025,
) -> int:
    """Seed Unit + CarbonReport + CarbonReportModule, return module_id."""
    unit = Unit(
        institutional_code="TEST",
        institutional_id="TEST-UNIT",
        name="Test Unit",
        level=1,
    )
    session.add(unit)
    await session.commit()
    assert unit.id is not None

    report = CarbonReport(year=year, unit_id=unit.id)
    session.add(report)
    await session.commit()
    assert report.id is not None

    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=module_type.value,
    )
    session.add(module)
    await session.commit()
    assert module.id is not None
    return module.id


async def _initial_compute(session: AsyncSession, entry_id: int) -> float:
    """Run initial compute and return total kg_co2eq."""
    entry = (
        await session.execute(select(DataEntry).where(col(DataEntry.id) == entry_id))
    ).scalar_one()
    emission_svc = DataEntryEmissionService(session)
    await emission_svc.upsert_by_data_entry(DataEntryResponse.model_validate(entry))
    await session.commit()
    rows = (
        (
            await session.execute(
                select(DataEntryEmission).where(
                    col(DataEntryEmission.data_entry_id) == entry_id
                )
            )
        )
        .scalars()
        .all()
    )
    return sum((r.kg_co2eq or 0.0) for r in rows)


async def _double_factor_value(
    Sf: async_sessionmaker,
    *,
    factor_id: int,
    value_key: str,
) -> None:
    async with Sf() as s:
        f = (
            await s.execute(select(Factor).where(col(Factor.id) == factor_id))
        ).scalar_one()
        new_values = dict(f.values)
        new_values[value_key] = float(new_values[value_key]) * 2.0
        f.values = new_values
        await s.commit()


async def _run_recalc(
    Sf: async_sessionmaker,
    *,
    data_entry_type: DataEntryTypeEnum,
    year: int = 2025,
) -> dict:
    async with Sf() as s:
        wf = EmissionRecalculationWorkflow(s)
        stats = await wf.recalculate_for_data_entry_type(data_entry_type, year)
        await s.commit()
    assert stats["errors"] == 0, stats["error_details"]
    return stats


async def _read_kg_total_on_fresh_engine(pg_dsn: str, entry_id: int) -> float:
    """Read total kg_co2eq for an entry on a fresh engine (cross-connection)."""
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
            return sum((r.kg_co2eq or 0.0) for r in rows)
    finally:
        await verify_engine.dispose()


# ── Per-module factor + entry seeders ──────────────────────────────────


async def _seed_equipment(
    s: AsyncSession,
    module_id: int,
    det: DataEntryTypeEnum,
    emission_type: EmissionType,
) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=emission_type.value,
        data_entry_type_id=det.value,
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
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=det.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "equipment_class": "Laptop",
            "sub_class": "Standard",
            "active_usage_hours_per_week": 40.0,
            "standby_usage_hours_per_week": 128.0,
            "name": "Test Laptop",
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


async def _seed_purchase(
    s: AsyncSession,
    module_id: int,
    det: DataEntryTypeEnum,
    emission_type: EmissionType,
) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=emission_type.value,
        data_entry_type_id=det.value,
        classification={"purchase_institutional_code": "PIC-001"},
        values={"ef_kg_co2eq_per_currency": 0.5, "currency": "eur"},
        year=2025,
    )
    s.add(factor)
    await s.commit()
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=det.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "purchase_institutional_code": "PIC-001",
            "name": "Test purchase",
            "supplier": "ACME",
            "total_spent_amount": 100.0,
            "currency": "eur",
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


async def _seed_external_cloud(s: AsyncSession, module_id: int) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=EmissionType.external__clouds__calcul.value,
        data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
        classification={"provider": "AWS", "service_type": "compute"},
        values={"ef_kg_co2eq_per_currency": 0.05, "currency": "eur"},
        year=2025,
    )
    s.add(factor)
    await s.commit()
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.external_clouds.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "provider": "AWS",
            "service_type": "compute",
            "spent_amount": 200.0,
            "currency": "eur",
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


async def _seed_external_ai(s: AsyncSession, module_id: int) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=EmissionType.external__ai__provider_openai.value,
        data_entry_type_id=DataEntryTypeEnum.external_ai.value,
        classification={"provider": "openai", "usage_type": "chat"},
        values={"ef_kg_co2eq_per_request": 0.01},
        year=2025,
    )
    s.add(factor)
    await s.commit()
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.external_ai.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "provider": "openai",
            "usage_type": "chat",
            "fte_count": 1.0,
            "requests_per_user_per_day": "5-20 times per day",
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


async def _seed_process_emissions(s: AsyncSession, module_id: int) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=EmissionType.process_emissions__co2.value,
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        classification={"category": "co2", "subcategory": "industrial"},
        values={"ef_kg_co2eq_per_unit": 1.5, "unit": "kg"},
        year=2025,
    )
    s.add(factor)
    await s.commit()
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "category": "co2",
            "subcategory": "industrial",
            "quantity": 100.0,
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


async def _seed_energy_combustion(s: AsyncSession, module_id: int) -> tuple[int, int]:
    factor = Factor(
        emission_type_id=EmissionType.buildings__combustion__natural_gas.value,
        data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
        classification={"name": "natural_gas", "unit": "kWh"},
        values={"ef_kg_co2eq_per_unit": 0.2},
        year=2025,
    )
    s.add(factor)
    await s.commit()
    assert factor.id is not None
    entry = DataEntry(
        data_entry_type_id=DataEntryTypeEnum.energy_combustion.value,
        carbon_report_module_id=module_id,
        data={
            "primary_factor_id": factor.id,
            "name": "natural_gas",
            "quantity": 1000.0,
        },
    )
    s.add(entry)
    await s.commit()
    assert entry.id is not None
    return factor.id, entry.id


# ── Per-module ITs ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "det, emission_type",
    [
        (DataEntryTypeEnum.it, EmissionType.equipment__it),
        (DataEntryTypeEnum.scientific, EmissionType.equipment__scientific),
        (DataEntryTypeEnum.other, EmissionType.equipment__other),
    ],
    ids=["it", "scientific", "other"],
)
async def test_equipment_factor_values_change_propagates(
    pg_dsn,
    det,
    emission_type,
):
    """Equipment (it / scientific / other) — JSON-link, ef change doubles
    kg_co2eq via the bulk-prefetch + ``upsert_by_data_entry`` path."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.equipment_electric_consumption
            )
            factor_id, entry_id = await _seed_equipment(
                s, module_id, det, emission_type
            )

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_kwh"
        )
        await _run_recalc(Sf, data_entry_type=det)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "det, emission_type",
    [
        (
            DataEntryTypeEnum.scientific_equipment,
            EmissionType.purchases__scientific_equipment,
        ),
        (DataEntryTypeEnum.other_purchases, EmissionType.purchases__other),
    ],
    ids=["purchase_common", "purchase_additional"],
)
async def test_purchase_factor_values_change_propagates(pg_dsn, det, emission_type):
    """Purchase (common / additional) — JSON-link, kind=purchase_institutional_code.
    Doubling ef doubles kg_co2eq."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.purchase
            )
            factor_id, entry_id = await _seed_purchase(s, module_id, det, emission_type)

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_currency"
        )
        await _run_recalc(Sf, data_entry_type=det)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_external_cloud_factor_values_change_propagates(pg_dsn):
    """External cloud — JSON-link, kind=provider, subkind=service_type."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.external_cloud_and_ai
            )
            factor_id, entry_id = await _seed_external_cloud(s, module_id)

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_currency"
        )
        await _run_recalc(Sf, data_entry_type=DataEntryTypeEnum.external_clouds)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_external_ai_factor_values_change_propagates(pg_dsn):
    """External AI — JSON-link, kind=provider, subkind=usage_type."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.external_cloud_and_ai
            )
            factor_id, entry_id = await _seed_external_ai(s, module_id)

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_request"
        )
        await _run_recalc(Sf, data_entry_type=DataEntryTypeEnum.external_ai)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_process_emissions_factor_values_change_propagates(pg_dsn):
    """Process emissions — JSON-link, kind=category, subkind=subcategory."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.process_emissions
            )
            factor_id, entry_id = await _seed_process_emissions(s, module_id)

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_unit"
        )
        await _run_recalc(Sf, data_entry_type=DataEntryTypeEnum.process_emissions)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)


@pytest.mark.asyncio
async def test_energy_combustion_factor_values_change_propagates(pg_dsn):
    """Buildings energy combustion — JSON-link, kind=name."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            module_id = await _seed_unit_and_module(
                s, module_type=ModuleTypeEnum.buildings
            )
            factor_id, entry_id = await _seed_energy_combustion(s, module_id)

        async with Sf() as s:
            initial_total = await _initial_compute(s, entry_id)
        assert initial_total > 0

        await _double_factor_value(
            Sf, factor_id=factor_id, value_key="ef_kg_co2eq_per_unit"
        )
        await _run_recalc(Sf, data_entry_type=DataEntryTypeEnum.energy_combustion)
    finally:
        await engine.dispose()

    new_total = await _read_kg_total_on_fresh_engine(pg_dsn, entry_id)
    assert new_total == pytest.approx(initial_total * 2.0, rel=1e-3)
