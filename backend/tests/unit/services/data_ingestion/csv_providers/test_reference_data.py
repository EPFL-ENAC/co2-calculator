"""Tests for ReferenceDataCSVProvider."""

from unittest.mock import MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion.csv_providers.reference_data import (
    LOCATIONS_REQUIRED_COLUMNS,
    ReferenceDataCSVProvider,
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
