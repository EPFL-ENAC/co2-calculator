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
            "year": 2025,
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

    mock_factor = MagicMock(id=42)
    mock_factor.id = 42

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value={"k": mock_factor}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert setup["handlers"] == [handler]
    assert setup["required_columns"] == {"required_col"}
    assert "factors_map" in setup
    assert "factor_id_to_factor" in setup
    assert setup["factor_id_to_factor"] == {42: mock_factor}


@pytest.mark.asyncio
async def test_setup_handlers_and_factors_raises_when_year_missing():
    """Regression: a CSV upload that arrives without ``year`` in the
    payload must fail loudly at setup time rather than silently importing
    every row with primary_factor_id=None.

    The factor lookup keys on ``{type}:{year}:{kind}:{subkind}``, so a
    missing year produces a ``{type}:0:...`` key that never matches any
    real factor — the kind of silent miscompile this guard is meant to
    prevent. See base_csv_provider.py::_process_row, which now also has
    a defensive ``if self.year is None: raise`` so that even if a future
    caller bypasses setup the row loop refuses to fall back to a sentinel.
    """
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            # year deliberately omitted — mimics a frontend payload that
            # forgets to include it (the bug the guard catches).
        },
        data_session=MagicMock(),
    )

    with pytest.raises(ValueError, match="year is required"):
        await provider._setup_handlers_and_factors()


@pytest.mark.asyncio
async def test_setup_handlers_and_factors_raises_when_year_is_zero():
    """Sibling regression: ``year=0`` is also invalid. The guard uses
    ``if not self.year`` (matching the MODULE_PER_YEAR sibling's pattern)
    so falsy years are rejected the same as ``None``."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 0,
        },
        data_session=MagicMock(),
    )

    with pytest.raises(ValueError, match="year is required"):
        await provider._setup_handlers_and_factors()


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
    """Test validation passes when factor requirement is disabled."""
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
        category_field=None,
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

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"kind": "k1"},
        factor=None,  # No longer used
        stats=stats,
        row_idx=3,
        max_row_errors=5,
        setup_result=setup_result,
    )

    # Should succeed because require_factor_to_match=False
    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None


def test_extract_kind_subkind_values_no_handler():
    """Test _extract_kind_subkind_values with empty handlers list."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    kind, subkind = provider._extract_kind_subkind_values({"any": "row"}, [])

    assert kind == ""
    assert subkind is None


def test_extract_kind_subkind_values_missing_field():
    """Test _extract_kind_subkind_values when field doesn't exist in row."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(kind_field="kind", subkind_field="sub")
    filtered_row = {"other": "value"}

    kind, subkind = provider._extract_kind_subkind_values(filtered_row, [handler])

    assert kind == ""
    assert subkind is None


@pytest.mark.asyncio
async def test_resolve_from_category_missing_field(monkeypatch):
    """Test that missing category_field returns None data_entry_type."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(category_field="nonexistent_field")
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "required_columns": set(),
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
    assert "Missing data_entry_type_id" in error_msg


@pytest.mark.asyncio
async def test_setup_no_handler_for_type(monkeypatch):
    """Test error when no handler exists for data_entry_type."""


@pytest.mark.asyncio
async def test_setup_returns_empty_factor_id_map_with_no_factors(monkeypatch):
    """Test that factor_id_to_factor is empty dict when no factors loaded."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2025,
        },
        data_session=MagicMock(),
    )

    handler = MagicMock()
    handler.create_dto.model_fields = {}
    # Opt out of the empty-factors guard added in #1236 — this test
    # asserts the factor_id_to_factor mapping shape, not the
    # require-factor invariant (covered by test_guard_factors_required).
    handler.require_factor_to_match = False

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value={}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert "factor_id_to_factor" in setup
    assert setup["factor_id_to_factor"] == {}


@pytest.mark.asyncio
async def test_setup_returns_multiple_factors_in_id_map(monkeypatch):
    """Test factor_id_to_factor correctly maps multiple factors."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2025,
        },
        data_session=MagicMock(),
    )

    factor1 = MagicMock()
    factor1.id = 1
    factor2 = MagicMock()
    factor2.id = 2
    factor3 = MagicMock()
    factor3.id = 3

    handler = MagicMock()
    handler.create_dto.model_fields = {}

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value={"a": factor1, "b": factor2, "c": factor3}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert setup["factor_id_to_factor"] == {1: factor1, 2: factor2, 3: factor3}


@pytest.mark.asyncio
async def test_setup_skips_factors_without_id(monkeypatch):
    """Test that factors lacking an id attribute are skipped gracefully."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2025,
        },
        data_session=MagicMock(),
    )

    factor_with_id = MagicMock()
    factor_with_id.id = 10
    factor_without_id = MagicMock()
    factor_without_id.id = None  # type: ignore[assignment]

    handler = MagicMock()
    handler.create_dto.model_fields = {}

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(
            return_value={"with_id": factor_with_id, "without_id": factor_without_id}
        ),
    )

    setup = await provider._setup_handlers_and_factors()

    assert setup["factor_id_to_factor"] == {10: factor_with_id}


@pytest.mark.asyncio
async def test_resolve_handler_with_configured_type_provided():
    """Test that configured data_entry_type_id takes priority over category field."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.student.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        kind_field="kind",
        subkind_field=None,
        category_field="equipment_category",
        require_factor_to_match=False,
        require_subkind_for_factor=False,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "factor_id_to_factor": {},
        "required_columns": set(),
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"equipment_category": "not_used"},
        factor=None,
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    # Should use configured type, not category field
    assert data_entry_type == DataEntryTypeEnum.student
    assert resolved_handler == handler
    assert error_msg is None


@pytest.mark.asyncio
async def test_resolve_handler_from_category_field():
    """Test resolving data_entry_type from category_field when not in config."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv"},  # No data_entry_type_id in config
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        kind_field="kind",
        subkind_field=None,
        category_field="equipment_category",
        require_factor_to_match=False,
        require_subkind_for_factor=False,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {"10:test": MagicMock()},
        "factor_id_to_factor": {},
        "required_columns": {"kind"},
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"kind": "test", "equipment_category": "scientific"},
        factor=None,
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type == DataEntryTypeEnum.scientific
    assert error_msg is None


@pytest.mark.asyncio
async def test_all_data_entry_types_return_factor_id_to_factor(monkeypatch):
    """Every valid DataEntryTypeEnum must return factor_id_to_factor in setup."""
    for entry_type in list(DataEntryTypeEnum):
        provider = ModuleUnitSpecificCSVProvider(
            {
                "file_path": "tmp/test.csv",
                "data_entry_type_id": entry_type.value,
                "year": 2025,
            },
            data_session=MagicMock(),
        )

        handler = MagicMock()
        handler.create_dto.model_fields = {}
        # See sibling test — opt out of the require-factor guard so
        # this mapping-shape assertion still runs on empty factors.
        handler.require_factor_to_match = False

        monkeypatch.setattr(
            csv_providers_module.module_unit_specific.BaseModuleHandler,
            "get_by_type",
            MagicMock(return_value=handler),
        )
        monkeypatch.setattr(
            csv_providers_module.module_unit_specific,
            "load_factors_map",
            AsyncMock(return_value={}),
        )

        setup = await provider._setup_handlers_and_factors()

        assert "factor_id_to_factor" in setup, (
            f"missing factor_id_to_factor for {entry_type}"
        )
        assert isinstance(setup["factor_id_to_factor"], dict), (
            f"factor_id_to_factor for {entry_type} should be a dict"
        )
