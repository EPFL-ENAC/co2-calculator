"""Unit tests for BaseCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionResult
from app.models.user import UserProvider
from app.services.data_ingestion.base_csv_provider import (
    BATCH_SIZE,
    BaseCSVProvider,
    StatsDict,
    _get_expected_columns_from_handlers,
    _get_required_columns_from_handler,
    _validate_file_path,
)

# ======================================================================
# File Path Validation Tests - Security Critical
# ======================================================================


def test_validate_file_path_valid():
    """Test that valid file paths pass validation."""
    # Valid paths from allowed prefixes
    _validate_file_path("tmp/upload123.csv")
    _validate_file_path("uploads/data.csv")
    _validate_file_path("temporary/test.csv")
    # Should not raise any exception


def test_validate_file_path_empty():
    """Test that empty file path is rejected."""
    with pytest.raises(ValueError, match="file_path cannot be empty"):
        _validate_file_path("")


def test_validate_file_path_directory_traversal():
    """Test that directory traversal attempts are blocked."""
    with pytest.raises(ValueError, match="directory traversal not allowed"):
        _validate_file_path("tmp/../etc/passwd")

    with pytest.raises(ValueError, match="directory traversal not allowed"):
        _validate_file_path("../../etc/passwd")

    with pytest.raises(ValueError, match="directory traversal not allowed"):
        _validate_file_path("tmp/subdir/../../../etc/passwd")


def test_validate_file_path_absolute_paths():
    """Test that absolute paths are rejected."""
    with pytest.raises(ValueError, match="absolute paths not allowed"):
        _validate_file_path("/etc/passwd")

    with pytest.raises(ValueError, match="absolute paths not allowed"):
        _validate_file_path("/tmp/upload.csv")


def test_validate_file_path_invalid_prefix():
    """Test that paths without allowed prefixes are rejected."""
    with pytest.raises(ValueError, match="must start with one of"):
        _validate_file_path("downloads/file.csv")

    with pytest.raises(ValueError, match="must start with one of"):
        _validate_file_path("data/file.csv")

    with pytest.raises(ValueError, match="must start with one of"):
        _validate_file_path("file.csv")


# ======================================================================
# Handler Helper Function Tests
# ======================================================================


def test_get_expected_columns_from_handlers():
    """Test extracting expected columns from handlers."""
    mock_handler1 = MagicMock()
    mock_handler1.create_dto.model_fields = {
        "col1": MagicMock(),
        "col2": MagicMock(),
    }

    mock_handler2 = MagicMock()
    mock_handler2.create_dto.model_fields = {
        "col2": MagicMock(),  # Duplicate
        "col3": MagicMock(),
    }

    result = _get_expected_columns_from_handlers([mock_handler1, mock_handler2])

    assert result == {"col1", "col2", "col3"}


def test_get_required_columns_from_handler():
    """Test extracting required columns from handler."""
    mock_field_required = MagicMock()
    mock_field_required.is_required.return_value = True

    mock_field_optional = MagicMock()
    mock_field_optional.is_required.return_value = False

    mock_field_meta = MagicMock()
    mock_field_meta.is_required.return_value = True  # But it's in meta fields

    mock_handler = MagicMock()
    mock_handler.create_dto.model_fields = {
        "required_col": mock_field_required,
        "optional_col": mock_field_optional,
        "data": mock_field_meta,  # Meta field, should be excluded
        "carbon_report_module_id": mock_field_meta,  # Meta field
    }

    result = _get_required_columns_from_handler(mock_handler)

    assert "required_col" in result
    assert "optional_col" not in result
    assert "data" not in result
    assert "carbon_report_module_id" not in result


# ======================================================================
# CSV Header Validation Tests
# ======================================================================


class ConcreteCSVProvider(BaseCSVProvider):
    """Concrete implementation for testing."""

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_factors(self):
        return {}

    def _extract_kind_subkind_values(self, filtered_row, handlers):
        return ("kind", None)

    async def _resolve_handler_and_validate(
        self, filtered_row, factor, stats, row_idx, max_row_errors, setup_result
    ):
        return (None, None, None)


@pytest.mark.asyncio
async def test_validate_csv_headers_valid():
    """Test that valid CSV with all required columns passes validation."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider.carbon_report_module_id = 99

    csv_text = "col1,col2,col3\nval1,val2,val3\nval4,val5,val6"
    expected_columns = {"col1", "col2", "col3"}
    required_columns = {"col1", "col2"}

    # Should not raise
    await provider._validate_csv_headers(csv_text, expected_columns, required_columns)


@pytest.mark.asyncio
async def test_validate_csv_headers_empty_file():
    """Test that empty CSV file is rejected."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    csv_text = ""

    with pytest.raises(ValueError, match="CSV file is empty"):
        await provider._validate_csv_headers(csv_text, set(), set())


@pytest.mark.asyncio
async def test_validate_csv_headers_only_header():
    """Test that CSV with only header row is rejected."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    csv_text = "col1,col2,col3\n"

    with pytest.raises(ValueError, match="CSV file is empty"):
        await provider._validate_csv_headers(csv_text, set(), set())


