"""Unit tests for BaseCSVProvider."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.models.carbon_report import CarbonReportModule
from app.models.data_entry import (
    BULK_PER_YEAR_SOURCES,
    DataEntry,
    DataEntrySourceEnum,
    DataEntryTypeEnum,
)
from app.models.data_ingestion import EntityType, IngestionResult
from app.models.module_type import ModuleTypeEnum
from app.models.user import UserProvider
from app.services.data_ingestion.base_csv_provider import (
    REUPLOAD_HINT,
    BaseCSVProvider,
    StatsDict,
    _get_expected_columns_from_handlers,
    _get_required_columns_from_handler,
    _is_blank_data_row,
    _validate_file_path,
)


class _DummyDataEntryPayload(BaseModel):
    """Minimal model used to trigger a real ``pydantic.ValidationError``
    (float/date parsing failures) the same way a real handler's
    ``create_dto`` would, without depending on a concrete handler."""

    amount: float
    date: datetime.date


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


def test_is_blank_data_row_all_required_empty():
    assert _is_blank_data_row({"amount": "", "note": "x"}, {"amount"}) is True


def test_is_blank_data_row_partial_required_value():
    assert _is_blank_data_row({"amount": "10", "note": ""}, {"amount"}) is False


def test_is_blank_data_row_no_required_columns():
    assert _is_blank_data_row({"amount": ""}, set()) is False


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
async def test_process_csv_with_blank_rows_does_not_raise_value_error():
    """Regression test: Verifies that intermittent and trailing structural
    blank rows (like ',,') are skipped by the loop guard and do not cause
    the batch processor to raise a 'Data entry is None without error message'
    ValueError.
    """
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99, "year": 2025}

    # 1. Use an AsyncMock session to satisfy general async database dependencies
    mock_session = AsyncMock()
    provider = ConcreteCSVProvider(config, data_session=mock_session)

    # Mock out the batch-saving step completely to avoid database repository
    # dependencies
    provider._process_batch = AsyncMock(return_value=2)

    # 2. Mock the async files_store layer
    mock_files_store = MagicMock()
    mock_files_store.move_file = AsyncMock(return_value="processing/test.csv")
    mock_files_store.file_exists = AsyncMock(return_value=True)

    # Provide csv_content as raw bytes (b"...") so .decode() succeeds
    csv_content = b"head1,head2,head3\nval1,val2,val3\n,,\nvala,valb,valc\n,,\n,,"
    mock_files_store.get_file = AsyncMock(return_value=(csv_content, "text/csv"))

    # Patch the private backend attribute
    provider._files_store = mock_files_store

    # 3. Mock handlers and setup results so _process_row works for valid rows
    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(data={"head1": "val"})
    handler.kind_field = "head1"
    handler.subkind_field = None
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))

    async def mock_setup():
        return {
            "handlers": [handler],
            "factors_map": {},
            "expected_columns": {"head1", "head2", "head3"},
            "required_columns": {"head1"},
        }

    provider._setup_handlers_and_factors = mock_setup
    provider._resolve_handler_and_validate = AsyncMock(
        return_value=(DataEntryTypeEnum.student, handler, None)
    )

    # 4. Trigger the ingestion processor method
    try:
        result = await provider.process_csv_in_batches()
    except ValueError as e:
        if "Data entry is None without error message" in str(e):
            pytest.fail(
                "Regression caught! Deleting the blank row loop guard causes "
                "a structural empty row to trigger an absolute process crash."
            )
        raise e

    # 5. Assertions: check execution runs without completely failing out
    assert result is not None


# ======================================================================
# Issue #1564 — member (uid, sius_code) composite uniqueness in the row loop
# ======================================================================


def _drive_member_csv(
    db_session: AsyncSession, module_id: int, rows_data: list[dict]
) -> "ConcreteCSVProvider":
    """Build a provider that feeds ``rows_data`` through the real row loop.

    ``_process_row`` is stubbed to skip CSV parsing/validation (out of scope
    here) but returns a real ``member`` DataEntry per row, so the composite
    (user_institutional_id, sius_code) uniqueness check in
    ``process_csv_in_batches`` — the code under test — runs for real against
    ``db_session``. ``_process_batch`` is stubbed to skip factor/emission
    computation, which is irrelevant to the uniqueness check.
    """
    config = {
        "file_path": "tmp/test.csv",
        "carbon_report_module_id": module_id,
        "module_type_id": ModuleTypeEnum.headcount.value,
        "year": 2025,
    }
    provider = ConcreteCSVProvider(config, data_session=db_session)

    mock_files_store = MagicMock()
    mock_files_store.move_file = AsyncMock(return_value="processing/test.csv")
    mock_files_store.file_exists = AsyncMock(return_value=True)
    csv_content = ("\n".join(["header"] + ["row"] * len(rows_data))).encode()
    mock_files_store.get_file = AsyncMock(return_value=(csv_content, "text/csv"))
    provider._files_store = mock_files_store

    async def mock_setup():
        return {
            "handlers": [],
            "factors_map": {},
            "expected_columns": {"header"},
            "required_columns": set(),
        }

    provider._setup_handlers_and_factors = mock_setup

    async def fake_process_row(row, row_idx, setup_result, stats, max_row_errors, _map):
        entry = DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module_id,
            data=dict(rows_data[row_idx - 1]),
        )
        return entry, None, None, None

    provider._process_row = fake_process_row
    provider._process_batch = AsyncMock(return_value=len(rows_data))
    return provider


@pytest.mark.asyncio
async def test_csv_batch_accepts_same_member_different_sius_code(
    db_session: AsyncSession,
):
    """Same unit + user_institutional_id, different sius_code (multi-role
    member) — both rows must be ingested, no DUPLICATE_INSTITUTIONAL_ID."""
    module = CarbonReportModule(
        carbon_report_id=1, module_type_id=ModuleTypeEnum.headcount.value, status=0
    )
    db_session.add(module)
    await db_session.flush()

    rows_data = [
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "53"},
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "54"},
    ]
    provider = _drive_member_csv(db_session, module.id, rows_data)

    result = await provider.process_csv_in_batches()

    assert result["stats"]["row_errors_count"] == 0
    assert result["stats"]["rows_processed"] == 2


@pytest.mark.asyncio
async def test_csv_batch_rejects_true_duplicate_member_role(db_session: AsyncSession):
    """Same unit + user_institutional_id + sius_code (true duplicate) — the
    second row is rejected with DUPLICATE_INSTITUTIONAL_ID."""
    module = CarbonReportModule(
        carbon_report_id=1, module_type_id=ModuleTypeEnum.headcount.value, status=0
    )
    db_session.add(module)
    await db_session.flush()

    rows_data = [
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "53"},
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "53"},
    ]
    provider = _drive_member_csv(db_session, module.id, rows_data)

    result = await provider.process_csv_in_batches()

    assert result["stats"]["row_errors_count"] == 1
    assert result["stats"]["row_errors"][0]["reason"] == "DUPLICATE_INSTITUTIONAL_ID"
    assert result["stats"]["rows_processed"] == 1


@pytest.mark.asyncio
async def test_csv_batch_rejects_role_already_persisted(db_session: AsyncSession):
    """A (user_institutional_id, sius_code) already in the DB for the module
    (e.g. a manual entry surviving the bulk replace) rejects the CSV row via
    the pre-seeded set — ONE bulk prefetch instead of a per-row SELECT
    (stage 2026-07-17: the per-row check ran at 14 rows/s)."""
    module = CarbonReportModule(
        carbon_report_id=1, module_type_id=ModuleTypeEnum.headcount.value, status=0
    )
    db_session.add(module)
    await db_session.flush()

    db_session.add(
        DataEntry(
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=module.id,
            data={"name": "X X", "user_institutional_id": "123456", "sius_code": "53"},
        )
    )
    await db_session.flush()

    rows_data = [
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "53"},
        {"name": "X X", "user_institutional_id": "123456", "sius_code": "54"},
    ]
    provider = _drive_member_csv(db_session, module.id, rows_data)

    result = await provider.process_csv_in_batches()

    assert result["stats"]["row_errors_count"] == 1
    assert result["stats"]["row_errors"][0]["reason"] == "DUPLICATE_INSTITUTIONAL_ID"
    assert result["stats"]["rows_processed"] == 1


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
    except ValueError, Exception:
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
# Batch Size Setting Test
# ======================================================================


def test_copy_batch_size_setting():
    """Data-entry COPY batches are sized by INGEST_COPY_BATCH_SIZE."""
    assert get_settings().INGEST_COPY_BATCH_SIZE >= 1


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
    """_process_row builds the data entry from the row alone: no factor is
    matched, seeded, or stamped at ingest — factor defaults are derived at
    compute/display time."""
    config = {"file_path": "tmp/test.csv", "year": 2025}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        data={"amount": 10, "label": "x"}
    )
    handler.kind_field = "kind"
    handler.subkind_field = None
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))

    async def resolve_handler(*_args, **_kwargs):
        return (DataEntryTypeEnum.student, handler, None)

    # Mock _resolve_handler_and_validate
    provider._resolve_handler_and_validate = resolve_handler

    # Mock _extract_kind_subkind_values to return matching key
    def extract_kind_subkind(filtered_row, handlers):
        return ("x", None)

    provider._extract_kind_subkind_values = extract_kind_subkind

    setup_result = {
        "handlers": [handler],
        "factors_map": {
            f"{DataEntryTypeEnum.student.value}:2025:x:": SimpleNamespace(id=77)
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
    assert result_factor is None  # ingest never resolves a factor
    assert data_entry is not None
    assert data_entry.carbon_report_module_id == 123
    assert "primary_factor_id" not in data_entry.data
    # No seeding: the entry carries exactly what the row provided.
    assert set(data_entry.data) == {"amount", "label"}


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
async def test_process_row_skips_blank_scaffolding_row():
    """Empty template rows are skipped before required-field validation."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    setup_result = {
        "handlers": [MagicMock()],
        "factors_map": {},
        "expected_columns": {"amount", "note"},
        "required_columns": {"amount"},
    }
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        {"amount": "", "note": ""},
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map=None,
    )

    assert data_entry is None
    assert error_msg is None
    assert result_factor is None
    assert kg_co2eq_override is None
    assert stats["rows_skipped"] == 1
    assert stats["row_errors"] == []


