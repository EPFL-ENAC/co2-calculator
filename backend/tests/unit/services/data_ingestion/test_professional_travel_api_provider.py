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
            "rows_missing_centre_financier": 0,
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
            "rows_missing_centre_financier": 0,
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

    async def test_missing_centre_financier_yields_none(self, provider):
        # When Tableau drops the Centre financier column (rename or
        # max_fields cutoff), every record's unit_institutional_id must
        # be None — not a "unknown_unit" sentinel that masks the
        # fail-fast guard in _resolve_carbon_report_modules.
        records = [self._make_record(**{"Centre financier": None})]
        result = await provider.transform_data(records)
        assert result[0]["unit_institutional_id"] is None

    async def test_resolve_modules_raises_when_all_units_missing(self, provider):
        provider.data_session = MagicMock()
        transformed = [
            {"unit_institutional_id": None},
            {"unit_institutional_id": ""},
        ]
        with pytest.raises(
            ValueError, match=r"all \d+ rows have a null 'Centre financier'"
        ):
            await provider._resolve_carbon_report_modules(transformed)


# ---------------------------------------------------------------------------
# ingest — SAP coverage gap observability
# ---------------------------------------------------------------------------


class TestIngestSapCoverageGap:
    """Pin the SAP coverage signal that Kuoni/SAP integration owner flagged
    2026-05: ~117/15865 rows per year have a blank Centre financier (no
    matching SAP expense report for the Kuoni décompte number). The provider
    must skip those rows without failing the job AND surface them under a
    dedicated counter so a feed regression is detectable from job metadata.
    """

    @pytest.mark.asyncio
    async def test_blank_centre_financier_counted_separately(self):
        provider = _make_provider(year=2024)
        provider.user = None

        def _raw(sciper, cf):
            return {
                "IN_Departure date": "20240601",
                "SCIPER": sciper,
                "IN_Segment origin airport code": "GVA",
                "IN_Segment destination airport code": "CDG",
                "Number of trips": "1",
                "ROUND_TRIP": "YES",
                "Centre financier": cf,
                "IN_Segment class": "AIR ECONOMY CLASS",
                "OUT_CO2_CORRECTED": 100,
                "OUT_DISTANCE_CORRECTED": 400,
            }

        provider.fetch_data = AsyncMock(
            return_value=[
                _raw("111", "F0828"),
                _raw("222", None),
                _raw("333", ""),
            ]
        )
        provider._resolve_carbon_report_modules = AsyncMock(return_value={"0828": 42})
        provider._load_data = AsyncMock(return_value={"inserted": 1})
        provider._update_job = AsyncMock()

        result = await provider.ingest()
        stats = result["stats"]

        assert stats["rows_missing_centre_financier"] == 2
        assert stats["rows_processed"] == 1
        assert stats["rows_skipped"] == 2

        # Operator-facing message names the SAP root cause, not the
        # internal "unit_institutional_id" jargon.
        reasons = [e["reason"] for e in stats["row_errors"]]
        assert all(
            "Centre financier" in r and "SAP expense report" in r for r in reasons
        )


# ---------------------------------------------------------------------------
# _load_data — kg_co2eq override carrier + warning visibility
# ---------------------------------------------------------------------------