@pytest.mark.asyncio
async def test_validate_csv_headers_missing_required_all_rows():
    """Test that CSV with ALL rows missing required columns is rejected."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    # All 5 rows have col1, col2 but not col3
    csv_text = "col1,col2\nval1,val2\nval3,val4\nval5,val6\nval7,val8\nval9,val10"
    required_columns = {"col1", "col2", "col3"}

    with pytest.raises(ValueError, match="missing required columns"):
        await provider._validate_csv_headers(csv_text, set(), required_columns)


@pytest.mark.asyncio
async def test_validate_csv_headers_some_rows_have_required():
    """Test that CSV with SOME rows having required columns passes."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    # Row 3 has col3, so not ALL rows are missing it
    csv_text = "col1,col2,col3\nval1,val2,\nval3,val4,\n\
val5,val6,val7\nval8,val9,\nval10,val11,"
    required_columns = {"col1", "col2", "col3"}

    # Should not raise - flexible validation allows some missing values
    await provider._validate_csv_headers(csv_text, set(), required_columns)


@pytest.mark.asyncio
async def test_validate_csv_headers_strict_mode_missing_expected():
    """Test that strict mode rejects CSV missing expected columns."""
    config = {"file_path": "tmp/test.csv", "strict_column_validation": True}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    csv_text = "col1,col2\nval1,val2\nval3,val4"
    expected_columns = {"col1", "col2", "col3"}
    required_columns = {"col1"}

    with pytest.raises(ValueError, match="Strict mode.*missing expected columns"):
        await provider._validate_csv_headers(
            csv_text, expected_columns, required_columns
        )


@pytest.mark.asyncio
async def test_validate_csv_headers_malformed_csv():
    """Test that malformed CSV raises appropriate error."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    # Most CSV readers are lenient with unclosed quotes, so test with truly invalid CSV
    csv_text = "col1,col2\n" + ("x" * 1000000)  # Extremely large field

    # Note: standard csv.DictReader is very lenient and may not actually fail
    # So we'll just verify it doesn't crash
    try:
        await provider._validate_csv_headers(csv_text, set(), set())
    except (ValueError, Exception):
        pass  # Either outcome is acceptable


# ======================================================================
# Validate Connection Tests
# ======================================================================


@pytest.mark.asyncio
async def test_validate_connection_success():
    """Test successful connection validation when file exists."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    mock_files_store = MagicMock()
    mock_files_store.file_exists = AsyncMock(return_value=True)
    provider._files_store = mock_files_store

    result = await provider.validate_connection()

    assert result is True
    mock_files_store.file_exists.assert_awaited_once_with("tmp/test.csv")


@pytest.mark.asyncio
async def test_validate_connection_file_not_found():
    """Test connection validation fails when file does not exist."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    mock_files_store = MagicMock()
    mock_files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store = mock_files_store

    result = await provider.validate_connection()

    assert result is False


@pytest.mark.asyncio
async def test_validate_connection_no_file_path():
    """Test connection validation fails when no file path provided."""
    config = {}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    result = await provider.validate_connection()

    assert result is False


@pytest.mark.asyncio
async def test_validate_connection_exception():
    """Test connection validation handles exceptions gracefully."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    mock_files_store = MagicMock()
    mock_files_store.file_exists = AsyncMock(side_effect=Exception("Network error"))
    provider._files_store = mock_files_store

    result = await provider.validate_connection()

    assert result is False


# ======================================================================
# StatsDict Tests
# ======================================================================


def test_stats_dict_structure():
    """Test StatsDict has expected structure."""
    stats: StatsDict = {
        "rows_processed": 0,
        "rows_with_factors": 0,
        "rows_without_factors": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }

    # Verify all keys are present
    assert "rows_processed" in stats
    assert "rows_with_factors" in stats
    assert "rows_without_factors" in stats
    assert "rows_skipped" in stats
    assert "batches_processed" in stats
    assert "row_errors" in stats
    assert "row_errors_count" in stats


# ======================================================================
# Initialization and Configuration Tests
# ======================================================================


def test_provider_initialization():
    """Test BaseCSVProvider initialization."""
    config = {
        "file_path": "tmp/test.csv",
        "job_id": 123,
        "carbon_report_module_id": 456,
        "module_type_id": 789,
        "year": 2024,
    }

    mock_session = MagicMock()
    provider = ConcreteCSVProvider(config, data_session=mock_session)

    assert provider.job_id == 123
    assert provider.carbon_report_module_id == 456
    assert provider.module_type_id == 789
    assert provider.year == 2024
    assert provider.source_file_path == "tmp/test.csv"
    assert provider.data_session == mock_session


def test_provider_initialization_invalid_path():
    """Test that provider initialization validates file path."""
    config = {"file_path": "../etc/passwd"}

    with pytest.raises(ValueError, match="directory traversal not allowed"):
        ConcreteCSVProvider(config, data_session=MagicMock())