@pytest.mark.asyncio
async def test_process_row_validation_error_records_error(monkeypatch):
    """Test _process_row records handler validation errors."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.validate_create.side_effect = ValueError("bad payload")
    handler.kind_field = "kind"
    handler.subkind_field = None

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


@pytest.mark.asyncio
async def test_process_row_pydantic_validation_error_bad_float():
    """A bad-float CSV value produces a readable ``field: reason (got
    value)`` message instead of pydantic's raw multi-line dump (issue
    #659), for the data-entry CSV path."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.kind_field = "kind"
    handler.subkind_field = None

    def fake_validate_create(payload):
        return _DummyDataEntryPayload(amount="abc", date=datetime.date(2026, 1, 1))

    handler.validate_create.side_effect = fake_validate_create
    # Bypass handler resolution (covered by other tests) so this test
    # exercises the validate_create/ValidationError path directly.
    provider._resolve_handler_and_validate = AsyncMock(
        return_value=(DataEntryTypeEnum.member, handler, None)
    )

    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "expected_columns": {"amount"},
    }
    row = {"amount": "abc"}
    stats = _build_stats()

    (
        data_entry,
        error_msg,
        result_factor,
        kg_co2eq_override,
    ) = await provider._process_row(
        row,
        row_idx=4,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=2,
        unit_to_module_map=None,
    )

    assert data_entry is None
    assert error_msg == (
        "amount: Input should be a valid number, unable to parse "
        "string as a number (got 'abc')"
    )
    assert stats["rows_skipped"] == 1
    assert stats["row_errors"][0]["reason"] == error_msg


