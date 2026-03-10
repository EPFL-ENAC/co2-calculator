"""Tests for ModuleHandlerService."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.services.module_handler_service import ModuleHandlerService


@pytest.fixture
def service():
    session = MagicMock()
    return ModuleHandlerService(session)


def _make_handler(kind_field="kind", subkind_field="subkind"):
    handler = SimpleNamespace(
        kind_field=kind_field,
        subkind_field=subkind_field,
        kind_label_field=None,
        subkind_label_field=None,
    )
    return handler


# ── resolve_primary_factor_id ──────────────────────────────


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_with_subkind(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=42)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA", "subkind": "SubA1"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.scientific
    )

    assert result["primary_factor_id"] == 42
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.scientific,
        kind="ClassA",
        subkind="SubA1",
    )


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_no_subkind_field(service):
    """When handler has subkind_field=None (e.g. EnergyCombustion)."""
    handler = _make_handler(kind_field="name", subkind_field=None)
    factor = SimpleNamespace(id=7)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    payload = {"name": "natural_gas"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.energy_combustion
    )

    assert result["primary_factor_id"] == 7
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.energy_combustion,
        kind="natural_gas",
        subkind=None,
    )


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_no_kind_field(service):
    """When handler has no kind_field, payload is returned unchanged."""
    handler = _make_handler(kind_field=None, subkind_field=None)

    payload = {"foo": "bar"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.scientific
    )

    assert result == {"foo": "bar"}
    assert "primary_factor_id" not in result


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_merges_existing_data(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=10)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA"}
    existing = {"subkind": "SubB1"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.scientific, existing_data=existing
    )

    assert result["primary_factor_id"] == 10
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.scientific,
        kind="ClassA",
        subkind="SubB1",
    )


# ── resolve_primary_factor_if_changed ──────────────────────


@pytest.mark.asyncio
async def test_resolve_if_changed_no_existing_data(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=5)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    result = await service.resolve_primary_factor_if_changed(
        handler,
        {"kind": "A", "subkind": "B"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "A"},
        existing_data=None,
    )

    assert result["primary_factor_id"] == 5


@pytest.mark.asyncio
async def test_resolve_if_changed_kind_changed(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=99)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    result = await service.resolve_primary_factor_if_changed(
        handler,
        {"kind": "NewClass", "subkind": "Sub1"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "NewClass"},
        existing_data={"kind": "OldClass", "subkind": "Sub1"},
    )

    assert result["subkind"] is None
    assert result["primary_factor_id"] == 99


@pytest.mark.asyncio
async def test_resolve_if_changed_nothing_changed(service):
    handler = _make_handler()

    result = await service.resolve_primary_factor_if_changed(
        handler,
        {"kind": "Same", "subkind": "Sub"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "Same"},
        existing_data={"kind": "Same", "subkind": "Sub"},
    )

    assert "primary_factor_id" not in result


# ── get_taxonomy ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_taxonomy_builds_tree(service):
    handler = _make_handler()
    factors = [
        SimpleNamespace(classification={"kind": "A", "subkind": "A1"}),
        SimpleNamespace(classification={"kind": "A", "subkind": "A2"}),
        SimpleNamespace(classification={"kind": "B", "subkind": "B1"}),
    ]
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)

    result = await service.get_taxonomy(handler, DataEntryTypeEnum.scientific)

    assert result.name == "scientific"
    assert len(result.children) == 2
    a_node = result.children[0]
    assert a_node.name == "A"
    assert len(a_node.children) == 2
    assert a_node.children[0].name == "A1"
    assert a_node.children[1].name == "A2"
    b_node = result.children[1]
    assert b_node.name == "B"
    assert len(b_node.children) == 1
