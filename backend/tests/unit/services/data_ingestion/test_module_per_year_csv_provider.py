"""Tests for ModulePerYearCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion import csv_providers as csv_providers_module
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
)


def _build_stats():
    return {
        "rows_processed": 0,
        "rows_with_factors": 0,
        "rows_without_factors": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
    }


def test_extract_kind_subkind_values_from_handler_fields():
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )

    handler = SimpleNamespace(kind_field="kind", subkind_field="subkind")
    filtered_row = {"kind": "k1", "subkind": "s1"}

    kind, subkind = provider._extract_kind_subkind_values(filtered_row, [handler])

    assert kind == "k1"
    assert subkind == "s1"


def test_extract_kind_subkind_values_fallback_fields():
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )

    handler = SimpleNamespace(kind_field=None, subkind_field=None)
    filtered_row = {"Kind": "k2"}

    kind, subkind = provider._extract_kind_subkind_values(filtered_row, [handler])

    assert kind == "k2"
    assert subkind is None


@pytest.mark.asyncio
async def test_setup_handlers_and_factors_multiple_types(monkeypatch):
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.headcount.value)

    handler = MagicMock()
    handler.create_dto.model_fields = {"kind": MagicMock(), "value": MagicMock()}

    monkeypatch.setattr(
        csv_providers_module.module_per_year.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_per_year,
        "load_factors_map",
        AsyncMock(return_value={"k": []}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert setup["handlers"]
    assert setup["expected_columns"] == {"kind", "value"}
    assert "unit_institutional_id" in setup["required_columns"]


@pytest.mark.asyncio
async def test_setup_handlers_and_factors_invalid_data_entry_type(monkeypatch):
    provider = ModulePerYearCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.scientific.value,
        },
        data_session=MagicMock(),
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.headcount.value)

    monkeypatch.setattr(
        csv_providers_module.module_per_year.BaseModuleHandler,
        "get_by_type",
        MagicMock(),
    )

    with pytest.raises(Exception, match="not valid for module type"):
        await provider._setup_handlers_and_factors()


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_configured_missing_factor():
    """Test validation succeeds with configured type even if factor not in map."""
    provider = ModulePerYearCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=True,
        kind_field="kind",
        subkind_field=None,
        category_field=None,
    )
    # Empty factors_map, but configured type should bypass factor check
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={},
        factor=None,  # No longer used but kept for signature compatibility
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    # With configured data_entry_type_id, validation should succeed
    # Factor lookup happens later via ModuleHandlerService
    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_factor_mismatch():
    """Test validation passes when factor requirement is disabled."""
    provider = ModulePerYearCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=False,
        kind_field="kind",
        subkind_field=None,
        category_field=None,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},  # Empty map, but require_factor_to_match=False
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={},
        factor=None,  # No longer used
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    # Should succeed because require_factor_to_match=False
    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_missing_factor_no_config():
    """Test validation when no configured type and factor not in map."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )

    handler = SimpleNamespace(
        require_factor_to_match=True,
        kind_field="kind",
        subkind_field=None,
        category_field=None,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},  # Empty map
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={},
        factor=None,  # No longer used
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    # Should fail because no configured type and factor not found in map
    assert data_entry_type is None
    assert resolved_handler is None
    assert "Missing factor" in error_msg
    assert stats["rows_skipped"] == 1
