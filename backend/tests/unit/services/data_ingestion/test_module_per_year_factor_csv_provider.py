"""Tests for ModulePerYearFactorCSVProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.services.data_ingestion import csv_providers as csv_providers_module
from app.services.data_ingestion.csv_providers.factors import (
    ModulePerYearFactorCSVProvider,
)


def _make_handler(required_field_name="value"):
    handler = MagicMock()
    handler.expected_columns = {required_field_name}
    handler.required_columns = {required_field_name}
    return handler


@pytest.mark.asyncio
async def test_setup_handlers_and_context_single_type(monkeypatch):
    provider = ModulePerYearFactorCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = _make_handler()

    get_by_type = MagicMock(return_value=handler)
    monkeypatch.setattr(
        csv_providers_module.factors.BaseFactorHandler,
        "get_by_type",
        get_by_type,
    )
    monkeypatch.setattr(
        provider,
        "_resolve_valid_entry_types",
        MagicMock(return_value=[DataEntryTypeEnum.member]),
    )

    setup = await provider._setup_handlers_and_context()

    assert setup["handlers"] == [handler]
    assert setup["required_columns"] == {"value"}
    get_by_type.assert_called_once_with(DataEntryTypeEnum.member)


@pytest.mark.asyncio
async def test_setup_handlers_and_context_multiple_types(monkeypatch):
    provider = ModulePerYearFactorCSVProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )

    handler_one = _make_handler("field1")
    handler_two = _make_handler("field2")

    monkeypatch.setattr(
        csv_providers_module.factors.BaseFactorHandler,
        "get_by_type",
        MagicMock(side_effect=[handler_one, handler_two]),
    )
    monkeypatch.setattr(
        provider,
        "_resolve_valid_entry_types",
        MagicMock(return_value=[DataEntryTypeEnum.member, DataEntryTypeEnum.student]),
    )

    setup = await provider._setup_handlers_and_context()

    assert setup["handlers"] == [handler_one, handler_two]
    assert setup["required_columns"] == set()


@pytest.mark.asyncio
async def test_process_csv_in_batches_deletes_existing_factors(monkeypatch):
    """Test that existing factors are deleted before inserting new ones."""
    from app.services.factor_service import FactorService

    # Create a properly mocked data session
    mock_data_session = MagicMock()
    mock_data_session.flush = AsyncMock()
    mock_data_session.commit = AsyncMock()  # likely also needed in _finalize_and_commit
    mock_result = MagicMock()
    mock_result.all = MagicMock(return_value=[])
    mock_data_session.exec = MagicMock(return_value=mock_result)

    provider = ModulePerYearFactorCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2024,
        },
        data_session=mock_data_session,
    )

    # Mock the setup method
    setup_result = {
        "csv_text": "value\n100\n200",
        "handlers": [_make_handler()],
        "expected_columns": {"value"},
        "required_columns": {"value"},
        "processing_path": "processing/test.csv",
        "filename": "test.csv",
        "valid_entry_types": [DataEntryTypeEnum.member],
    }

    async def mock_setup():
        return setup_result

    monkeypatch.setattr(provider, "_setup_and_validate", mock_setup)

    # Create a mock FactorService
    mock_factor_service = MagicMock(spec=FactorService)
    mock_factor_service.count_by_data_entry_type_and_year = AsyncMock(return_value=5)
    mock_factor_service.bulk_delete_by_data_entry_type = AsyncMock()
    mock_factor_service.bulk_create = AsyncMock(return_value=[])

    # Patch FactorService instantiation to return our mocked service
    monkeypatch.setattr(
        "app.services.data_ingestion.base_factor_csv_provider.FactorService",
        MagicMock(return_value=mock_factor_service),
    )

    async def mock_process_batch(batch, factor_service):
        pass

    monkeypatch.setattr(provider, "_process_batch", mock_process_batch)

    # Mock file store operations
    mock_files_store = MagicMock()
    mock_files_store.move_file = AsyncMock(return_value=True)
    mock_files_store.get_file = AsyncMock(return_value=(b"value\n100\n200", "text/csv"))
    mock_files_store.file_exists = AsyncMock(return_value=True)

    provider._files_store = mock_files_store

    # Mock repo
    mock_repo = MagicMock()
    provider._repo = mock_repo

    # Call process_csv_in_batches
    result = await provider.process_csv_in_batches()

    # Verify deletion was called
    mock_factor_service.count_by_data_entry_type_and_year.assert_called_once()
    mock_factor_service.bulk_delete_by_data_entry_type.assert_called_once()

    # Verify stats include factors_deleted
    assert "factors_deleted" in result
    assert result["factors_deleted"] == 5