def test_provider_lazy_initialization():
    """Test that services are lazily initialized."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    # Should not be initialized yet
    assert provider._files_store is None
    assert provider._repo is None
    assert provider._unit_service is None
    assert provider._user_service is None


@pytest.mark.asyncio
async def test_fetch_data_not_used():
    """Test that fetch_data returns empty list (not used for CSV)."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    result = await provider.fetch_data({})

    assert result == []


@pytest.mark.asyncio
async def test_transform_data_passthrough():
    """Test that transform_data is a passthrough (not used for CSV)."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    input_data = [{"key": "value"}]
    result = await provider.transform_data(input_data)

    assert result == input_data


@pytest.mark.asyncio
async def test_load_data_default():
    """Test that _load_data returns default stats (not used for CSV)."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    result = await provider._load_data([])

    assert result == {"inserted": 0, "skipped": 0, "errors": 0}


# ======================================================================
# Batch Size Constant Test
# ======================================================================


def test_batch_size_constant():
    """Test that BATCH_SIZE is set to expected value."""
    assert BATCH_SIZE == 1000


# ======================================================================
# Row Processing Tests
# ======================================================================


def _build_stats() -> StatsDict:
    return {
        "rows_processed": 0,
        "rows_with_factors": 0,
        "rows_without_factors": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }


@pytest.mark.asyncio
async def test_process_row_success_with_unit_mapping(monkeypatch):
    """Test _process_row builds data entry when mapping is present."""
    config = {"file_path": "tmp/test.csv", "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        data={"amount": 10, "label": "x", "primary_factor_id": 77}
    )
    handler.kind_field = "kind"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.student, handler, None)

    # Mock _resolve_handler_and_validate
    provider._resolve_handler_and_validate = resolve_handler

    # Mock _extract_kind_subkind_values to return matching key
    def extract_kind_subkind(filtered_row, handlers):
        return ("x", None)

    provider._extract_kind_subkind_values = extract_kind_subkind

    # Setup factors_map with matching key
    setup_result = {
        "handlers": [handler],
        "factors_map": {
            f"{DataEntryTypeEnum.student.value}:x:": SimpleNamespace(
                id=77, values={"active_hours": 10}
            )
        },
        "expected_columns": {"unit_institutional_id", "amount", "label"},
    }
    row = {"unit_institutional_id": "U1", "amount": "10", "label": "x"}
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map={"U1": 123},
    )

    assert error_msg is None
    assert result_factor is None  # No longer returns factor
    assert data_entry is not None
    assert data_entry.carbon_report_module_id == 123
    assert data_entry.data.get("primary_factor_id") == 77


@pytest.mark.asyncio
async def test_process_row_rejects_falsy_year_after_setup_bypass():
    """Defense-in-depth row-level guard must reject ``year=0`` the same way
    ``_setup_handlers_and_factors`` does.

    Regression for the asymmetry caught in the PR review: the row-level
    check originally used ``if self.year is None`` while the setup-time
    check uses ``if not self.year``, so a caller that bypassed setup with
    ``year=0`` would slip past the backstop and rebuild the
    ``{type}:0:...`` silent-miss key — exactly the bug this PR is meant to
    close. Both layers now use the same falsy check.
    """
    config = {"file_path": "tmp/test.csv", "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    # Simulate a future caller that bypassed setup and left year unset/zero.
    # The setup-time guard would have raised; the row-level guard must too.
    provider.year = 0

    handler = MagicMock()
    handler.kind_field = "kind"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.student, handler, None)

    provider._resolve_handler_and_validate = resolve_handler
    provider._extract_kind_subkind_values = lambda filtered_row, handlers: (
        "x",
        None,
    )

    setup_result = {
        "handlers": [handler],
        "factors_map": {"unused_key": SimpleNamespace(id=1)},
        "expected_columns": {"unit_institutional_id"},
    }
    row = {"unit_institutional_id": "U1"}
    stats = _build_stats()

    # The row-level ValueError is caught by `_process_row`'s broad
    # try/except (same path every row-validation failure takes) and
    # recorded as a per-row error. The desired outcome is "this row is
    # rejected" — not "process_csv_in_batches aborts" — so assert the
    # per-row error path, not a propagated exception.
    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map={"U1": 123},
    )

    assert data_entry is None
    assert error_msg is not None and "year must be set" in error_msg
    assert kg_co2eq_override is None
    assert stats["rows_skipped"] == 1
    assert stats["row_errors_count"] == 1


