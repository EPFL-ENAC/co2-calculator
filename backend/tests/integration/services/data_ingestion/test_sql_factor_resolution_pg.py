"""SQL factor resolution in list queries (plan 1661-sql-factor-resolution).

``get_submodule_data`` joins ``Factor`` via a correlated scalar subquery on
the entry's classification — not via emission rows — so factor-backed
sort/filter work for entries whose emissions are not computed yet.  The
sqlite unit tests in ``tests/unit/repositories/test_data_entry_repo.py``
pin the resolution chain; this test pins the JSONB operator path and the
cross-row ordering on real Postgres.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.modules.emissions import EmissionType
from app.repositories.data_entry_repo import DataEntryRepository


@pytest.mark.asyncio
async def test_uncomputed_entry_sorts_and_displays_by_resolved_factor(pg_dsn):
    """Two equipment entries — one WITH emission rows, one without any —
    must both expose factor-backed columns and sort by them consistently."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            unit = Unit(
                institutional_code="TEST-SQLRES",
                institutional_id="TEST-UNIT-SQLRES",
                name="Test Unit",
                level=1,
            )
            s.add(unit)
            await s.commit()
            report = CarbonReport(year=2025, unit_id=unit.id)
            s.add(report)
            await s.commit()
            module = CarbonReportModule(
                carbon_report_id=report.id,
                module_type_id=ModuleTypeEnum.equipment.value,
            )
            s.add(module)
            await s.commit()
            module_id = module.id
            assert module_id is not None

            low = Factor(
                emission_type_id=EmissionType.equipment__it.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                classification={"equipment_class": "Laptop", "sub_class": "Std"},
                values={"active_power_w": 10.0, "standby_power_w": 1.0},
                year=2025,
            )
            high = Factor(
                emission_type_id=EmissionType.equipment__it.value,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                classification={"equipment_class": "Server", "sub_class": "Std"},
                values={"active_power_w": 500.0, "standby_power_w": 50.0},
                year=2025,
            )
            s.add_all([low, high])
            await s.commit()

            computed = DataEntry(
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                data={
                    "name": "Computed",
                    "equipment_class": "Laptop",
                    "sub_class": "Std",
                },
                year=2025,
            )
            uncomputed = DataEntry(
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                data={
                    "name": "Uncomputed",
                    "equipment_class": "Server",
                    "sub_class": "Std",
                },
                year=2025,
            )
            s.add_all([computed, uncomputed])
            await s.commit()
            # Emission rows only for `computed` — `uncomputed` relies purely
            # on the classification subquery.
            s.add(
                DataEntryEmission(
                    data_entry_id=computed.id,
                    emission_type_id=EmissionType.equipment__it.value,
                    primary_factor_id=low.id,
                    kg_co2eq=12.3,
                )
            )
            await s.commit()

            repo = DataEntryRepository(s)
            response = await repo.get_submodule_data(
                carbon_report_module_id=module_id,
                data_entry_type_id=DataEntryTypeEnum.it.value,
                limit=10,
                offset=0,
                sort_by="active_power_w",
                sort_order="desc",
            )
    finally:
        await engine.dispose()

    assert [i.name for i in response.items] == ["Uncomputed", "Computed"], (
        "sort by the factor-backed column must place the uncomputed "
        "Server entry (500 W) before the computed Laptop entry (10 W)"
    )
    assert response.items[0].active_power_w == 500.0
    assert response.items[1].active_power_w == 10.0
