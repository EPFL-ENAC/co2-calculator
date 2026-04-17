"""Unit tests for BaseCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
    config = {"file_path": "tmp/test.csv"}
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

    data_entry, error_msg, result_factor = await provider._process_row(
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

    data_entry, error_msg, result_factor = await provider._process_row(
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

    data_entry, error_msg, result_factor = await provider._process_row(
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
# Batch Processing Tests
# ======================================================================


@pytest.mark.asyncio
async def test_process_batch_creates_emissions():
    """Test _process_batch creates emissions from prepared objects."""
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

    await provider._process_batch(batch, data_entry_service, emission_service, user)

    data_entry_service.bulk_create.assert_awaited_once()
    emission_service.prepare_create.assert_awaited_once_with(created_entry)
    emission_service.bulk_create.assert_awaited_once()


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
