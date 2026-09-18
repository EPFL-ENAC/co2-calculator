"""A noisy entry payload resolves the canonical factor end-to-end (#1489).

Drives a CSV whose cells carry the noise real uploads have (spaces around
codes and names, an upper-case currency, a spreadsheet ``1.0`` on a numeric
facility id) through the real ``ModulePerYearCSVProvider`` chain against
Postgres, with the factor stored in canonical form. Pins three things at
once: the DTO normalization reaches ``data_entries.data`` (not only the typed
field), factor resolution matches on the normalized value, and the emission
is computed from that factor.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType

from .conftest import seeded_year_with_units
from .test_csv_ingest_matrix_pg import (
    _drive_csv_ingest,
    _ModuleSpec,
    _read_data_entries,
    _read_emissions_for_entries,
    _write_factor,
)

_YEAR = 2025

_PURCHASE = _ModuleSpec(
    module_type=ModuleTypeEnum.purchase,
    data_entry_type=DataEntryTypeEnum.it_equipment,
    csv_module="purchases_common",
    emission_type=EmissionType.purchases__it_equipment,
    factor_classification={
        "purchase_institutional_code": "PIC-IT",
        "purchase_additional_code": None,
        "currency": "eur",
    },
    factor_values={"ef_kg_co2eq_per_currency": 0.5, "currency": "eur"},
    # total_spent_amount=200.0 * ef=0.5, eur → eur so no FX.
    expected_kg_first_row=100.0,
)
_PURCHASE_CSV = (
    "unit_institutional_id,name,supplier,purchase_institutional_code,"
    "total_spent_amount,currency,purchase_additional_code,note\n"
    "{unit},  Smoke Microscope ,ACME,  PIC-IT  ,200.0,EUR,   ,\n"
)
_PURCHASE_EXPECTED_DATA = {
    "name": "Smoke Microscope",
    "purchase_institutional_code": "PIC-IT",
    "purchase_additional_code": None,
    "currency": "eur",
}

_FACILITY = _ModuleSpec(
    module_type=ModuleTypeEnum.research_facilities,
    data_entry_type=DataEntryTypeEnum.research_facilities,
    csv_module="researchfacilities_common",
    emission_type=EmissionType.research_facilities__facilities,
    factor_classification={"researchfacility_id": "1"},
    factor_values={"use_unit": "hours", "total_use": 100.0, "kg_co2eq_sum": 1000.0},
    # use=10 / total_use=100 * kg_co2eq_sum=1000.
    expected_kg_first_row=100.0,
)
_FACILITY_CSV = (
    "unit_institutional_id,researchfacility_id,researchfacility_name,use,use_unit,note\n"
    "{unit}, 1.0 ,  Smoke Facility ,10.0, hours ,\n"
)
_FACILITY_EXPECTED_DATA = {
    "researchfacility_id": "1",
    "researchfacility_name": "Smoke Facility",
    "use_unit": "hours",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("spec", "csv_template", "expected_data"),
    [
        pytest.param(_PURCHASE, _PURCHASE_CSV, _PURCHASE_EXPECTED_DATA, id="purchase"),
        pytest.param(_FACILITY, _FACILITY_CSV, _FACILITY_EXPECTED_DATA, id="facility"),
    ],
)
async def test_noisy_csv_row_resolves_canonical_factor(
    pg_dsn, spec: _ModuleSpec, csv_template: str, expected_data: dict
) -> None:
    engine = create_async_engine(pg_dsn, future=True)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as s:
            seeded = await seeded_year_with_units(s, year=_YEAR, n_units=1)
        unit = seeded.units[0]
        crm = seeded.modules_by_unit_and_type[(unit.id, int(spec.module_type))]
        async with session_factory() as s:
            factor_id = await _write_factor(s, spec=spec, year=_YEAR)

        parent, _children = await _drive_csv_ingest(
            spec=spec,
            session_factory=session_factory,
            csv_bytes=csv_template.format(unit=unit.institutional_id).encode(),
            target_unit_id=unit.id,
            year=_YEAR,
        )
        assert parent.state == IngestionState.FINISHED
        assert parent.result == IngestionResult.SUCCESS, parent.status_message

        async with session_factory() as s:
            entries = await _read_data_entries(s, carbon_report_module_id=crm.id)
            assert len(entries) == 1, "one CSV row, one entry"
            stored = {key: entries[0].data.get(key) for key in expected_data}
            assert stored == expected_data, "normalized values must reach data"
            emissions = await _read_emissions_for_entries(
                s, data_entry_ids=[entries[0].id]
            )
        assert [e.primary_factor_id for e in emissions] == [factor_id]
        assert emissions[0].kg_co2eq == pytest.approx(spec.expected_kg_first_row)
    finally:
        await engine.dispose()