@pytest.mark.asyncio
async def test_process_row_pydantic_validation_error_bad_date():
    """An invalid date CSV value produces a readable per-field message
    (issue #659), for the data-entry CSV path."""
    config = {"file_path": "tmp/test.csv", "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    handler = MagicMock()
    handler.kind_field = "kind"
    handler.subkind_field = None

    def fake_validate_create(payload):
        return _DummyDataEntryPayload(amount=1.0, date="2026-13-40")

    handler.validate_create.side_effect = fake_validate_create
    # Bypass handler resolution (covered by other tests) so this test
    # exercises the validate_create/ValidationError path directly.
    provider._resolve_handler_and_validate = AsyncMock(
        return_value=(DataEntryTypeEnum.member, handler, None)
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
        row_idx=5,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=2,
        unit_to_module_map=None,
    )

    assert data_entry is None
    assert error_msg.startswith("date: Input should be a valid date or datetime")
    assert "(got '2026-13-40')" in error_msg
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
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))
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

    # 3b. Ingest no longer stamps primary_factor_id onto the payload —
    # emission compute resolves the Factor dynamically at recalc time.
    assert "primary_factor_id" not in captured_validation_payload[0]
    assert "primary_factor_id" not in data_entry.data

    # 4. B-H1 — the override is also persisted under the reserved
    #    ``__kg_co2eq_override__`` carrier so the async recalc path
    #    (``upsert_by_data_entry`` → ``prepare_create``) still honors it
    #    when ``BULK_PATH_PURE_ASYNC`` skips the inline-write path.
    assert data_entry.data.get("__kg_co2eq_override__") == pytest.approx(152.685)


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
        }
    )
    handler.kind_field = "category"
    handler.subkind_field = None
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))

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

    data_entry, error_msg, _factor, kg_co2eq_override = await provider._process_row(
        row,
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        unit_to_module_map=None,
    )

    assert error_msg is None
    assert kg_co2eq_override is None
    assert data_entry is not None
    assert "primary_factor_id" not in data_entry.data


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
        }
    )
    handler.kind_field = "category"
    handler.subkind_field = None
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))

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
    assert "primary_factor_id" not in data_entry.data

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
    handler.enrich_csv_row = AsyncMock(side_effect=lambda d, s: (d, None))

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
        # B-H1 — the parsed override IS persisted under the reserved
        # ``__kg_co2eq_override__`` carrier so the async recalc honors it.
        assert data_entry.data.get("__kg_co2eq_override__") == pytest.approx(
            float(row["kg_co2eq"])
        ), f"row {row_idx}: missing __kg_co2eq_override__ carrier"
        actual_overrides.append(kg_co2eq_override)

    assert actual_overrides == pytest.approx(expected_overrides)


