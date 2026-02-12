"""Tests for ProfessionalTravelCSVProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.services.data_ingestion.base_csv_provider import StatsDict
from app.services.data_ingestion.csv_providers.professional_travel_csv_provider import (
    ProfessionalTravelCSVProvider,
)

# ── Fixtures ────────────────────────────────────────────────────


def _make_stats() -> StatsDict:
    return {
        "rows_processed": 0,
        "rows_with_factors": 0,
        "rows_without_factors": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }


def _make_setup_result(
    csv_text: str = "",
    configured_data_entry_type_id: int = DataEntryTypeEnum.trips.value,
) -> dict:
    """Minimal setup_result dict expected by _process_row."""
    from app.schemas.data_entry import BaseModuleHandler

    handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum.trips)
    expected_columns = set(handler.create_dto.model_fields.keys())
    return {
        "csv_text": csv_text,
        "entity_type": EntityType.MODULE_UNIT_SPECIFIC,
        "configured_data_entry_type_id": configured_data_entry_type_id,
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": expected_columns,
        "required_columns": set(),
        "processing_path": "processing/1/test.csv",
        "filename": "test.csv",
    }


@pytest.fixture
def base_config():
    return {
        "job_id": 1,
        "file_path": "tmp/travel.csv",
        "carbon_report_module_id": 10,
        "data_entry_type_id": DataEntryTypeEnum.trips.value,
    }


@pytest.fixture
def provider(base_config):
    """Create provider with mocked lazy properties."""
    mock_session = AsyncMock()
    prov = ProfessionalTravelCSVProvider(
        base_config, user=None, data_session=mock_session
    )
    prov._files_store = MagicMock()
    prov._repo = MagicMock()
    prov._repo.update_ingestion_job = AsyncMock()
    return prov


# ── _build_iata_cache ───────────────────────────────────────────


class TestBuildIataCache:
    @pytest.mark.asyncio
    async def test_builds_cache_from_query(self, provider):
        row_gva = MagicMock(iata_code="GVA", id=1)
        row_jfk = MagicMock(iata_code="jfk", id=2)  # lowercase
        mock_result = MagicMock()
        mock_result.all.return_value = [row_gva, row_jfk]
        provider.data_session.execute = AsyncMock(return_value=mock_result)

        cache = await provider._build_iata_cache()

        assert cache == {"GVA": 1, "JFK": 2}
        provider.data_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_cache_when_no_locations(self, provider):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        provider.data_session.execute = AsyncMock(return_value=mock_result)

        cache = await provider._build_iata_cache()

        assert cache == {}


# ── _build_train_name_cache ──────────────────────────────────────


class TestBuildTrainNameCache:
    @pytest.mark.asyncio
    async def test_builds_cache_from_query(self, provider):
        row_lausanne = MagicMock(name="Lausanne", id=10)
        row_zurich = MagicMock(name="Zürich HB", id=20)
        # MagicMock uses 'name' as a constructor kwarg, so set it explicitly
        row_lausanne.name = "Lausanne"
        row_zurich.name = "Zürich HB"
        mock_result = MagicMock()
        mock_result.all.return_value = [row_lausanne, row_zurich]
        provider.data_session.execute = AsyncMock(return_value=mock_result)

        cache = await provider._build_train_name_cache()

        assert cache == {"Lausanne": 10, "Zürich HB": 20}
        provider.data_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_cache_when_no_stations(self, provider):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        provider.data_session.execute = AsyncMock(return_value=mock_result)

        cache = await provider._build_train_name_cache()

        assert cache == {}


# ── _process_row ────────────────────────────────────────────────


class TestProcessRow:
    @pytest.mark.asyncio
    async def test_valid_row_creates_data_entry(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Alice",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, factor = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert isinstance(entry, DataEntry)
        assert entry.data["origin_location_id"] == 100
        assert entry.data["destination_location_id"] == 200
        assert entry.data["traveler_name"] == "Alice"
        assert stats["rows_skipped"] == 0

    @pytest.mark.asyncio
    async def test_sciper_mapped_to_traveler_id(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Bob",
            "sciper": "123456",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert entry.data["traveler_id"] == 123456

    @pytest.mark.asyncio
    async def test_number_of_trips_passed_through(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Charlie",
            "number_of_trips": "3",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert entry.data["number_of_trips"] == 3

    @pytest.mark.asyncio
    async def test_departure_date_passed_through(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Dave",
            "departure_date": "2024-06-15",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert entry is not None

    @pytest.mark.asyncio
    async def test_unsupported_transport_mode_skips_row(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "bus",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Eve",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Unsupported transport_mode" in err
        assert stats["rows_skipped"] == 1

    @pytest.mark.asyncio
    async def test_valid_train_row_creates_data_entry(self, provider):
        provider._train_name_cache = {"Lausanne": 300, "Zürich HB": 400}
        row = {
            "transport_mode": "train",
            "from": "Lausanne",
            "to": "Zürich HB",
            "traveler_name": "Fiona",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, factor = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert isinstance(entry, DataEntry)
        assert entry.data["origin_location_id"] == 300
        assert entry.data["destination_location_id"] == 400
        assert entry.data["traveler_name"] == "Fiona"
        assert stats["rows_skipped"] == 0

    @pytest.mark.asyncio
    async def test_unknown_train_origin_skips_row(self, provider):
        provider._train_name_cache = {"Zürich HB": 400}
        row = {
            "transport_mode": "train",
            "from": "Unknown Station",
            "to": "Zürich HB",
            "traveler_name": "George",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Origin 'Unknown Station' not found" in err
        assert stats["rows_skipped"] == 1

    @pytest.mark.asyncio
    async def test_unknown_train_destination_skips_row(self, provider):
        provider._train_name_cache = {"Lausanne": 300}
        row = {
            "transport_mode": "train",
            "from": "Lausanne",
            "to": "Nowhere",
            "traveler_name": "Hannah",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Destination 'Nowhere' not found" in err
        assert stats["rows_skipped"] == 1

    @pytest.mark.asyncio
    async def test_unknown_origin_iata_skips_row(self, provider):
        provider._iata_cache = {"SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "XXX",
            "to": "SFO",
            "traveler_name": "Frank",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Origin 'XXX' not found" in err
        assert stats["rows_skipped"] == 1

    @pytest.mark.asyncio
    async def test_unknown_destination_iata_skips_row(self, provider):
        provider._iata_cache = {"GVA": 100}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "YYY",
            "traveler_name": "Grace",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Destination 'YYY' not found" in err
        assert stats["rows_skipped"] == 1

    @pytest.mark.asyncio
    async def test_iata_codes_are_case_insensitive(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "gva",
            "to": "sfo",
            "traveler_name": "Henry",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        assert entry.data["origin_location_id"] == 100
        assert entry.data["destination_location_id"] == 200

    @pytest.mark.asyncio
    async def test_empty_transport_mode_skips_row(self, provider):
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Ivy",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert entry is None
        assert "Unsupported transport_mode" in err

    @pytest.mark.asyncio
    async def test_float_ids_are_coerced_to_int(self, provider):
        """Ensure float values from CSV parsing are coerced to int."""
        provider._iata_cache = {"GVA": 100, "SFO": 200}
        row = {
            "transport_mode": "plane",
            "from": "GVA",
            "to": "SFO",
            "traveler_name": "Jack",
            "number_of_trips": "2",
        }
        stats = _make_stats()
        setup = _make_setup_result()

        entry, err, _ = await provider._process_row(row, 1, setup, stats, 100)

        assert err is None
        # These should all be int, not float
        assert isinstance(entry.data["origin_location_id"], int)
        assert isinstance(entry.data["destination_location_id"], int)


# ── _setup_and_validate ─────────────────────────────────────────


class TestSetupAndValidate:
    @pytest.mark.asyncio
    async def test_raises_without_file_path(self):
        config = {
            "job_id": 1,
            "carbon_report_module_id": 10,
            "data_entry_type_id": DataEntryTypeEnum.trips.value,
        }
        mock_session = AsyncMock()
        prov = ProfessionalTravelCSVProvider(
            config, user=None, data_session=mock_session
        )
        prov._files_store = MagicMock()
        prov._repo = MagicMock()
        prov._repo.update_ingestion_job = AsyncMock()

        with pytest.raises(ValueError, match="Missing source_file_path"):
            await prov._setup_and_validate()

    @pytest.mark.asyncio
    async def test_successful_setup(self, provider):
        csv_content = "transport_mode,from,to,traveler_name\nplane,GVA,SFO,Alice\n"
        provider._files_store.move_file = AsyncMock(return_value=True)
        provider._files_store.get_file = AsyncMock(
            return_value=(csv_content.encode("utf-8"), "text/csv")
        )
        # Mock IATA cache build
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(iata_code="GVA", id=1),
            MagicMock(iata_code="SFO", id=2),
        ]
        provider.data_session.execute = AsyncMock(return_value=mock_result)

        result = await provider._setup_and_validate()

        assert result["entity_type"] == EntityType.MODULE_UNIT_SPECIFIC
        assert result["csv_text"] == csv_content
        assert result["filename"] == "travel.csv"
        assert provider._iata_cache == {"GVA": 1, "SFO": 2}

    @pytest.mark.asyncio
    async def test_missing_required_csv_column_raises(self, provider):
        # CSV missing "from" column
        csv_content = "transport_mode,to,traveler_name\nplane,SFO,Alice\n"
        provider._files_store.move_file = AsyncMock(return_value=True)
        provider._files_store.get_file = AsyncMock(
            return_value=(csv_content.encode("utf-8"), "text/csv")
        )

        with pytest.raises(ValueError, match="missing required columns"):
            await provider._setup_and_validate()
