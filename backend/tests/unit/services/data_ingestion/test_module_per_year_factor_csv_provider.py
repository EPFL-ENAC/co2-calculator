"""Tests for ModulePerYearFactorCSVProvider."""

from unittest.mock import MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.services.data_ingestion import csv_providers as csv_providers_module
from app.services.data_ingestion.csv_providers.factors import (
    ModulePerYearFactorCSVProvider,
)


def _make_handler(required_field_name="value"):
    field_required = MagicMock()
    field_required.is_required.return_value = True
    handler = MagicMock()
    handler.create_dto.model_fields = {required_field_name: field_required}
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

    monkeypatch.setattr(
        csv_providers_module.factors.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        provider,
        "_resolve_valid_entry_types",
        MagicMock(return_value=[DataEntryTypeEnum.member]),
    )

    setup = await provider._setup_handlers_and_context()

    assert setup["handlers"] == [handler]
    assert setup["required_columns"] == {"value"}


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