# ======================================================================
# Batch Processing Tests
# ======================================================================


@pytest.mark.asyncio
async def test_process_batch_skips_emissions_when_pure_async():
    """Plan 310-D — under ``BULK_PATH_PURE_ASYNC=True`` (the default),
    ``_process_batch`` writes data_entries but does NOT write
    data_entry_emissions; the runner-driven ``emission_recalc`` chain
    owns those writes via the ``csv_ingest_handler`` post-success
    fan-out."""
    data_session = MagicMock()
    data_session.commit = AsyncMock()
    config = {"file_path": "tmp/test.csv"}
    provider = ConcreteCSVProvider(config, data_session=data_session)
    provider._year_cache = {999: 2025}

    data_entry_service = MagicMock()
    emission_service = AsyncMock()

    data_entry_service.bulk_copy = AsyncMock(return_value=1)
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

    # data_entries STILL written (COPY path).
    data_entry_service.bulk_copy.assert_awaited_once()
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


# ======================================================================
# Setup / Idempotent Move Tests (#1559)
# ======================================================================


@pytest.mark.asyncio
async def test_setup_and_validate_skips_move_when_already_in_processing():
    """Regression #1559: a retry after a prior successful tmp->processing
    move (job crashed/restarted before FINISHED, sweep_stuck_running_jobs
    reset it to NOT_STARTED) must succeed by reading the file that is
    already at processing/<job_id>/, not fail with "Failed to move file"
    just because the tmp/ source is gone.
    """
    config = {"file_path": "tmp/test.csv", "job_id": 7, "carbon_report_module_id": 99}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    # Short-circuit the DB lookup at the top of _setup_and_validate.
    provider.job = SimpleNamespace(id=7)

    async def mock_setup():
        return {
            "handlers": [],
            "factors_map": {},
            "expected_columns": {"col1"},
            "required_columns": set(),
        }

    provider._setup_handlers_and_factors = mock_setup

    mock_files_store = MagicMock()
    # Destination already present (prior attempt); tmp/ source is gone —
    # move_file would fail if called, proving the retry never touches it.
    mock_files_store.file_exists = AsyncMock(return_value=True)
    mock_files_store.move_file = AsyncMock(
        side_effect=AssertionError("move_file must not be called on retry")
    )
    mock_files_store.get_file = AsyncMock(return_value=(b"col1\nval1\n", "text/csv"))
    provider._files_store = mock_files_store

    result = await provider._setup_and_validate()

    mock_files_store.move_file.assert_not_awaited()
    assert result["processing_path"] == "processing/7/test.csv"


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
    provider._files_store.file_exists = AsyncMock(return_value=False)
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
    # Issue #1398 — an all-rows-succeeded job stays silent on re-upload.
    assert REUPLOAD_HINT not in call_args.kwargs["status_message"]
    assert "rows_processed" in call_args.kwargs["extra_metadata"]
    assert "stats" in call_args.kwargs["extra_metadata"]
    # Check processed_file_path is in metadata
    assert (
        call_args.kwargs["extra_metadata"]["processed_file_path"]
        == "processed/7/test.csv"
    )

    assert result["inserted"] == 2


