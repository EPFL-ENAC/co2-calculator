"""Unit tests for DataEntryRepository.get_professional_travel_trip_legs.

Issue #282 — the maps endpoint exposes raw plane + train legs with
coordinates; aggregation is the frontend's job. These tests pin the repo
contract: rows that don't resolve to a Location get dropped (and counted),
sums roll up DataEntryEmission rows per entry, and the institutional_id
filter scopes results to a single traveler.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryStatusEnum, DataEntryTypeEnum
from app.models.data_entry_emission import DataEntryEmission, EmissionType
from app.models.location import Location, TransportModeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository


async def _seed_module(db_session: AsyncSession) -> int:
    module = CarbonReportModule(
        carbon_report_id=1,
        module_type_id=ModuleTypeEnum.professional_travel.value,
        status="in_progress",
    )
    db_session.add(module)
    await db_session.flush()
    assert module.id is not None
    return module.id


async def _seed_location(
    db_session: AsyncSession,
    *,
    mode: TransportModeEnum,
    name: str,
    lat: float,
    lng: float,
    iata: str | None = None,
) -> str:
    natural_key = Location.compute_natural_key(
        transport_mode=mode,
        name=name,
        latitude=lat,
        longitude=lng,
        iata_code=iata,
    )
    db_session.add(
        Location(
            transport_mode=mode,
            name=name,
            latitude=lat,
            longitude=lng,
            iata_code=iata,
            natural_key=natural_key,
        )
    )
    await db_session.flush()
    return natural_key


async def _seed_plane(
    db_session: AsyncSession,
    *,
    module_id: int,
    origin_iata: str,
    destination_iata: str,
    kg_co2eq: float,
    user_iid: str = "11111",
    number_of_trips: int = 1,
) -> None:
    entry = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.plane,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_iata": origin_iata,
            "destination_iata": destination_iata,
            "user_institutional_id": user_iid,
            "number_of_trips": number_of_trips,
        },
    )
    db_session.add(entry)
    await db_session.flush()
    assert entry.id is not None
    db_session.add(
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.professional_travel__plane.value,
            kg_co2eq=kg_co2eq,
        )
    )
    await db_session.flush()


async def _seed_train(
    db_session: AsyncSession,
    *,
    module_id: int,
    origin_name: str,
    destination_name: str,
    kg_co2eq: float,
    origin_natural_key: str,
    destination_natural_key: str,
    user_iid: str = "11111",
    number_of_trips: int = 1,
) -> None:
    entry = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=DataEntryTypeEnum.train,
        status=DataEntryStatusEnum.PENDING,
        data={
            "origin_name": origin_name,
            "destination_name": destination_name,
            "origin_natural_key": origin_natural_key,
            "destination_natural_key": destination_natural_key,
            "user_institutional_id": user_iid,
            "number_of_trips": number_of_trips,
        },
    )
    db_session.add(entry)
    await db_session.flush()
    assert entry.id is not None
    db_session.add(
        DataEntryEmission(
            data_entry_id=entry.id,
            emission_type_id=EmissionType.professional_travel__train.value,
            kg_co2eq=kg_co2eq,
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_returns_plane_and_train_legs_with_coords(db_session: AsyncSession):
    repo = DataEntryRepository(db_session)
    module_id = await _seed_module(db_session)
    await _seed_location(
        db_session,
        mode=TransportModeEnum.plane,
        name="Geneva Airport",
        lat=46.2381,
        lng=6.1090,
        iata="GVA",
    )
    await _seed_location(
        db_session,
        mode=TransportModeEnum.plane,
        name="JFK",
        lat=40.6413,
        lng=-73.7781,
        iata="JFK",
    )
    lausanne_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Lausanne",
        lat=46.5167,
        lng=6.6333,
    )
    paris_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Paris",
        lat=48.8566,
        lng=2.3522,
    )

    await _seed_plane(
        db_session,
        module_id=module_id,
        origin_iata="GVA",
        destination_iata="JFK",
        kg_co2eq=1234.5,
    )
    await _seed_train(
        db_session,
        module_id=module_id,
        origin_name="Lausanne",
        destination_name="Paris",
        origin_natural_key=lausanne_key,
        destination_natural_key=paris_key,
        kg_co2eq=10.0,
    )

    legs, dropped = await repo.get_professional_travel_trip_legs(
        carbon_report_module_id=module_id,
    )

    assert dropped == 0
    modes = sorted(leg["mode"] for leg in legs)
    assert modes == ["plane", "train"]
    plane = next(leg for leg in legs if leg["mode"] == "plane")
    assert plane["origin_name"] == "Geneva Airport"
    assert plane["destination_name"] == "JFK"
    assert plane["origin_lat"] == pytest.approx(46.2381)
    assert plane["destination_lng"] == pytest.approx(-73.7781)
    assert plane["kg_co2eq"] == pytest.approx(1234.5)
    assert plane["number_of_trips"] == 1
    train = next(leg for leg in legs if leg["mode"] == "train")
    assert train["origin_name"] == "Lausanne"
    assert train["destination_name"] == "Paris"


@pytest.mark.asyncio
async def test_drops_rows_with_unresolved_location(db_session: AsyncSession):
    repo = DataEntryRepository(db_session)
    module_id = await _seed_module(db_session)
    await _seed_location(
        db_session,
        mode=TransportModeEnum.plane,
        name="Geneva Airport",
        lat=46.2381,
        lng=6.1090,
        iata="GVA",
    )
    # Resolvable
    await _seed_plane(
        db_session,
        module_id=module_id,
        origin_iata="GVA",
        destination_iata="GVA",
        kg_co2eq=1.0,
    )
    # Unresolvable destination IATA
    await _seed_plane(
        db_session,
        module_id=module_id,
        origin_iata="GVA",
        destination_iata="XXX",
        kg_co2eq=2.0,
    )

    legs, dropped = await repo.get_professional_travel_trip_legs(
        carbon_report_module_id=module_id,
    )

    assert len(legs) == 1
    assert dropped == 1


@pytest.mark.asyncio
async def test_institutional_id_filter_scopes_to_one_traveler(
    db_session: AsyncSession,
):
    repo = DataEntryRepository(db_session)
    module_id = await _seed_module(db_session)
    await _seed_location(
        db_session,
        mode=TransportModeEnum.plane,
        name="Geneva Airport",
        lat=46.2381,
        lng=6.1090,
        iata="GVA",
    )

    await _seed_plane(
        db_session,
        module_id=module_id,
        origin_iata="GVA",
        destination_iata="GVA",
        kg_co2eq=1.0,
        user_iid="alice",
    )
    await _seed_plane(
        db_session,
        module_id=module_id,
        origin_iata="GVA",
        destination_iata="GVA",
        kg_co2eq=2.0,
        user_iid="bob",
    )

    legs, _dropped = await repo.get_professional_travel_trip_legs(
        carbon_report_module_id=module_id,
        institutional_id_filter="alice",
    )

    assert len(legs) == 1
    assert legs[0]["kg_co2eq"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_leg_carries_number_of_trips(db_session: AsyncSession):
    """A single DataEntry can stand for many trips; the leg must report the
    stored ``number_of_trips`` so the client sums it rather than counting rows.
    """
    repo = DataEntryRepository(db_session)
    module_id = await _seed_module(db_session)
    lausanne_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Lausanne",
        lat=46.5167,
        lng=6.6333,
    )
    zurich_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Zurich",
        lat=47.3769,
        lng=8.5417,
    )

    await _seed_train(
        db_session,
        module_id=module_id,
        origin_name="Lausanne",
        destination_name="Zurich",
        origin_natural_key=lausanne_key,
        destination_natural_key=zurich_key,
        kg_co2eq=500.0,
        number_of_trips=100,
    )

    legs, dropped = await repo.get_professional_travel_trip_legs(
        carbon_report_module_id=module_id,
    )

    assert dropped == 0
    assert len(legs) == 1
    assert legs[0]["number_of_trips"] == 100


@pytest.mark.asyncio
async def test_train_join_disambiguates_same_name_stations(
    db_session: AsyncSession,
):
    """Station names are not unique ("Berne" exists in CH and DE). The join
    must resolve via the entry's natural_key, returning exactly one leg at the
    intended station — not a leg per same-named location.
    """
    repo = DataEntryRepository(db_session)
    module_id = await _seed_module(db_session)
    swiss_berne_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Berne",
        lat=46.9480,
        lng=7.4474,
    )
    # Same name, different place (a German "Berne") → distinct natural_key.
    await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Berne",
        lat=53.1667,
        lng=8.5000,
    )
    berlin_key = await _seed_location(
        db_session,
        mode=TransportModeEnum.train,
        name="Berlin",
        lat=52.5200,
        lng=13.4050,
    )

    await _seed_train(
        db_session,
        module_id=module_id,
        origin_name="Berne",
        destination_name="Berlin",
        origin_natural_key=swiss_berne_key,
        destination_natural_key=berlin_key,
        kg_co2eq=42.0,
    )

    legs, dropped = await repo.get_professional_travel_trip_legs(
        carbon_report_module_id=module_id,
    )

    assert dropped == 0
    assert len(legs) == 1
    assert legs[0]["origin_lat"] == pytest.approx(46.9480)
    assert legs[0]["origin_lng"] == pytest.approx(7.4474)
