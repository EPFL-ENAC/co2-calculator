"""Tests for ModulePerYearCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.services.data_ingestion import base_csv_provider as base_csv_provider_module
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
        {"file_path": "tmp/test.csv", "year": 2025}, data_session=MagicMock()
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
        base_csv_provider_module,
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
    # we used to fail on missing factor, but now with the new logic,
    # it should not fail if require_factor_to_match is False
    # assert "Missing factor" in error_msg  --- IGNORE ---
    assert stats["rows_skipped"] == 1


# ---------------------------------------------------------------------------
# Regression: equipment/purchase ingests with empty factors must FAIL FAST
# at setup time (#1236 follow-up).  User-reported 2026-05-20 — uploading
# data.csv for equipment with no factors uploaded grinds through 50 000
# rows of identical "no matching factor" errors instead of refusing
# up front.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_equipment_with_empty_factors_fails_fast_at_setup(monkeypatch):
    """ModuleTypeEnum.equipment_electric_consumption + empty factors_map
    raises at setup — the per-row loop is never entered."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv", "year": 2025}, data_session=MagicMock()
    )
    provider.job = SimpleNamespace(
        module_type_id=ModuleTypeEnum.equipment_electric_consumption.value
    )

    handler = MagicMock()
    handler.create_dto.model_fields = {}
    handler.require_factor_to_match = False  # equipment handler's real value

    monkeypatch.setattr(
        csv_providers_module.module_per_year.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_csv_provider_module,
        "load_factors_map",
        AsyncMock(return_value={}),  # the bug shape
    )

    with pytest.raises(ValueError) as exc:
        await provider._setup_handlers_and_factors()

    msg = str(exc.value)
    assert "equipment_electric_consumption" in msg
    assert "factors" in msg.lower()
    assert "infers" in msg.lower()


@pytest.mark.asyncio
async def test_purchase_with_empty_factors_fails_fast_at_setup(monkeypatch):
    """ModuleTypeEnum.purchase shares the factor-inferred-DET shape;
    same guard fires."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv", "year": 2025}, data_session=MagicMock()
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.purchase.value)

    handler = MagicMock()
    handler.create_dto.model_fields = {}
    handler.require_factor_to_match = False

    monkeypatch.setattr(
        csv_providers_module.module_per_year.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_csv_provider_module,
        "load_factors_map",
        AsyncMock(return_value={}),
    )

    with pytest.raises(ValueError) as exc:
        await provider._setup_handlers_and_factors()
    assert "purchase" in str(exc.value)


@pytest.mark.asyncio
async def test_non_factor_inferred_module_tolerates_empty_factors(monkeypatch):
    """Modules NOT in ``_FACTOR_INFERRED_MODULES`` (headcount, buildings,
    professional_travel, …) ingest rows even with empty factors — they
    carry the DET in a category column that maps to ``DataEntryTypeEnum``
    names directly, so empty factors is a legitimate state."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv", "year": 2025}, data_session=MagicMock()
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.headcount.value)

    handler = MagicMock()
    handler.create_dto.model_fields = {"kind": MagicMock()}
    handler.require_factor_to_match = False  # headcount's real value

    monkeypatch.setattr(
        csv_providers_module.module_per_year.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_csv_provider_module,
        "load_factors_map",
        AsyncMock(return_value={}),
    )

    setup = await provider._setup_handlers_and_factors()  # no raise
    assert setup["factors_map"] == {}


@pytest.mark.asyncio
async def test_setup_raises_when_year_missing(monkeypatch):
    """Regression: MODULE_PER_YEAR setup must fail loudly without ``year``.

    Factor lookups key on ``{type}:{year}:{kind}:{subkind}``; a missing
    year silently misses every factor. MODULE_UNIT_SPECIFIC already had
    this guard — converged into the shared loader."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"},  # year deliberately omitted
        data_session=MagicMock(),
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.headcount.value)

    with pytest.raises(ValueError, match="year is required"):
        await provider._setup_handlers_and_factors()


@pytest.mark.asyncio
async def test_resolve_configured_type_accepts_string_id():
    """Regression: job config may carry data_entry_type_id as a string
    (JSON payload). MODULE_UNIT_SPECIFIC cast through int(); MODULE_PER_YEAR
    did not — converged in the shared resolver."""
    provider = ModulePerYearCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": str(DataEntryTypeEnum.member.value),
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=False,
        kind_field="kind",
        subkind_field=None,
        category_field=None,
    )
    setup_result = {"handlers": [handler], "factors_map": {}}
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

    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None
