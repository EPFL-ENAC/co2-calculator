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
async def test_finalize_and_commit_routes_batch_through_upsert(monkeypatch):
    """Plan 310B Part 2: factor ingest upserts in place; never bulk-deletes.

    Confirms ``_finalize_and_commit`` routes a non-empty batch through
    ``factor_repo.upsert_factors`` stamped with the parent job_id, and
    reports the result in ``stats['factors_upserted']``.
    """
    from app.models.factor import Factor

    mock_data_session = MagicMock()
    mock_data_session.flush = AsyncMock()

    provider = ModulePerYearFactorCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2024,
            "job_id": 42,
        },
        data_session=mock_data_session,
    )
    provider._files_store = MagicMock()
    provider._files_store.move_file = AsyncMock(return_value=True)

    mock_factor_repo = MagicMock()
    mock_factor_repo.upsert_factors = AsyncMock(return_value=3)

    batch = [
        Factor(
            emission_type_id=10000,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            classification={"kind": "food"},
            values={"kg_co2eq_per_fte": 420},
            year=2024,
        )
    ]
    stats = {
        "rows_processed": 1,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
        "factors_deleted": 0,
        "factors_upserted": 0,
    }

    result = await provider._finalize_and_commit(
        batch=batch,
        factor_service=MagicMock(),
        stats=stats,
        setup_result={"processing_path": "processing/x", "filename": "x.csv"},
        factor_repo=mock_factor_repo,
    )

    mock_factor_repo.upsert_factors.assert_awaited_once()
    args, kwargs = mock_factor_repo.upsert_factors.call_args
    assert kwargs.get("current_job_id") == 42
    assert stats["factors_upserted"] == 3
    assert stats["factors_deleted"] == 0
    assert result["state"].value == 3  # IngestionState.FINISHED