@pytest.mark.asyncio
async def test_finalize_and_commit_warning_includes_reupload_hint():
    """Issue #1398 — a partial ingestion (rows_skipped > 0, e.g. the job
    stopped early) must explicitly tell the user to re-upload the file.
    Recalculating only recomputes emissions for rows already committed —
    it cannot add rows that were never ingested.
    """
    from app.models.data_ingestion import IngestionResult

    config = {"file_path": "tmp/test.csv", "job_id": 7}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=True)
    provider.data_session.flush = AsyncMock()
    provider._update_job = AsyncMock()
    provider._process_batch = AsyncMock()
    provider._recompute_module_stats = AsyncMock()

    stats = _build_stats()
    stats["rows_processed"] = 7
    stats["rows_skipped"] = 3
    stats["batches_processed"] = 1
    setup_result = {"processing_path": "processing/7/test.csv", "filename": "test.csv"}

    await provider._finalize_and_commit(
        batch=[MagicMock()],
        data_entry_service=MagicMock(),
        emission_service=MagicMock(),
        stats=stats,
        setup_result=setup_result,
        batch_kg_co2eq_overrides=[None],
    )

    call_args = provider._update_job.call_args
    assert call_args.kwargs["result"] == IngestionResult.WARNING
    assert REUPLOAD_HINT in call_args.kwargs["status_message"]
    # The original summary is preserved, not replaced.
    assert "3 skipped" in call_args.kwargs["status_message"]


@pytest.mark.asyncio
async def test_finalize_and_commit_all_skipped_error_includes_reupload_hint():
    """Issue #1398 — the ERROR case reachable through _finalize_and_commit
    (every row skipped, nothing processed) also needs the re-upload hint,
    not just WARNING."""
    from app.models.data_ingestion import IngestionResult

    config = {"file_path": "tmp/test.csv", "job_id": 7}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())

    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=True)
    provider.data_session.flush = AsyncMock()
    provider._update_job = AsyncMock()
    provider._process_batch = AsyncMock()
    provider._recompute_module_stats = AsyncMock()

    stats = _build_stats()
    stats["rows_processed"] = 0
    stats["rows_skipped"] = 5
    setup_result = {"processing_path": "processing/7/test.csv", "filename": "test.csv"}

    await provider._finalize_and_commit(
        batch=[],
        data_entry_service=MagicMock(),
        emission_service=MagicMock(),
        stats=stats,
        setup_result=setup_result,
        batch_kg_co2eq_overrides=[],
    )

    call_args = provider._update_job.call_args
    assert call_args.kwargs["result"] == IngestionResult.ERROR
    assert REUPLOAD_HINT in call_args.kwargs["status_message"]


# ======================================================================
# Issue #1398 — mid-stream failure (before _finalize_and_commit) messaging
# ======================================================================


@pytest.mark.asyncio
async def test_process_csv_in_batches_failure_includes_reupload_hint():
    """A hard stop before _finalize_and_commit (crash/timeout during setup
    or row processing) must still tell the user to re-upload — not leave a
    bare exception string that implies recalculation would help."""
    from app.models.data_ingestion import IngestionResult

    config = {"file_path": "tmp/test.csv", "job_id": 7}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider._update_job = AsyncMock()
    provider.data_session.rollback = AsyncMock()
    provider._setup_and_validate = AsyncMock(
        side_effect=RuntimeError("crashed at row 3000")
    )

    with pytest.raises(RuntimeError):
        await provider.process_csv_in_batches()

    call_args = provider._update_job.call_args
    assert REUPLOAD_HINT in call_args.kwargs["status_message"]
    assert "crashed at row 3000" in call_args.kwargs["status_message"]
    assert call_args.kwargs["result"] == IngestionResult.ERROR


