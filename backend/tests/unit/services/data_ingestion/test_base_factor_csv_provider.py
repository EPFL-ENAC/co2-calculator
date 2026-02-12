"""Tests for BaseFactorCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.services.data_ingestion import base_factor_csv_provider
from app.services.data_ingestion.base_factor_csv_provider import BaseFactorCSVProvider


class ConcreteFactorProvider(BaseFactorCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_context(self):
        return {}


def _build_stats():
    return {
        "rows_processed": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }


def test_resolve_data_entry_type_configured():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1},
        data_session=MagicMock(),
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={},
        valid_entry_types=[DataEntryTypeEnum.member],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_from_id_invalid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type_id": "999"},
        valid_entry_types=[DataEntryTypeEnum.member],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


def test_resolve_data_entry_type_from_name_valid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type": "member"},
        valid_entry_types=[DataEntryTypeEnum.member],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_from_name_invalid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type": "not-valid"},
        valid_entry_types=[DataEntryTypeEnum.member],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


def test_resolve_data_entry_type_single_valid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={},
        valid_entry_types=[DataEntryTypeEnum.member],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_missing_multi():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    data_entry_type = provider._resolve_data_entry_type(
        row={},
        valid_entry_types=[DataEntryTypeEnum.member, DataEntryTypeEnum.student],
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


@pytest.mark.asyncio
async def test_process_row_missing_factor_variant_for_trips():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    setup_result = {
        "expected_columns": {"data_entry_type_id"},
        "valid_entry_types": [DataEntryTypeEnum.trips],
        "factor_variant": None,
    }

    factor, error_msg = await provider._process_row(
        row={"data_entry_type_id": str(DataEntryTypeEnum.trips.value)},
        row_idx=1,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=MagicMock(),
    )

    assert factor is None
    assert "Missing factor_variant" in error_msg
    assert stats["rows_skipped"] == 1


@pytest.mark.asyncio
async def test_process_row_validation_error_records_error(monkeypatch):
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()

    handler = MagicMock()
    handler.validate_create.side_effect = ValueError("bad payload")

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )

    setup_result = {
        "expected_columns": {"data_entry_type_id"},
        "valid_entry_types": [DataEntryTypeEnum.member],
        "factor_variant": None,
    }

    factor, error_msg = await provider._process_row(
        row={"data_entry_type_id": str(DataEntryTypeEnum.member.value)},
        row_idx=2,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=MagicMock(),
    )

    assert factor is None
    assert "Validation error" in error_msg
    assert stats["rows_skipped"] == 1


@pytest.mark.asyncio
async def test_process_row_success(monkeypatch):
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "year": 2024},
        data_session=MagicMock(),
    )
    stats = _build_stats()

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        emission_type_id=10,
        is_conversion=False,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        classification={"kind": "x"},
        values={"value": 1.0},
    )

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )

    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock(return_value=SimpleNamespace(id=1))

    setup_result = {
        "expected_columns": {"data_entry_type_id"},
        "valid_entry_types": [DataEntryTypeEnum.member],
        "factor_variant": None,
    }

    factor, error_msg = await provider._process_row(
        row={"data_entry_type_id": str(DataEntryTypeEnum.member.value)},
        row_idx=3,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=factor_service,
    )

    assert error_msg is None
    assert factor.id == 1
    factor_service.prepare_create.assert_awaited_once()


def test_validate_csv_headers_strict_missing_expected():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "strict_column_validation": True},
        data_session=MagicMock(),
    )

    csv_text = "col1,col2\nval1,val2"
    expected_columns = {"col1", "col2", "col3"}

    with pytest.raises(ValueError, match="Strict mode"):
        provider._validate_csv_headers(csv_text, expected_columns, set())


@pytest.mark.asyncio
async def test_finalize_and_commit_move_file_failure():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "job_id": 1, "year": 2024},
        data_session=MagicMock(),
    )
    provider._files_store = MagicMock()
    provider._files_store.move_file = AsyncMock(return_value=False)
    provider.data_session.flush = AsyncMock()

    with pytest.raises(ValueError, match="Failed to move file"):
        await provider._finalize_and_commit(
            batch=[],
            factor_service=MagicMock(),
            stats=_build_stats(),
            setup_result={"processing_path": "processing/x", "filename": "x.csv"},
        )
