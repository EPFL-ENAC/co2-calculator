"""Integration test: plane table search matches joined airport names (#1436).

Plane entries store only IATA codes in ``DataEntry.data``; the displayed
from/to columns are ``Location.name`` resolved through the plane Location
JOIN. Searching must therefore match the airport name (and still match the
raw IATA code), and the pagination count query must apply the same JOINs so
``total_items`` agrees with the returned page.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.constants import ModuleStatus
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository


def _plane_location(
    name: str, iata: str, latitude: float, longitude: float, country_code: str
) -> Location:
    return Location(
        transport_mode=TransportModeEnum.plane,
        name=name,
        iata_code=iata,
        latitude=latitude,
        longitude=longitude,
        country_code=country_code,
        natural_key=Location.compute_natural_key(
            transport_mode=TransportModeEnum.plane, iata_code=iata
        ),
    )


def _plane_entry(module_id: int, origin_iata: str, destination_iata: str) -> DataEntry:
    return DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_iata": origin_iata,
            "destination_iata": destination_iata,
            "user_institutional_id": "u1",
            "number_of_trips": 1,
            "cabin_class": "economy",
        },
    )


@pytest.mark.asyncio
async def test_plane_search_matches_airport_names_and_iata(db_session: AsyncSession):
    repo = DataEntryRepository(db_session)

    report = CarbonReport(year=2025, unit_id=1, overall_status=0)
    db_session.add(report)
    await db_session.flush()
    module = CarbonReportModule(
        carbon_report_id=report.id,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status=ModuleStatus.NOT_STARTED,
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add(
        _plane_location("Paris Charles de Gaulle", "CDG", 49.0097, 2.5479, "FR")
    )
    db_session.add(_plane_location("Zurich Airport", "ZRH", 47.4647, 8.5492, "CH"))
    db_session.add(_plane_location("Geneva Airport", "GVA", 46.2381, 6.1089, "CH"))
    db_session.add(_plane_entry(module.id, "CDG", "ZRH"))
    db_session.add(_plane_entry(module.id, "GVA", "ZRH"))
    await db_session.commit()

    async def search(term: str):
        return await repo.get_submodule_data(
            carbon_report_module_id=module.id,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            limit=10,
            offset=0,
            sort_by="origin_name",
            sort_order="asc",
            filter=term,
        )

    # Origin airport name — only the CDG entry matches, and the pagination
    # count must agree with the page (guards the count-query JOINs).
    result = await search("Paris")
    assert result.count == 1, f"expected 1 item for 'Paris', got {result.count}"
    assert result.items[0].origin_iata == "CDG"  # type: ignore[attr-defined]
    assert result.summary.total_items == 1

    # Destination airport name — both entries fly to Zurich.
    result = await search("Zurich")
    assert result.count == 2, f"expected 2 items for 'Zurich', got {result.count}"
    assert result.summary.total_items == 2

    # Raw IATA code search keeps working.
    result = await search("CDG")
    assert result.count == 1, f"expected 1 item for 'CDG', got {result.count}"
    assert result.items[0].origin_iata == "CDG"  # type: ignore[attr-defined]
    assert result.summary.total_items == 1