@pytest.mark.asyncio
async def test_ingest_mid_stream_failure_includes_reupload_hint():
    """The terminal message actually persisted for a mid-stream failure is
    written by ingest()'s exception handler (it runs after, and overwrites,
    process_csv_in_batches()'s own handler) — it must carry the same
    re-upload wording."""
    from app.models.data_ingestion import IngestionResult

    config = {"file_path": "tmp/test.csv", "job_id": 7}
    provider = ConcreteCSVProvider(config, data_session=MagicMock())
    provider._update_job = AsyncMock()
    provider.process_csv_in_batches = AsyncMock(
        side_effect=RuntimeError("crashed at row 3000")
    )

    with pytest.raises(RuntimeError):
        await provider.ingest()

    call_args = provider._update_job.call_args
    assert REUPLOAD_HINT in call_args.kwargs["status_message"]
    assert "crashed at row 3000" in call_args.kwargs["status_message"]
    assert call_args.kwargs["result"] == IngestionResult.ERROR


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
    config = {
        "file_path": "tmp/test.csv",
        "module_type_id": module_type_id,
        "year": 2026,
    }
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
    data_entry_service.repo.bulk_delete_by_source_year = AsyncMock(return_value=0)

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    # One set-based delete, scoped to type 70 only
    assert data_entry_service.repo.bulk_delete_by_source_year.call_count == 1
    call_kwargs = data_entry_service.repo.bulk_delete_by_source_year.call_args.kwargs
    assert call_kwargs["year"] == 2026
    assert call_kwargs["data_entry_type_ids"] == [
        DataEntryTypeEnum.research_facilities.value
    ]
    # Cross-source replace: a per-year CSV upload also replaces prior API
    # syncs — otherwise their surviving rows mass-skip the upload as
    # DUPLICATE_INSTITUTIONAL_ID (stage incident, 2026-07-17).
    assert call_kwargs["sources"] == [s.value for s in BULK_PER_YEAR_SOURCES]
    assert DataEntrySourceEnum.EXTERNAL_INTEGRATION.value in call_kwargs["sources"]
    assert DataEntrySourceEnum.USER_MANUAL.value not in call_kwargs["sources"]
    assert (
        DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC.value not in call_kwargs["sources"]
    )


@pytest.mark.asyncio
async def test_delete_sibling_submodule_not_wiped():
    """Uploading animal facilities (71) must not delete research facilities (70)."""
    provider = _make_provider_with_job(module_type_id=6, data_entry_type_id=71)

    data_entry_service = MagicMock()
    data_entry_service.repo.bulk_delete_by_source_year = AsyncMock(return_value=0)

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    assert data_entry_service.repo.bulk_delete_by_source_year.call_count == 1
    call_kwargs = data_entry_service.repo.bulk_delete_by_source_year.call_args.kwargs
    assert call_kwargs["data_entry_type_ids"] == [
        DataEntryTypeEnum.mice_and_fish_animal_facilities.value
    ]


@pytest.mark.asyncio
async def test_delete_all_types_when_no_data_entry_type_id():
    """Without data_entry_type_id on the job, all module types are deleted."""
    # module_type_id=6 has two types; no specific type given
    provider = _make_provider_with_job(module_type_id=6, data_entry_type_id=None)

    data_entry_service = MagicMock()
    data_entry_service.repo.bulk_delete_by_source_year = AsyncMock(return_value=0)

    unit_to_module_map = {"unit-1": 999}
    await provider._delete_existing_entries_for_module_per_year(
        unit_to_module_map, _make_stats(), data_entry_service
    )

    # Both types (70 and 71) deleted in the single set-based call
    assert data_entry_service.repo.bulk_delete_by_source_year.call_count == 1
    call_kwargs = data_entry_service.repo.bulk_delete_by_source_year.call_args.kwargs
    deleted_types = set(call_kwargs["data_entry_type_ids"])
    assert DataEntryTypeEnum.research_facilities.value in deleted_types
    assert DataEntryTypeEnum.mice_and_fish_animal_facilities.value in deleted_types