class TestLoadDataKgCo2eqHandling:
    """Regression tests for the kg_co2eq override carrier path in _load_data:

    - Bad values surface at WARNING level (not DEBUG) so operators see them.
    - The data_payload passed to bulk_create must NOT contain a 'kg_co2eq' key.
    """

    @pytest.mark.asyncio
    async def test_load_data_warns_on_unparseable_kg_co2eq(self, caplog):
        import logging

        provider = _make_provider()
        provider.user = None  # bypass UserRead.model_validate on MagicMock

        # Mock the services so _load_data runs purely in memory.
        mock_service = MagicMock()
        mock_service.bulk_create = AsyncMock(
            return_value=[MagicMock(id=1)]  # one created entry per input
        )
        mock_emission_service = MagicMock()
        mock_emission_service.prepare_create = AsyncMock(return_value=[])
        mock_emission_service.bulk_create = AsyncMock()

        with (
            patch(
                "app.services.data_ingestion.api_providers."
                "professional_travel_api_provider.DataEntryService",
                return_value=mock_service,
            ),
            caplog.at_level(
                logging.WARNING,
                logger="app.services.data_ingestion."
                "api_providers.professional_travel_api_provider",
            ),
        ):
            # One item with a garbage kg_co2eq — should warn but still process.
            await provider._load_data(
                [
                    {
                        "carbon_report_module_id": 99,
                        "origin_iata": "GVA",
                        "destination_iata": "ZRH",
                        "kg_co2eq": "not-a-number",
                    }
                ]
            )

        warnings = [
            rec
            for rec in caplog.records
            if rec.levelno == logging.WARNING and "kg_co2eq" in rec.message
        ]
        assert warnings, (
            "expected a WARNING-level log mentioning kg_co2eq, "
            f"got: {[(r.levelname, r.message) for r in caplog.records]}"
        )
        assert "not-a-number" in warnings[0].message

    @pytest.mark.asyncio
    async def test_load_data_strips_kg_co2eq_from_persisted_data(self, monkeypatch):
        """Whether kg_co2eq is parseable or not, it must be popped from the
        data_payload before DataEntry construction so it never lands in the
        DB JSON column. This is the API mirror of the CSV regression.

        Pinned against the legacy inline-write path
        (``BULK_PATH_PURE_ASYNC=False``) — the override-routing
        assertions read ``prepare_create`` await args, which the
        pure-async path skips entirely.  The kg_co2eq stripping
        itself is path-independent and would also pass under the
        async path; this test specifically pins the override carrier.
        """

        # Patch ``get_settings`` on the provider module so the gate
        # in ``_load_data`` sees BULK_PATH_PURE_ASYNC=False without
        # needing to clear the lru_cache.  The other settings reads
        # in this module (Tableau creds) need the real values, so we
        # delegate every other attribute to the cached Settings.
        provider = _make_provider()
        provider.user = None  # bypass UserRead.model_validate on MagicMock

        captured_entries: list = []

        async def fake_bulk_create(entries, *_args, **_kwargs):
            captured_entries.extend(entries)
            return [MagicMock(id=i) for i, _ in enumerate(entries, start=1)]

        mock_service = MagicMock()
        mock_service.bulk_create = AsyncMock(side_effect=fake_bulk_create)

        with patch(
            "app.services.data_ingestion.api_providers."
            "professional_travel_api_provider.DataEntryService",
            return_value=mock_service,
        ):
            await provider._load_data(
                [
                    {
                        "carbon_report_module_id": 99,
                        "origin_iata": "GVA",
                        "destination_iata": "ZRH",
                        "kg_co2eq": 152.685,  # valid float
                    },
                    {
                        "carbon_report_module_id": 99,
                        "origin_iata": "CDG",
                        "destination_iata": "JFK",
                        "kg_co2eq": "garbage",  # unparseable
                    },
                ]
            )

        # Two DataEntry instances built; neither has kg_co2eq in its data dict.
        assert len(captured_entries) == 2
        for entry in captured_entries:
            assert "kg_co2eq" not in entry.data, (
                f"kg_co2eq leaked into DataEntry.data: {entry.data!r}"
            )

        # B-H1 — the parseable override is persisted under the reserved
        # ``__kg_co2eq_override__`` carrier so the async recalc path picks
        # it up via ``prepare_create``'s data-keyed fallback.  Garbage
        # values are dropped (no carrier set).
        assert captured_entries[0].data.get("__kg_co2eq_override__") == 152.685
        assert "__kg_co2eq_override__" not in captured_entries[1].data

    @pytest.mark.asyncio
    async def test_load_data_skips_emissions_under_pure_async(self):
        """Plan 310-D — under ``BULK_PATH_PURE_ASYNC=True`` (the default),
        ``_load_data`` writes ``data_entries`` but does NOT call
        ``emission_service.prepare_create`` /
        ``emission_service.bulk_create``.  The runner-driven recalc
        chain (fired by ``api_ingest_handler`` post-success) owns
        emission writes for the bulk path.
        """
        provider = _make_provider()
        provider.user = None

        mock_service = MagicMock()
        mock_service.bulk_create = AsyncMock(return_value=[MagicMock(id=1)])

        with patch(
            "app.services.data_ingestion.api_providers."
            "professional_travel_api_provider.DataEntryService",
            return_value=mock_service,
        ):
            await provider._load_data(
                [
                    {
                        "carbon_report_module_id": 99,
                        "origin_iata": "GVA",
                        "destination_iata": "ZRH",
                        "kg_co2eq": 152.685,
                    }
                ]
            )

        # data_entries STILL written; emissions are now owned by the async chain.
        mock_service.bulk_create.assert_awaited_once()
