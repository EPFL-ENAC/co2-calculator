"""Tests for ModuleHandlerService.

Factor-classification matching itself (kind/subkind chain, override-key-first
rule, ambiguity handling) is owned and tested by ``FactorResolver`` — see
``tests/unit/services/test_factor_resolver.py``. These tests cover what
``ModuleHandlerService`` itself is responsible for: merging existing_data
into a lookup copy without mutating the caller's payload, delegating to
``FactorResolver``, the kind-change clearing side-effects, and
``populate_defaults``.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
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
    no factor_value_fields declared."""
    return SimpleNamespace(
        kind_field="purchase_institutional_code",
        subkind_field=None,
        kind_field_override="purchase_additional_code",
        kind_label_field=None,
        subkind_label_field=None,
        to_label=lambda x: x.capitalize(),
    )


# ── resolve_factor ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_factor_delegates_to_resolver(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=42)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA", "subkind": "SubA1"}
    result = await service.resolve_factor(
        handler, payload, DataEntryTypeEnum.scientific, year=2025
    )

    assert result is factor
    service.factor_resolver.resolve.assert_awaited_once_with(
        handler,
        {"kind": "ClassA", "subkind": "SubA1"},
        DataEntryTypeEnum.scientific,
        2025,
    )


@pytest.mark.asyncio
async def test_resolve_factor_no_match_returns_none(service):
    handler = _make_handler(kind_field=None, subkind_field=None)
    service.factor_resolver.resolve = AsyncMock(return_value=None)

    payload = {"foo": "bar"}
    result = await service.resolve_factor(
        handler, payload, DataEntryTypeEnum.scientific, year=2025
    )

    assert result is None
    assert payload == {"foo": "bar"}


@pytest.mark.asyncio
async def test_resolve_factor_merges_existing_data(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=10)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA"}
    existing = {"subkind": "SubB1"}
    result = await service.resolve_factor(
        handler,
        payload,
        DataEntryTypeEnum.scientific,
        year=2025,
        existing_data=existing,
    )

    assert result is factor
    service.factor_resolver.resolve.assert_awaited_once_with(
        handler,
        {"kind": "ClassA", "subkind": "SubB1"},
        DataEntryTypeEnum.scientific,
        2025,
    )


@pytest.mark.asyncio
async def test_resolve_factor_does_not_mutate_payload(service):
    """existing_data merges into a COPY used for the lookup — the caller's
    payload dict and the existing_data dict are left untouched."""
    handler = _make_handler()
    factor = SimpleNamespace(id=10)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA"}
    existing = {"subkind": "SubB1"}
    await service.resolve_factor(
        handler,
        payload,
        DataEntryTypeEnum.scientific,
        year=2025,
        existing_data=existing,
    )

    assert payload == {"kind": "ClassA"}
    assert existing == {"subkind": "SubB1"}


@pytest.mark.asyncio
async def test_resolve_factor_override_handler_returns_full_factor(service):
    """Behavior change from the old stamping code: override handlers
    (purchase) used to always come back with factor=None even on a match
    (only the id was stamped); resolve_factor now returns the full Factor
    since nothing needs to hide it from the caller anymore."""
    handler = _purchase_handler()
    factor = SimpleNamespace(
        id=11, classification={"purchase_additional_code": "ADD-1"}
    )
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    payload = {
        "purchase_institutional_code": "A",
        "purchase_additional_code": "ADD-1",
    }
    result = await service.resolve_factor(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result is factor


@pytest.mark.asyncio
async def test_resolve_factor_wires_real_factor_resolver():
    """End-to-end sanity check that the service really composes a live
    FactorResolver rather than the mocked stand-in used by the other tests
    here — guards against the wiring itself breaking silently."""
    handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum.it)
    assert handler.kind_field is not None
    factor = Factor(
        id=7,
        data_entry_type_id=DataEntryTypeEnum.it.value,
        emission_type_id=1,
        classification={handler.kind_field: "Mill"},
        values={},
        year=2025,
    )
    service = ModuleHandlerService(MagicMock())

    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=AsyncMock(return_value=[factor]),
    ):
        result = await service.resolve_factor(
            handler,
            {handler.kind_field: "Mill"},
            DataEntryTypeEnum.it,
            year=2025,
        )

    assert result is not None
    assert result.id == 7


# ── populate_defaults ───────────────────────────────────────


@pytest.mark.asyncio
async def test_populate_defaults_applies_when_factor_given(service):
    """Defaults apply whenever a factor is passed in — no
    stored-id-matches-factor.id guard anymore."""
    handler = SimpleNamespace(factor_value_fields=["active_usage_hours_per_week"])
    factor = SimpleNamespace(id=42, values={"active_usage_hours_per_week": 40})
    data = {"name": "Freezer"}

    result = await service.populate_defaults(handler, data, factor)

    assert result["active_usage_hours_per_week"] == 40


@pytest.mark.asyncio
async def test_populate_defaults_skips_field_already_set(service):
    handler = SimpleNamespace(factor_value_fields=["active_usage_hours_per_week"])
    factor = SimpleNamespace(id=42, values={"active_usage_hours_per_week": 40})
    data = {"active_usage_hours_per_week": 12}

    result = await service.populate_defaults(handler, data, factor)

    assert result["active_usage_hours_per_week"] == 12


