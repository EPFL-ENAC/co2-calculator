"""Tests for ProfessionalTravelApiProvider.

Covers pure/static functions and transform_data logic.
Heavy integration methods (_load_data, _resolve_carbon_report_modules, ingest)
are tested via mocking.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
    normalize_vds_payload,
    to_bool,
)

# ---------------------------------------------------------------------------
# to_bool
# ---------------------------------------------------------------------------


class TestToBool:
    def test_true_values(self):
        for v in ("true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"):
            assert to_bool(v) is True

    def test_false_values(self):
        for v in ("false", "0", "no", "off", "", "random"):
            assert to_bool(v) is False


# ---------------------------------------------------------------------------
# normalize_vds_payload
# ---------------------------------------------------------------------------


class TestNormalizeVdsPayload:
    def test_moves_return_format_from_query_to_options(self):
        payload = {"query": {"returnFormat": "OBJECTS", "fields": []}}
        result, changed = normalize_vds_payload(payload)
        assert changed is True
        assert "returnFormat" not in result["query"]
        assert result["options"]["returnFormat"] == "OBJECTS"

    def test_removes_max_rows(self):
        payload = {"query": {"maxRows": 100, "fields": []}}
        result, changed = normalize_vds_payload(payload)
        assert changed is True
        assert "maxRows" not in result["query"]

    def test_no_change_when_clean(self):
        payload = {"query": {"fields": []}, "options": {"returnFormat": "OBJECTS"}}
        result, changed = normalize_vds_payload(payload)
        assert changed is False

    def test_does_not_overwrite_existing_option(self):
        payload = {
            "query": {"returnFormat": "ARRAYS"},
            "options": {"returnFormat": "OBJECTS"},
        }
        result, changed = normalize_vds_payload(payload)
        # Existing option preserved
        assert result["options"]["returnFormat"] == "OBJECTS"

    def test_no_query_key(self):
        payload = {"options": {}}
        result, changed = normalize_vds_payload(payload)
        assert changed is False


# ---------------------------------------------------------------------------
# Helper to build a provider instance with mocked settings
# ---------------------------------------------------------------------------


def _make_provider(**config_overrides):
    """Build a ProfessionalTravelApiProvider with mocked dependencies."""
    config = {"year": 2024, "module_type_id": 2, **config_overrides}
    user = MagicMock()
    user.id = 1

    with patch(
        "app.services.data_ingestion.api_providers.professional_travel_api_provider.get_settings"
    ) as mock_settings:
        s = mock_settings.return_value
        s.TABLEAU_SERVER_URL = "https://tableau.test"
        s.TABLEAU_SITE_CONTENT_URL = "site"
        s.TABLEAU_DS_FLIGHTS_LUID = "ds-luid"
        s.TABLEAU_CONNECTED_APP_CLIENT_ID = "client-id"
        s.TABLEAU_CONNECTED_APP_SECRET_ID = "secret-id"
        s.TABLEAU_CONNECTED_APP_SECRET_VALUE = "secretvalue1234567890123456789012"
        s.TABLEAU_REQUEST_TIMEOUT_SECONDS = "30"
        s.TABLEAU_VERIFY_SSL = "false"
        s.TABLEAU_REST_MIN_API_VERSION = "3.21"
        s.TABLEAU_MAX_FIELDS = 50
        s.TABLEAU_USERNAME = "testuser"

        provider = ProfessionalTravelApiProvider(
            config,
            user,
            job_session=None,
            data_session=AsyncMock(),
        )
    return provider


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_valid_date(self):
        p = _make_provider()
        result = p._parse_date("20240315")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_empty_string(self):
        p = _make_provider()
        assert p._parse_date("") is None

    def test_wrong_length(self):
        p = _make_provider()
        assert p._parse_date("2024-03-15") is None

    def test_none_like(self):
        p = _make_provider()
        assert p._parse_date(None) is None


# ---------------------------------------------------------------------------
# _normalize_class
# ---------------------------------------------------------------------------


class TestNormalizeClass:
    def test_economy(self):
        p = _make_provider()
        assert p._normalize_class("AIR ECONOMY CLASS") == "eco"

    def test_business(self):
        p = _make_provider()
        assert p._normalize_class("AIR BUSINESS CLASS") == "business"

    def test_first(self):
        p = _make_provider()
        assert p._normalize_class("AIR FIRST CLASS") == "first"

    def test_unknown_defaults_to_eco(self):
        p = _make_provider()
        assert p._normalize_class("SOMETHING ELSE") == "eco"
        assert p._normalize_class("") == "eco"


# ---------------------------------------------------------------------------
# _extract_field_captions
# ---------------------------------------------------------------------------


class TestExtractFieldCaptions:
    def test_from_data_key(self):
        p = _make_provider()
        metadata = {"data": [{"fieldCaption": "A"}, {"fieldCaption": "B"}]}
        assert p._extract_field_captions(metadata) == ["A", "B"]

    def test_from_fields_key(self):
        p = _make_provider()
        metadata = {"fields": [{"fieldCaption": "X"}]}
        assert p._extract_field_captions(metadata) == ["X"]

    def test_from_result_data(self):
        p = _make_provider()
        metadata = {"result": {"data": [{"fieldCaption": "Z"}]}}
        assert p._extract_field_captions(metadata) == ["Z"]

    def test_deduplication(self):
        p = _make_provider()
        metadata = {"data": [{"fieldCaption": "A"}, {"fieldCaption": "A"}]}
        assert p._extract_field_captions(metadata) == ["A"]

    def test_skips_non_dict_entries(self):
        p = _make_provider()
        metadata = {"data": ["not_a_dict", {"fieldCaption": "OK"}]}
        assert p._extract_field_captions(metadata) == ["OK"]

    def test_empty_metadata(self):
        p = _make_provider()
        assert p._extract_field_captions({}) == []


# ---------------------------------------------------------------------------
# _build_payload
# ---------------------------------------------------------------------------


class TestBuildPayload:
    def test_valid_payload(self):
        p = _make_provider()
        result = p._build_payload(["Field1", "Field2"])
        assert result["datasource"]["datasourceLuid"] == "ds-luid"
        assert len(result["query"]["fields"]) == 2
        assert result["options"]["returnFormat"] == "OBJECTS"

    def test_raises_without_datasource_luid(self):
        p = _make_provider()
        p.datasource_luid = None
        with pytest.raises(ValueError, match="datasource_luid"):
            p._build_payload(["A"])

    def test_raises_with_empty_captions(self):
        p = _make_provider()
        with pytest.raises(ValueError, match="field_captions"):
            p._build_payload([])


# ---------------------------------------------------------------------------
# _record_row_error
# ---------------------------------------------------------------------------


class TestRecordRowError:
    def test_records_error_within_limit(self):
        stats = {
            "rows_processed": 0,
            "rows_with_factors": 0,
            "rows_without_factors": 0,
            "rows_skipped": 0,
            "row_errors": [],
            "row_errors_count": 0,
        }
        ProfessionalTravelApiProvider._record_row_error(stats, 5, "bad row", 10)
        assert stats["rows_skipped"] == 1
        assert stats["row_errors_count"] == 1
        assert stats["row_errors"] == [{"row": 5, "reason": "bad row"}]

    def test_respects_max_row_errors(self):
        stats = {
            "rows_processed": 0,
            "rows_with_factors": 0,
            "rows_without_factors": 0,
            "rows_skipped": 0,
            "row_errors": [{"row": i, "reason": "x"} for i in range(10)],
            "row_errors_count": 10,
        }
        ProfessionalTravelApiProvider._record_row_error(stats, 99, "overflow", 10)
        # Count increments but list doesn't grow beyond max
        assert stats["row_errors_count"] == 11
        assert len(stats["row_errors"]) == 10


# ---------------------------------------------------------------------------
# transform_data
# ---------------------------------------------------------------------------


class TestTransformData:
    @pytest.fixture
    def provider(self):
        return _make_provider(year=2024)

    def _make_record(self, **overrides):
        record = {
            "IN_Departure date": "20240601",
            "SCIPER": "123456",
            "IN_Segment origin airport code": "GVA",
            "IN_Segment destination airport code": "CDG",
            "Number of trips": "2",
            "ROUND_TRIP": "YES",
            "Centre financier": "F0828",
            "IN_Segment class": "AIR ECONOMY CLASS",
            "OUT_CO2_CORRECTED": 150.5,
            "OUT_DISTANCE_CORRECTED": 420.0,
            "IN_Supplier": "Swiss",
            "IN_Ticket number": "TK001",
            "TRANSPORT_TYPE": "AIR",
            "PASSENGER_TYPE": "ADULT",
        }
        record.update(overrides)
        return record

    async def test_basic_transform(self, provider):
        records = [self._make_record()]
        result = await provider.transform_data(records)
        assert len(result) == 1
        entry = result[0]
        assert entry["user_institutional_id"] == "123456"
        assert entry["origin_iata"] == "GVA"
        assert entry["destination_iata"] == "CDG"
        assert entry["cabin_class"] == "eco"
        assert entry["number_of_trips"] == 2
        assert entry["round_trip"] is True
        assert entry["kg_co2eq"] == 150.5
        assert entry["distance_km"] == 420.0
        # Unit prefix stripped: F0828 -> 0828
        assert entry["unit_institutional_id"] == "0828"

    async def test_filters_wrong_year(self, provider):
        records = [self._make_record(**{"IN_Departure date": "20230601"})]
        result = await provider.transform_data(records)
        assert len(result) == 0

    async def test_filters_missing_sciper(self, provider):
        records = [self._make_record(SCIPER="")]
        result = await provider.transform_data(records)
        assert len(result) == 0

    async def test_filters_missing_iata(self, provider):
        records = [
            self._make_record(**{"IN_Segment origin airport code": ""}),
        ]
        result = await provider.transform_data(records)
        assert len(result) == 0

    async def test_invalid_date_filtered(self, provider):
        records = [self._make_record(**{"IN_Departure date": "bad"})]
        result = await provider.transform_data(records)
        assert len(result) == 0

    async def test_number_of_trips_defaults_to_1(self, provider):
        records = [self._make_record(**{"Number of trips": None})]
        result = await provider.transform_data(records)
        assert result[0]["number_of_trips"] == 1

    async def test_number_of_trips_invalid_defaults_to_1(self, provider):
        records = [self._make_record(**{"Number of trips": "abc"})]
        result = await provider.transform_data(records)
        assert result[0]["number_of_trips"] == 1

    async def test_unit_prefix_not_stripped_for_numeric(self, provider):
        records = [self._make_record(**{"Centre financier": "1234"})]
        result = await provider.transform_data(records)
        assert result[0]["unit_institutional_id"] == "1234"
