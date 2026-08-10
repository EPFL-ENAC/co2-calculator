"""Tests for ModuleHandlerService.

Factor-classification matching is owned and tested by ``FactorResolver``
(``tests/unit/services/test_factor_resolver.py``); list-time resolution by
the SQL subquery in ``DataEntryRepository``. What remains here is what the
service itself owns: the pure kind-change clearing normalization on update
payloads, and taxonomy building.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
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
        to_label=lambda x: x.capitalize(),
    )
    return handler


def _purchase_handler():
    """Override-style handler (e.g. purchase): kind_field_override is set,
    no factor_value_fields declared.
    """
    return SimpleNamespace(
        kind_field="purchase_institutional_code",
        subkind_field=None,
        kind_field_override="purchase_additional_code",
        kind_label_field=None,
        subkind_label_field=None,
        to_label=lambda x: x.capitalize(),
    )


# ── clear_dependent_fields_on_kind_change ───────────────────


def test_clear_kind_changed_clears_subkind_and_override():
    handler = _purchase_handler()
    handler.subkind_field = "subkind"
    payload = {
        "purchase_institutional_code": "NEW",
        "subkind": "old-sub",
        "purchase_additional_code": "OLD-CODE",
    }
    result = ModuleHandlerService.clear_dependent_fields_on_kind_change(
        handler,
        payload,
        item_data={"purchase_institutional_code": "NEW"},
        existing_data={"purchase_institutional_code": "OLD"},
    )
    assert result["subkind"] is None
    assert result["purchase_additional_code"] is None


def test_clear_kind_changed_keeps_fields_supplied_in_request():
    handler = _purchase_handler()
    handler.subkind_field = "subkind"
    payload = {
        "purchase_institutional_code": "NEW",
        "subkind": "new-sub",
        "purchase_additional_code": "NEW-CODE",
    }
    result = ModuleHandlerService.clear_dependent_fields_on_kind_change(
        handler,
        payload,
        item_data={
            "purchase_institutional_code": "NEW",
            "subkind": "new-sub",
            "purchase_additional_code": "NEW-CODE",
        },
        existing_data={"purchase_institutional_code": "OLD"},
    )
    assert result["subkind"] == "new-sub"
    assert result["purchase_additional_code"] == "NEW-CODE"


def test_clear_kind_unchanged_leaves_payload_untouched():
    handler = _make_handler()
    payload = {"kind": "same", "subkind": "keep-me"}
    result = ModuleHandlerService.clear_dependent_fields_on_kind_change(
        handler,
        payload,
        item_data={"kind": "same", "note": "hi"},
        existing_data={"kind": "same", "subkind": "keep-me"},
    )
    assert result == {"kind": "same", "subkind": "keep-me"}


def test_clear_kind_absent_from_request_leaves_payload_untouched():
    handler = _make_handler()
    payload = {"kind": "old", "subkind": "keep-me"}
    result = ModuleHandlerService.clear_dependent_fields_on_kind_change(
        handler,
        payload,
        item_data={"subkind": "keep-me", "note": "hi"},
        existing_data={"kind": "old", "subkind": "other"},
    )
    assert result["subkind"] == "keep-me"


def test_clear_no_existing_data_is_noop():
    handler = _make_handler()
    payload = {"kind": "new", "subkind": "s"}
    result = ModuleHandlerService.clear_dependent_fields_on_kind_change(
        handler, payload, item_data={"kind": "new"}, existing_data=None
    )
    assert result == {"kind": "new", "subkind": "s"}


# ── get_taxonomy ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_taxonomy_builds_tree(service):
    handler = _make_handler()
    factors = [
        Factor(emission_type_id=1, classification={"kind": "A", "subkind": "A1"}),
        Factor(emission_type_id=1, classification={"kind": "A", "subkind": "A2"}),
        Factor(emission_type_id=1, classification={"kind": "B", "subkind": "B1"}),
    ]
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)

    result = await service.get_taxonomy(
        handler, DataEntryTypeEnum.scientific, year=2025
    )

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
