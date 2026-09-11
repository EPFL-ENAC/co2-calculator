"""Tests for ReferenceDataCSVProvider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.building_room import BuildingRoom
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.modules.emissions import EmissionType
from app.services.data_ingestion.csv_providers.reference_data import (
    BUILDING_ROOMS_EXPECTED_COLUMNS,
    BUILDING_ROOMS_REQUIRED_COLUMNS,
    LOCATIONS_REQUIRED_COLUMNS,
    ReferenceDataCSVProvider,
    _non_negative_surface,
    _to_float,
    _validated_room_type,
)
from app.services.data_ingestion.provider_factory import ProviderFactory


def _make_provider(**overrides) -> ReferenceDataCSVProvider:
    config = {"job_id": 1, "year": 2024, **overrides}
    return ReferenceDataCSVProvider(config=config, data_session=MagicMock())


def test_entity_type_and_target_type():
    provider = _make_provider()
    assert provider.entity_type == EntityType.MODULE_PER_YEAR
    assert provider.target_type == TargetType.REFERENCE_DATA
    assert provider.provider_name == IngestionMethod.csv


def test_provider_factory_routes_reference_csv_for_every_module():
    # FE pins module_type_id (2 for travel, 3 for buildings), so the registry
    # must answer for every concrete module rather than just (None, ...).
    for module_type in ModuleTypeEnum:
        provider_class = ProviderFactory.get_provider_by_keys(
            module_type,
            IngestionMethod.csv,
            TargetType.REFERENCE_DATA,
            EntityType.MODULE_PER_YEAR,
        )
        assert provider_class is ReferenceDataCSVProvider, (
            f"missing reference CSV provider for module={module_type}"
        )


def test_resolve_data_entry_type_requires_value():
    provider = _make_provider()
    with pytest.raises(ValueError, match="data_entry_type_id is required"):
        provider._resolve_data_entry_type()


def test_resolve_data_entry_type_returns_enum():
    provider = _make_provider(data_entry_type_id=DataEntryTypeEnum.plane.value)
    assert provider._resolve_data_entry_type() == DataEntryTypeEnum.plane


def test_validate_headers_rejects_empty_csv():
    with pytest.raises(ValueError, match="empty"):
        ReferenceDataCSVProvider._validate_headers(
            "", LOCATIONS_REQUIRED_COLUMNS, LOCATIONS_REQUIRED_COLUMNS
        )


def test_validate_headers_rejects_missing_required():
    csv_text = "transport_mode,name\nplane,JFK\n"
    with pytest.raises(ValueError, match="missing required columns"):
        ReferenceDataCSVProvider._validate_headers(
            csv_text,
            LOCATIONS_REQUIRED_COLUMNS,
            LOCATIONS_REQUIRED_COLUMNS,
        )


def test_validate_headers_accepts_full_set():
    csv_text = "transport_mode,name,latitude,longitude\nplane,JFK,40.6,-73.7\n"
    # Should not raise — every required column is present.
    ReferenceDataCSVProvider._validate_headers(
        csv_text,
        LOCATIONS_REQUIRED_COLUMNS,
        LOCATIONS_REQUIRED_COLUMNS,
    )


def test_validate_headers_rejects_misspelled_column():
    # Regression test for #1545: a misspelled column (e.g.
    # room_surface_square_meters instead of room_surface_square_meter) must
    # fail loudly rather than silently resolving to None on every row. Every
    # rooms column is required (#2716), so the typo surfaces as the missing one.
    csv_text = (
        "building_location,building_name,room_name,room_type,"
        "room_surface_square_meters\n"
        "ECUBLENS,GC,AI0122,office,12\n"
    )
    with pytest.raises(ValueError, match="missing required.*room_surface_square_meter"):
        ReferenceDataCSVProvider._validate_headers(
            csv_text,
            BUILDING_ROOMS_REQUIRED_COLUMNS,
            BUILDING_ROOMS_EXPECTED_COLUMNS,
        )


def test_validate_headers_rejects_unknown_columns():
    csv_text = (
        "building_location,building_name,room_name,room_type,"
        "room_surface_square_meter,floor\n"
        "ECUBLENS,GC,AI0122,office,12,3\n"
    )
    with pytest.raises(ValueError, match="unexpected columns"):
        ReferenceDataCSVProvider._validate_headers(
            csv_text,
            BUILDING_ROOMS_REQUIRED_COLUMNS,
            BUILDING_ROOMS_EXPECTED_COLUMNS,
        )


def test_parse_locations_filters_by_transport_mode():
    csv_text = (
        "transport_mode,airport_size,name,latitude,longitude,"
        "continent,country_code,municipality,iata_code,keywords\n"
        "plane,large_airport,JFK,40.6,-73.7,NA,US,New York,JFK,\n"
        "train,,Lyon Part-Dieu,45.76,4.86,EU,FR,Lyon,,\n"
        "plane,medium_airport,LGA,40.77,-73.87,NA,US,New York,LGA,\n"
    )

    plane_rows = ReferenceDataCSVProvider._parse_locations_rows(
        csv_text, DataEntryTypeEnum.plane
    )
    train_rows = ReferenceDataCSVProvider._parse_locations_rows(
        csv_text, DataEntryTypeEnum.train
    )

    assert [r[2] for r in plane_rows] == ["JFK", "LGA"]
    assert [r[2] for r in train_rows] == ["Lyon Part-Dieu"]


@pytest.mark.asyncio
async def test_ingest_locations_replaces_same_mode_only(db_session):
    """A train reference upload must ERASE prior train rows and re-insert,
    while leaving plane rows untouched (scoped replace, like building rooms).
    Without this, re-uploading from a new source accumulates stale stations
    and orphans nothing it should keep.
    """
    from sqlalchemy import select

    from app.models.location import Location, TransportModeEnum

    db_session.add(
        Location(
            transport_mode=TransportModeEnum.train,
            name="StaleStation",
            latitude=40.0,
            longitude=2.0,
            country_code="ES",
            natural_key="train:es:stalestation:40.0:2.0",
        )
    )
    db_session.add(
        Location(
            transport_mode=TransportModeEnum.plane,
            name="KeepAirport",
            latitude=48.0,
            longitude=2.0,
            country_code="FR",
            iata_code="CDG",
            natural_key="plane:CDG",
        )
    )
    await db_session.flush()

    provider = ReferenceDataCSVProvider(config={"job_id": 1}, data_session=db_session)
    # 10-column row order: mode, airport_size, name, lat, lon, continent,
    # country_code, municipality, iata_code, keywords.
    new_rows = [
        ["train", "", "FreshStation", "46.0", "6.0", "", "CH", "", "", "FreshStation"],
    ]

    await provider._ingest_locations_sqlite(new_rows, DataEntryTypeEnum.train)

    names = {
        loc.name for loc in (await db_session.execute(select(Location))).scalars().all()
    }
    assert "StaleStation" not in names, "prior train rows must be erased on reupload"
    assert "FreshStation" in names, "new train rows must be inserted"
    assert "KeepAirport" in names, "a train upload must not touch plane rows"


@pytest.mark.asyncio
async def test_validate_connection_requires_file_path():
    provider = _make_provider()
    assert await provider.validate_connection() is False


def test_job_type_for_reference_data():
    # ``_job_type_for`` must route REFERENCE_DATA → reference_ingest so the
    # csv_ingest handler's emission_recalc fan-out doesn't fire against a
    # job that has no factor or data-entry rows to recalculate.
    from app.api.v1.data_sync import _job_type_for

    assert (
        _job_type_for(TargetType.REFERENCE_DATA, IngestionMethod.csv)
        == "reference_ingest"
    )
    assert (
        _job_type_for(TargetType.REFERENCE_DATA, IngestionMethod.api)
        == "reference_ingest"
    )
    # Sanity-check the other branches still return their original mapping.
    assert _job_type_for(TargetType.FACTORS, IngestionMethod.csv) == "factor_ingest"
    assert _job_type_for(TargetType.DATA_ENTRIES, IngestionMethod.csv) == "csv_ingest"


def test_reference_ingest_handler_is_registered():
    # Bootstrap imports reference_ingest_tasks so the @register decorator fires;
    # without it run_job would raise ``No handler registered for
    # job_type='reference_ingest'`` once the dispatcher hands it off.
    from app.tasks.bootstrap import bootstrap_handlers
    from app.tasks.registry import get_handler

    bootstrap_handlers()
    handler = get_handler("reference_ingest")
    assert callable(handler)


def test_to_float_blank_and_dash_are_none() -> None:
    assert _to_float(None) is None
    assert _to_float("") is None
    assert _to_float("  ") is None
    assert _to_float("-") is None
    assert _to_float("18.5") == 18.5


def test_to_float_rejects_unparseable_present_value() -> None:
    """#1489 (audit F-2): a present-but-unparseable numeric (wrong decimal
    separator, stray text) must fail the upload, not silently become NULL —
    the same failure mode as #1545's typo'd column, one level down.
    """
    with pytest.raises(ValueError, match="Invalid numeric value"):
        _to_float("12,5")


def test_validated_room_type_accepts_vocabulary_and_blank() -> None:
    assert _validated_room_type("office") == "office"
    assert _validated_room_type(" laboratories ") == "laboratories"
    assert _validated_room_type("") is None
    assert _validated_room_type(None) is None


def test_validated_room_type_rejects_unknown_value() -> None:
    """#2588: the entry side rejects unknown room types, the reference side
    accepted anything. Both must enforce the same vocabulary.
    """
    with pytest.raises(ValueError, match="Invalid room_type"):
        _validated_room_type("swimming-pool")


def test_non_negative_surface() -> None:
    assert _non_negative_surface(18.5) == 18.5
    assert _non_negative_surface(0.0) == 0.0
    assert _non_negative_surface(None) is None
    with pytest.raises(ValueError, match="non-negative"):
        _non_negative_surface(-3.0)


_ROOMS_HEADER = (
    "building_location,building_name,room_name,room_type,room_surface_square_meter"
)
_KNOWN_BUILDINGS_PATCH = (
    "app.services.data_ingestion.csv_providers.reference_data.FactorRepository"
)


def _known_buildings(*names: str):
    """Stand in for the factors table: the buildings that have a factor row."""
    patcher = patch(_KNOWN_BUILDINGS_PATCH)
    repo_cls = patcher.start()
    repo_cls.return_value.list_classification_values = AsyncMock(
        return_value=set(names)
    )
    return patcher


async def _ingest_rooms(csv_rows: str, *known: str) -> dict:
    patcher = _known_buildings(*known)
    try:
        return await _make_provider()._ingest_building_rooms(
            f"{_ROOMS_HEADER}\n{csv_rows}"
        )
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_bad_room_type() -> None:
    with pytest.raises(ValueError, match="Invalid room_type"):
        await _ingest_rooms("ECUBLENS,AAB,AAB 0 01,swimming-pool,18.0\n", "AAB")


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_negative_surface() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        await _ingest_rooms("ECUBLENS,AAB,AAB 0 01,office,-18.0\n", "AAB")


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_empty_surface_with_its_line() -> None:
    """#2716: an empty surface cell used to import as NULL and every entry
    naming the room computed to nothing. Line 1 is the header, so the
    offending row is file line 3.
    """
    with pytest.raises(ValueError, match=r"line 3: empty room_surface_square_meter"):
        await _ingest_rooms(
            "ECUBLENS,AAB,AAB 0 01,office,18.0\nECUBLENS ,AI,AI 2 46.1,laboratories,\n",
            "AAB",
            "AI",
        )


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_empty_mandatory_cells() -> None:
    """Rows missing a name used to be skipped and counted, not rejected."""
    with pytest.raises(ValueError, match=r"line 2: empty building_name, room_type"):
        await _ingest_rooms("ECUBLENS,,AAB 0 01,,18.0\n", "AAB")


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_duplicates_spaces_ignored() -> None:
    """Exact duplicates and spacing-only variants both collapse to one room;
    the message points at both lines so the data manager can delete one.
    """
    with pytest.raises(ValueError) as exc_info:
        await _ingest_rooms(
            "ECUBLENS,AAB,AAB 0 14,office,25.81\n"
            "ECUBLENS,AAB,AAB 0 14,office,25.81\n"
            "ECUBLENS,AI,AI 3147,office,11.94\n"
            "ECUBLENS,AI,AI 3 147,office,11.94\n",
            "AAB",
            "AI",
        )
    message = str(exc_info.value)
    assert "line 3: room 'AAB 0 14' already listed on line 2" in message
    assert "line 5: room 'AI 3 147' already listed on line 4" in message


@pytest.mark.asyncio
async def test_ingest_building_rooms_rejects_building_without_factors() -> None:
    with pytest.raises(ValueError, match=r"line 2: building 'ZEBRAFISH'"):
        await _ingest_rooms(
            "ECUBLENS,ZEBRAFISH,ZEBRAFISH facility,laboratories,40.0\n", "AAB"
        )


@pytest.mark.asyncio
async def test_ingest_building_rooms_names_the_missing_factors_upload() -> None:
    """A factor-less database is one message, not one line per room."""
    with pytest.raises(ValueError, match="upload building_rooms_factors.csv"):
        await _ingest_rooms("ECUBLENS,AAB,AAB 0 01,office,18.0\n")


@pytest.mark.asyncio
async def test_ingest_building_rooms_reports_every_defect_class_at_once() -> None:
    with pytest.raises(ValueError) as exc_info:
        await _ingest_rooms(
            "ECUBLENS,AAB,AAB 0 01,office,\n"
            "ECUBLENS,AAB,AAB 0 01,office,18.0\n"
            "GENEVE,B,B 3 3 222.129,laboratories,9.0\n",
            "AAB",
        )
    message = str(exc_info.value)
    assert "Rows with an empty mandatory cell (1):" in message
    assert "Rooms listed more than once (1):" in message
    assert "Buildings with no row in the buildings factors (1):" in message


@pytest.mark.asyncio
async def test_ingest_building_rooms_valid_rows_still_pass(db_session) -> None:
    """Zero is a valid surface, cells are trimmed, and the building check
    reads the real factors table.
    """
    from sqlalchemy import select

    db_session.add(
        Factor(
            emission_type_id=EmissionType.buildings__rooms.value,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            classification={
                "building_name": "AAB",
                "room_type": "office",
                "energy_type": "electric",
            },
            values={"ef_kg_co2eq_per_kwh": 0.1},
            year=2025,
        )
    )
    await db_session.flush()
    provider = ReferenceDataCSVProvider(
        config={"job_id": 1, "year": 2024}, data_session=db_session
    )
    csv_text = (
        f"{_ROOMS_HEADER}\n"
        "ECUBLENS,AAB,AAB 0 01,office,18.0\n"
        "ECUBLENS ,AAB,AAB 0 02,archives,0.0\n"
    )
    stats = await provider._ingest_building_rooms(csv_text)
    assert stats == {"rows_processed": 2, "rows_skipped": 0, "rows_inserted": 2}
    rows = (await db_session.exec(select(BuildingRoom))).scalars().all()
    assert {r.building_location for r in rows} == {"ECUBLENS"}
    assert {r.room_surface_square_meter for r in rows} == {18.0, 0.0}