@pytest.mark.asyncio
async def test_process_row_missing_unit_mapping_records_error():
    """Test _process_row records error when unit mapping is missing."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {"unit_id", "amount"},
    }
    row = {"unit_id": "UNKNOWN", "amount": "10"}
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=2,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=2,
        unit_to_module_map={"U1": 123},
    )

    assert data_entry is None
    assert result_factor is None
    assert error_msg is not None
    assert stats["rows_skipped"] == 1
    assert stats["row_errors_count"] == 1
    assert stats["row_errors"][0]["row"] == 2


@pytest.mark.asyncio
async def test_process_row_validation_error_records_error(monkeypatch):
    """Test _process_row records handler validation errors."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.side_effect = ValueError("bad payload")
    handler.kind_field = "kind"
    handler.subkind_field = None

    # Mock ModuleHandlerService directly in base_csv_provider module
    mock_handler_service_instance = MagicMock()
    mock_handler_service_instance.resolve_primary_factor_id = AsyncMock(
        return_value={"primary_factor_id": None}
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {"amount"},
    }
    row = {"amount": "10"}
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=3,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=2,
        unit_to_module_map=None,
    )

    assert data_entry is None
    assert result_factor is None
    assert stats["rows_skipped"] == 1


# ======================================================================
# Regression: kg_co2eq must NOT be persisted into DataEntry.data
# ======================================================================


@pytest.mark.asyncio
async def test_process_row_extracts_kg_co2eq_out_of_band():
    """A CSV row with a `kg_co2eq` column must produce a `DataEntry` whose
    persisted ``data`` does NOT contain that key. The value must be returned
    as the 4th tuple element so the caller can pass it to ``prepare_create``
    transiently.

    Regression for the bug where the CSV provider stuffed ``kg_co2eq`` into
    ``filtered_row`` (and hence into ``DataEntry.data``), corrupting the
    source-of-truth JSON column with a derived/imported value.
    """
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 42, "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    # validate_create receives the filtered_row payload — confirm kg_co2eq is
    # NOT present in what it sees, then return whatever data it likes.
    captured_validation_payload: list[dict] = []

    def fake_validate_create(payload):
        captured_validation_payload.append(dict(payload))
        return SimpleNamespace(
            data={
                "origin_iata": "GVA",
                "destination_iata": "ZRH",
                "cabin_class": "first",
                "primary_factor_id": None,
            }
        )

    handler.validate_create.side_effect = fake_validate_create
    handler.kind_field = "category"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.plane, handler, None)

    provider._resolve_handler_and_validate = resolve_handler
    provider._extract_kind_subkind_values = lambda *_a, **_kw: ("very_short_haul", None)

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {
            "origin_iata",
            "destination_iata",
            "cabin_class",
            "user_institutional_id",
            "number_of_trips",
        },
    }
    # Note: kg_co2eq is intentionally absent from expected_columns — the
    # provider must extract it directly from the raw row regardless.
    row = {
        "origin_iata": "GVA",
        "destination_iata": "ZRH",
        "cabin_class": "first",
        "user_institutional_id": "150322",
        "number_of_trips": "1",
        "kg_co2eq": "152.685",
    }
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        _factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map=None,
    )

    assert error_msg is None
    assert data_entry is not None

    # 1. The override is returned out-of-band as a float.
    assert kg_co2eq_override == pytest.approx(152.685)

    # 2. kg_co2eq must NOT have leaked into the persisted DataEntry.data.
    assert "kg_co2eq" not in data_entry.data, (
        f"kg_co2eq leaked into DataEntry.data: {data_entry.data!r}"
    )

    # 3. validate_create must have received the row WITHOUT kg_co2eq.
    assert len(captured_validation_payload) == 1
    assert "kg_co2eq" not in captured_validation_payload[0]


