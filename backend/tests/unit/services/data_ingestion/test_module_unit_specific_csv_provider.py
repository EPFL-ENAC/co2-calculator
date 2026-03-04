"""Tests for ModuleUnitSpecificCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.services.data_ingestion import csv_providers as csv_providers_module
from app.services.data_ingestion.csv_providers.module_unit_specific import (
    ModuleUnitSpecificCSVProvider,
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


@pytest.mark.asyncio
async def test_setup_handlers_and_factors_single_type(monkeypatch):
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    field_required = MagicMock()
    field_required.is_required.return_value = True
    field_optional = MagicMock()
    field_optional.is_required.return_value = False

    handler = MagicMock()
    handler.create_dto.model_fields = {
        "required_col": field_required,
        "optional_col": field_optional,
    }

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value={"k": []}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert setup["handlers"] == [handler]
    assert setup["required_columns"] == {"required_col"}


def test_extract_kind_subkind_values_from_handler():
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(kind_field="kind", subkind_field="subkind")
    filtered_row = {"kind": "k1", "subkind": "s1"}

    kind, subkind = provider._extract_kind_subkind_values(filtered_row, [handler])

    assert kind == "k1"
    assert subkind == "s1"


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_missing_required_fields():
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=False, kind_field="kind", subkind_field=None
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "required_columns": {"amount"},
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={},
        factor=None,
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type is None
    assert resolved_handler is None
    assert "Missing required fields" in error_msg
    assert stats["rows_skipped"] == 1


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_missing_factor(monkeypatch):
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=True,
        require_subkind_for_factor=False,
        kind_field="kind",
        subkind_field="subkind",
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "required_columns": set(),
    }
    stats = _build_stats()

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "is_in_factors_map",
        MagicMock(return_value=False),
    )

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"kind": "k1"},
        factor=None,
        stats=stats,
        row_idx=2,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type is None
    assert resolved_handler is None
    assert "No matching factor" in error_msg
    assert stats["rows_skipped"] == 1


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_factor_mismatch(monkeypatch):
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=False,
        require_subkind_for_factor=False,
        kind_field="kind",
        subkind_field=None,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "required_columns": set(),
    }
    stats = _build_stats()

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "is_in_factors_map",
        MagicMock(return_value=True),
    )

    factor = SimpleNamespace(data_entry_type_id=DataEntryTypeEnum.student.value)

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"kind": "k1"},
        factor=factor,
        stats=stats,
        row_idx=3,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type is None
    assert resolved_handler is None
    assert "mismatch" in error_msg
    assert stats["rows_skipped"] == 1