@pytest.mark.asyncio
async def test_populate_defaults_noop_without_factor_value_fields(service):
    """Purchase-style override handlers never declare factor_value_fields,
    so the new full-Factor return (was None before) is a no-op here."""
    handler = _purchase_handler()
    factor = SimpleNamespace(id=11, values={"ef_kg_co2eq_per_currency": 0.4})
    data = {"purchase_institutional_code": "A"}

    result = await service.populate_defaults(handler, data, factor)

    assert result == {"purchase_institutional_code": "A"}


# ── resolve_factor_if_changed ───────────────────────────────


@pytest.mark.asyncio
async def test_resolve_if_changed_no_existing_data(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=5)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"kind": "A", "subkind": "B"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "A"},
        existing_data=None,
        year=2025,
    )

    assert resolved_factor is factor
    assert "primary_factor_id" not in result


@pytest.mark.asyncio
async def test_resolve_if_changed_kind_changed(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=99)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"kind": "NewClass", "subkind": "Sub1"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "NewClass"},
        existing_data={"kind": "OldClass", "subkind": "Sub1"},
        year=2025,
    )

    assert result["subkind"] is None
    assert resolved_factor is factor
    assert "primary_factor_id" not in result


@pytest.mark.asyncio
async def test_resolve_if_changed_kind_changed_populates_defaults(service):
    """kind change re-resolves and repopulates factor_value_fields — this
    now fires whenever a factor comes back, not only when a stored
    primary_factor_id happened to already match it."""
    handler = _make_handler()
    handler.factor_value_fields = ["active_usage_hours_per_week"]
    factor = SimpleNamespace(id=99, values={"active_usage_hours_per_week": 40})
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"kind": "NewClass", "subkind": "Sub1"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "NewClass"},
        existing_data={"kind": "OldClass", "subkind": "Sub1"},
        year=2025,
    )

    assert result["active_usage_hours_per_week"] == 40
    assert resolved_factor is factor


@pytest.mark.asyncio
async def test_resolve_if_changed_nothing_changed(service):
    handler = _make_handler()
    service.factor_resolver.resolve = AsyncMock()

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"kind": "Same", "subkind": "Sub"},
        DataEntryTypeEnum.scientific,
        item_data={"kind": "Same"},
        existing_data={"kind": "Same", "subkind": "Sub"},
        year=2025,
    )

    assert "primary_factor_id" not in result
    assert resolved_factor is None
    service.factor_resolver.resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_if_changed_kind_change_clears_stale_override(service):
    """Changing A without resending B must clear the stored B, not reuse it.

    Regression: with A=41112200/B=VC02 stored, updating only A left VC02 in
    the merged data, so resolution kept matching the OLD code's factor.
    """
    handler = _purchase_handler()
    new_factor = SimpleNamespace(id=81)
    service.factor_resolver.resolve = AsyncMock(return_value=new_factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"purchase_institutional_code": "41112201"},
        DataEntryTypeEnum.services,
        item_data={"purchase_institutional_code": "41112201"},
        existing_data={
            "purchase_institutional_code": "41112200",
            "purchase_additional_code": "VC02",
        },
        year=2025,
    )

    assert result["purchase_additional_code"] is None
    assert resolved_factor is new_factor
    assert "primary_factor_id" not in result


@pytest.mark.asyncio
async def test_resolve_if_changed_kind_and_override_both_change(service):
    """When the request supplies both A and B, the new B is kept, not
    cleared by the kind-change side effect."""
    handler = _purchase_handler()
    new_factor = SimpleNamespace(id=91)
    service.factor_resolver.resolve = AsyncMock(return_value=new_factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {
            "purchase_institutional_code": "41112201",
            "purchase_additional_code": "VC99",
        },
        DataEntryTypeEnum.services,
        item_data={
            "purchase_institutional_code": "41112201",
            "purchase_additional_code": "VC99",
        },
        existing_data={
            "purchase_institutional_code": "41112200",
            "purchase_additional_code": "VC02",
        },
        year=2025,
    )

    assert result["purchase_additional_code"] == "VC99"
    assert resolved_factor is new_factor


@pytest.mark.asyncio
async def test_resolve_if_changed_override_changed_only_triggers_resolve(service):
    """Changing only the override code (kind untouched) must still
    re-resolve."""
    handler = _purchase_handler()
    factor = SimpleNamespace(id=61)
    service.factor_resolver.resolve = AsyncMock(return_value=factor)

    result, resolved_factor = await service.resolve_factor_if_changed(
        handler,
        {"purchase_additional_code": "ADD-NEW"},
        DataEntryTypeEnum.services,
        item_data={"purchase_additional_code": "ADD-NEW"},
        existing_data={
            "purchase_institutional_code": "F",
            "purchase_additional_code": "ADD-OLD",
        },
        year=2025,
    )

    assert resolved_factor is factor
    assert "primary_factor_id" not in result
    service.factor_resolver.resolve.assert_awaited_once()


# ── get_taxonomy ────────────────────────────────────────────


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