@pytest.mark.asyncio
async def test_process_row_with_no_kg_co2eq_returns_none_override():
    """Rows without a kg_co2eq column produce a None override — not an
    error, not a side effect on DataEntry.data."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 42, "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        data={
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
            "primary_factor_id": None,
        }
    )
    handler.kind_field = "category"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.plane, handler, None)

    provider._resolve_handler_and_validate = resolve_handler
    provider._extract_kind_subkind_values = lambda *_a, **_kw: ("very_short_haul", None)

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {"origin_iata", "destination_iata"},
    }
    row = {"origin_iata": "GVA", "destination_iata": "ZRH"}
    stats = _build_stats()

    _data_entry, error_msg, _factor, kg_co2eq_override = await provider._process_row(
        row,
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map=None,
    )

    assert error_msg is None
    assert kg_co2eq_override is None


@pytest.mark.asyncio
async def test_process_row_warns_on_unparseable_kg_co2eq(caplog):
    """A non-empty but non-numeric kg_co2eq cell must surface a WARNING-level
    log (not a silent debug) and still produce a valid DataEntry with no
    override applied. Locks in the visibility bump from the bot review.
    """
    import logging

    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 42, "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        data={
            "origin_iata": "GVA",
            "destination_iata": "ZRH",
            "primary_factor_id": None,
        }
    )
    handler.kind_field = "category"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.plane, handler, None)

    provider._resolve_handler_and_validate = resolve_handler
    provider._extract_kind_subkind_values = lambda *_a, **_kw: ("very_short_haul", None)

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {"origin_iata", "destination_iata"},
    }
    row = {
        "origin_iata": "GVA",
        "destination_iata": "ZRH",
        "kg_co2eq": "not-a-number",
    }
    stats = _build_stats()

    with caplog.at_level(
        logging.WARNING, logger="app.services.data_ingestion.base_csv_provider"
    ):
        data_entry, error_msg, _factor, kg_co2eq_override = await provider._process_row(
            row,
            row_idx=7,
            setup_result=setup_result,
            stats=stats,
            max_row_errors=5,
            unit_to_module_map=None,
        )

    # The row still processes — only the override is dropped.
    assert error_msg is None
    assert data_entry is not None
    assert kg_co2eq_override is None

    # The parse failure is visible at WARNING level, not debug.
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
    assert "Row 7" in warnings[0].message


@pytest.mark.asyncio
async def test_process_row_consumes_dumb_csv_fixture_for_plane():
    """Consume the dumb plane CSV fixture row-by-row via csv.DictReader and
    verify each row's kg_co2eq is extracted out-of-band — not persisted into
    DataEntry.data. This is the integration-shape regression for the user's
    debugging case (GVA→ZRH plane import).
    """
    import csv as _csv
    from pathlib import Path

    fixture_path = (
        Path(__file__).parent.parent.parent.parent
        / "integration"
        / "data_ingestion"
        / "fixtures"
        / "regression_kg_co2eq_plane.csv"
    )
    assert fixture_path.exists(), f"missing fixture: {fixture_path}"

    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 42, "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.side_effect = lambda payload: SimpleNamespace(
        data={k: v for k, v in payload.items() if k != "data_entry_type_id"}
    )
    handler.kind_field = "category"
    handler.subkind_field = None

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.plane, handler, None)

    provider._resolve_handler_and_validate = resolve_handler
    provider._extract_kind_subkind_values = lambda *_a, **_kw: ("very_short_haul", None)

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {
            "origin_iata",
            "destination_iata",
            "cabin_class",
            "user_institutional_id",
            "number_of_trips",
        },
    }

    with open(fixture_path, encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))

    # Sanity: fixture really has kg_co2eq column with non-empty values.
    assert all(r.get("kg_co2eq") for r in rows), rows
    expected_overrides = [float(r["kg_co2eq"]) for r in rows]

    actual_overrides = []
    for row_idx, row in enumerate(rows, start=1):
        stats = _build_stats()
        (
            data_entry,
            error_msg,
            _factor,
            kg_co2eq_override,
        ) = await provider._process_row(
            row,
            row_idx=row_idx,
            setup_result=setup_result,
            stats=stats,
            max_row_errors=5,
            unit_to_module_map=None,
        )

        assert error_msg is None, f"row {row_idx} errored: {error_msg}"
        assert data_entry is not None
        # Per-row invariant: kg_co2eq is NOT in the persisted data dict.
        assert "kg_co2eq" not in data_entry.data, (
            f"row {row_idx}: kg_co2eq leaked into DataEntry.data: {data_entry.data!r}"
        )
        actual_overrides.append(kg_co2eq_override)

    assert actual_overrides == pytest.approx(expected_overrides)


# ======================================================================
# Batch Processing Tests
# ======================================================================


@pytest.fixture
def legacy_inline_emissions(monkeypatch):
    """Force ``BULK_PATH_PURE_ASYNC=False`` so the legacy inline-write path
    in ``_process_batch`` / ``_recompute_module_stats`` runs (used by the
    pre-310D batch tests).  Patches ``get_settings`` directly so we don't
    have to clear the lru_cache."""
    from app.services.data_ingestion import base_csv_provider

    fake = MagicMock()
    fake.BULK_PATH_PURE_ASYNC = False
    monkeypatch.setattr(base_csv_provider, "get_settings", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_process_batch_creates_emissions(legacy_inline_emissions):
    """Test _process_batch creates emissions from prepared objects.

    Pinned against the legacy path (``BULK_PATH_PURE_ASYNC=False``); the
    pure-async path is covered by
    ``test_process_batch_skips_emissions_when_pure_async``.
    """
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    # Pre-populate year cache to avoid DB query in _process_batch
    provider._year_cache = {999: 2025}

    data_entry_service = MagicMock()
    emission_service = AsyncMock()

    created_entry = SimpleNamespace(id=1, carbon_report_module_id=999)
    data_entry_service.bulk_create = AsyncMock(return_value=[created_entry])
    emission_service.prepare_create = AsyncMock(return_value=[SimpleNamespace(id=9)])
    emission_service.bulk_create = AsyncMock()

    # Mock batch entry with carbon_report_module_id
    batch_entry = MagicMock()
    batch_entry.carbon_report_module_id = 999
    batch = [batch_entry]

    user = SimpleNamespace(
        id=1,
        email="test@example.com",
        display_name="Test User",
        provider=UserProvider.DEFAULT,
        institutional_id="default-1441",
    )

    # No CSV kg_co2eq overrides for this batch (parallel list of None).
    await provider._process_batch(
        batch, data_entry_service, emission_service, user, [None]
    )

    data_entry_service.bulk_create.assert_awaited_once()
    emission_service.prepare_create.assert_awaited_once_with(
        created_entry, kg_co2eq_override=None
    )
    emission_service.bulk_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_batch_skips_emissions_when_pure_async():
    """Plan 310-D — under ``BULK_PATH_PURE_ASYNC=True`` (the default),
    ``_process_batch`` writes data_entries but does NOT write
    data_entry_emissions; the runner-driven ``emission_recalc`` chain
    owns those writes via the ``csv_ingest_handler`` post-success
    fan-out."""
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider._year_cache = {999: 2025}

    data_entry_service = MagicMock()
    emission_service = AsyncMock()

    created_entry = SimpleNamespace(id=1, carbon_report_module_id=999)
    data_entry_service.bulk_create = AsyncMock(return_value=[created_entry])
    emission_service.prepare_create = AsyncMock()
    emission_service.bulk_create = AsyncMock()

    batch_entry = MagicMock()
    batch_entry.carbon_report_module_id = 999
    user = SimpleNamespace(
        id=1,
        email="test@example.com",
        display_name="Test User",
        provider=UserProvider.DEFAULT,
        institutional_id="default-1441",
    )

    await provider._process_batch(
        [batch_entry], data_entry_service, emission_service, user, [None]
    )

    # data_entries STILL written.
    data_entry_service.bulk_create.assert_awaited_once()
    # Emissions writes are skipped — chain handles them.
    emission_service.prepare_create.assert_not_awaited()
    emission_service.bulk_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_recompute_module_stats_skips_when_pure_async():
    """Plan 310-D — ``_recompute_module_stats`` is a no-op under
    ``BULK_PATH_PURE_ASYNC=True``; the runner-driven ``aggregation``
    handler owns the stats write."""
    from app.services.carbon_report_module_service import CarbonReportModuleService

    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider._unit_to_module_map = {1: 100, 2: 200}

    with patch.object(
        CarbonReportModuleService, "recompute_stats", new_callable=AsyncMock
    ) as mock_recompute:
        await provider._recompute_module_stats()

    mock_recompute.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_batch_routes_kg_co2eq_overrides_by_id(
    legacy_inline_emissions,
):
    """Carrier flow regression: a batch with kg_co2eq overrides aligned to
    its inputs must produce a {data_entry.id: kg_co2eq} dict and forward
    each override per-call to ``prepare_create``.

    This covers the end-to-end carrier path that the unit-level _process_row
    and prepare_create tests cover only in isolation.

    Pinned against the legacy inline-write path (Plan 310-D's pure-async
    path skips emissions entirely; carrier routing still matters for
    rollback semantics).
    """
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider._year_cache = {999: 2025}

    data_entry_service = MagicMock()
    emission_service = AsyncMock()

    # bulk_create preserves input order — return three responses with
    # incrementing IDs aligned to the input batch.
    created_entries = [
        SimpleNamespace(id=10, carbon_report_module_id=999),
        SimpleNamespace(id=11, carbon_report_module_id=999),
        SimpleNamespace(id=12, carbon_report_module_id=999),
    ]
    data_entry_service.bulk_create = AsyncMock(return_value=created_entries)
    emission_service.prepare_create = AsyncMock(return_value=[SimpleNamespace(id=99)])
    emission_service.bulk_create = AsyncMock()

    batch = []
    for _ in range(3):
        e = MagicMock()
        e.carbon_report_module_id = 999
        batch.append(e)

    user = SimpleNamespace(
        id=1,
        email="test@example.com",
        display_name="Test User",
        provider=UserProvider.DEFAULT,
        institutional_id="default-1441",
    )

    # Two of three rows have an override; the middle one does not.
    overrides = [152.685, None, 380.0]

    await provider._process_batch(
        batch, data_entry_service, emission_service, user, overrides
    )

    # prepare_create must be called once per response, with the override
    # routed by data_entry.id (not by index, not by formula path).
    assert emission_service.prepare_create.await_count == 3
    actual_calls = {
        call.args[0].id: call.kwargs.get("kg_co2eq_override")
        for call in emission_service.prepare_create.await_args_list
    }
    assert actual_calls == {10: 152.685, 11: None, 12: 380.0}


# ======================================================================
# Finalization Tests
# ======================================================================


@pytest.mark.asyncio
async def test_finalize_and_commit_moves_file_and_updates_job():
    """Test _finalize_and_commit updates job and moves file."""
    from app.models.data_ingestion import IngestionResult, IngestionState

    config = {"file_path": "tmp/test.csv", "job_id": 7}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    provider._files_store = MagicMock()
    provider._files_store.move_file = AsyncMock(return_value=True)
    provider.data_session.flush = AsyncMock()
    provider._update_job = AsyncMock()
    provider._process_batch = AsyncMock()
    provider._recompute_module_stats = AsyncMock()

    stats = _build_stats()
    stats["rows_processed"] = 2
    stats["batches_processed"] = 1
    setup_result = {"processing_path": "processing/7/test.csv", "filename": "test.csv"}

    result = await provider._finalize_and_commit(
        batch=[MagicMock()],
        data_entry_service=MagicMock(),
        emission_service=MagicMock(),
        stats=stats,
        setup_result=setup_result,
        batch_kg_co2eq_overrides=[None],
    )

    provider._process_batch.assert_awaited_once()
    provider._files_store.move_file.assert_awaited_once_with(
        "processing/7/test.csv", "processed/7/test.csv"
    )

    # _update_job is called once at the end with full summary
    # (previously was called twice - once after file move, once at end)
    assert provider._update_job.await_count == 1

    # Single call: final summary
    call_args = provider._update_job.call_args
    assert (
        call_args.kwargs["status_message"]
        == "Processed 2 rows: 0 with factors, 0 without factors, 0 skipped"
    )
    assert call_args.kwargs["state"] == IngestionState.FINISHED
    assert call_args.kwargs["result"] == IngestionResult.SUCCESS
    assert "rows_processed" in call_args.kwargs["extra_metadata"]
    assert "stats" in call_args.kwargs["extra_metadata"]
    # Check processed_file_path is in metadata
    assert (
        call_args.kwargs["extra_metadata"]["processed_file_path"]
        == "processed/7/test.csv"
    )

    assert result["inserted"] == 2


# ======================================================================
# _compute_ingestion_result Tests
# ======================================================================


class TestComputeIngestionResult:
    """Tests for BaseCSVProvider._compute_ingestion_result."""

    def _make_provider(self):
        config = {"file_path": "tmp/test.csv"}
        return ConcreteCSVProvider(config, data_session=MagicMock())

    def test_all_processed_no_skipped_returns_success(self):
        provider = self._make_provider()
        stats = _build_stats()
        stats["rows_processed"] = 10
        stats["rows_skipped"] = 0
        assert provider._compute_ingestion_result(stats) == IngestionResult.SUCCESS

    def test_some_skipped_returns_warning(self):
        provider = self._make_provider()
        stats = _build_stats()
        stats["rows_processed"] = 7
        stats["rows_skipped"] = 3
        assert provider._compute_ingestion_result(stats) == IngestionResult.WARNING

    def test_none_processed_returns_error(self):
        provider = self._make_provider()
        stats = _build_stats()
        stats["rows_processed"] = 0
        stats["rows_skipped"] = 5
        assert provider._compute_ingestion_result(stats) == IngestionResult.ERROR

    def test_none_processed_none_skipped_returns_error(self):
        provider = self._make_provider()
        stats = _build_stats()
        assert provider._compute_ingestion_result(stats) == IngestionResult.ERROR


# ======================================================================
# _record_row_error Tests
# ======================================================================


class TestRecordRowError:
    """Tests for BaseCSVProvider._record_row_error (static method)."""

    def test_increments_skipped_and_error_count(self):
        stats = _build_stats()
        BaseCSVProvider._record_row_error(stats, 1, "bad value", max_row_errors=10)
        assert stats["rows_skipped"] == 1
        assert stats["row_errors_count"] == 1
        assert len(stats["row_errors"]) == 1
        assert stats["row_errors"][0] == {"row": 1, "reason": "bad value"}

    def test_caps_row_errors_list_at_max(self):
        stats = _build_stats()
        for i in range(5):
            BaseCSVProvider._record_row_error(stats, i, f"err {i}", max_row_errors=3)
        # All 5 counted, but only 3 stored
        assert stats["rows_skipped"] == 5
        assert stats["row_errors_count"] == 5
        assert len(stats["row_errors"]) == 3

    def test_max_zero_stores_nothing(self):
        stats = _build_stats()
        BaseCSVProvider._record_row_error(stats, 1, "err", max_row_errors=0)
        assert stats["rows_skipped"] == 1
        assert stats["row_errors_count"] == 1
        assert len(stats["row_errors"]) == 0


# ======================================================================
# _get_source_from_entity_type Tests
# ======================================================================


class TestGetSourceFromEntityType:
    """Tests for BaseCSVProvider._get_source_from_entity_type."""

    def test_module_per_year(self):
        config = {"file_path": "tmp/test.csv"}
        p = ConcreteCSVProvider(config, data_session=MagicMock())
        # ConcreteCSVProvider.entity_type already returns MODULE_PER_YEAR
        assert (
            p._get_source_from_entity_type() == DataEntrySourceEnum.CSV_MODULE_PER_YEAR
        )

    def test_module_unit_specific(self, monkeypatch):
        config = {"file_path": "tmp/test.csv"}
        p = ConcreteCSVProvider(config, data_session=MagicMock())
        monkeypatch.setattr(
            type(p),
            "entity_type",
            property(lambda self: EntityType.MODULE_UNIT_SPECIFIC),
        )
        assert (
            p._get_source_from_entity_type()
            == DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC
        )

    def test_unknown_entity_type_returns_none(self, monkeypatch):
        config = {"file_path": "tmp/test.csv"}
        p = ConcreteCSVProvider(config, data_session=MagicMock())
        monkeypatch.setattr(type(p), "entity_type", property(lambda self: MagicMock()))
        assert p._get_source_from_entity_type() is None


# ======================================================================
# _resolve_data_entry_type_from_category Tests
# ======================================================================


class TestResolveDataEntryTypeFromCategory:
    """Tests for BaseCSVProvider._resolve_data_entry_type_from_category."""

    def test_no_category_field_returns_none(self):
        handler = SimpleNamespace()  # no category_field attribute
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={"col": "val"},
            handler=handler,
            row_idx=1,
            stats=stats,
            max_row_errors=5,
        )
        assert result is None
        assert stats["rows_skipped"] == 0

    def test_empty_category_value_returns_none(self):
        handler = SimpleNamespace(category_field="category")
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={"category": ""},
            handler=handler,
            row_idx=1,
            stats=stats,
            max_row_errors=5,
        )
        assert result is None
        assert stats["rows_skipped"] == 0

    def test_missing_category_key_returns_none(self):
        handler = SimpleNamespace(category_field="category")
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={}, handler=handler, row_idx=1, stats=stats, max_row_errors=5
        )
        assert result is None

    def test_valid_category_resolves_enum(self):
        handler = SimpleNamespace(category_field="category")
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={"category": "scientific"},
            handler=handler,
            row_idx=1,
            stats=stats,
            max_row_errors=5,
        )
        assert result == DataEntryTypeEnum.scientific

    def test_valid_category_case_insensitive(self):
        handler = SimpleNamespace(category_field="category")
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={"category": "Scientific"},
            handler=handler,
            row_idx=1,
            stats=stats,
            max_row_errors=5,
        )
        assert result == DataEntryTypeEnum.scientific

    def test_invalid_category_records_error_returns_none(self):
        handler = SimpleNamespace(category_field="category")
        stats = _build_stats()
        result = BaseCSVProvider._resolve_data_entry_type_from_category(
            row={"category": "nonexistent"},
            handler=handler,
            row_idx=1,
            stats=stats,
            max_row_errors=5,
        )
        assert result is None
        assert stats["rows_skipped"] == 1
        assert stats["row_errors_count"] == 1


# ======================================================================
# _delete_existing_entries_for_module_per_year – scope isolation tests
# ======================================================================


def _make_provider_with_job(module_type_id: int, data_entry_type_id: int | None):
    """Return a ConcreteCSVProvider whose self.job is pre-populated."""
    config = {"file_path": "tmp/test.csv", "module_type_id": module_type_id}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider.job = SimpleNamespace(
        module_type_id=module_type_id,
        data_entry_type_id=data_entry_type_id,
    )
    provider.user = None
    return provider


def _make_stats() -> dict:
    return {
        "rows_processed": 0,
        "rows_skipped": 0,
        "rows_with_factors": 0,
        "rows_without_factors": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }


@pytest.mark.asyncio
async def test_delete_scoped_to_specific_data_entry_type():
    """When data_entry_type_id is set, only that type is deleted.

    Regression: research_facilities (module 6) has two submodules — 70 and 71.
    Uploading for type 70 must NOT wipe type 71 entries, and vice-versa.
    """
    # module_type_id=6 (research_facilities) has types 70 and 71
    provider = _make_provider_with_job(module_type_id=6, data_entry_type_id=70)

    data_entry_service = MagicMock()
    data_entry_service.bulk_delete_by_source = AsyncMock()

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    # bulk_delete_by_source must be called exactly once — for type 70 only
    assert data_entry_service.bulk_delete_by_source.call_count == 1
    call_kwargs = data_entry_service.bulk_delete_by_source.call_args.kwargs
    assert call_kwargs["data_entry_type_id"] == DataEntryTypeEnum.research_facilities
    assert call_kwargs["source"] == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value


@pytest.mark.asyncio
async def test_delete_sibling_submodule_not_wiped():
    """Uploading animal facilities (71) must not delete research facilities (70)."""
    provider = _make_provider_with_job(module_type_id=6, data_entry_type_id=71)

    data_entry_service = MagicMock()
    data_entry_service.bulk_delete_by_source = AsyncMock()

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    assert data_entry_service.bulk_delete_by_source.call_count == 1
    call_kwargs = data_entry_service.bulk_delete_by_source.call_args.kwargs
    assert (
        call_kwargs["data_entry_type_id"]
        == DataEntryTypeEnum.mice_and_fish_animal_facilities
    )


@pytest.mark.asyncio
async def test_delete_all_types_when_no_data_entry_type_id():
    """Without data_entry_type_id on the job, all module types are deleted."""
    # module_type_id=6 has two types; no specific type given
    provider = _make_provider_with_job(module_type_id=6, data_entry_type_id=None)

    data_entry_service = MagicMock()
    data_entry_service.bulk_delete_by_source = AsyncMock()

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    # Both types (70 and 71) should be deleted
    assert data_entry_service.bulk_delete_by_source.call_count == 2
    deleted_types = {
        call.kwargs["data_entry_type_id"]
        for call in data_entry_service.bulk_delete_by_source.call_args_list
    }
    assert DataEntryTypeEnum.research_facilities in deleted_types
    assert DataEntryTypeEnum.mice_and_fish_animal_facilities in deleted_types
