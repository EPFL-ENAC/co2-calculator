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

from app.core.factor_taxonomy_cache import taxonomy_cache
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
from app.services.module_handler_service import ModuleHandlerService


@pytest.fixture(autouse=True)
def _clear_taxonomy_cache():
    """The taxonomy cache is a process-wide singleton (#2258) — reset it
    around every test so one test's cached tree can't leak into another's.
    """
    taxonomy_cache.clear()
    yield
    taxonomy_cache.clear()


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
        taxonomy_meta_fields=(),
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
        taxonomy_meta_fields=(),
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


# ── get_taxonomy caching (#2258) ────────────────────────────


@pytest.mark.asyncio
async def test_get_taxonomy_second_call_served_from_cache(service):
    """A second call for the same (data_entry_type, year) must not re-query
    factors — the whole point of caching this expensive tree build (#2258).
    """
    handler = _make_handler()
    factors = [Factor(emission_type_id=1, classification={"kind": "A"})]
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)

    first = await service.get_taxonomy(handler, DataEntryTypeEnum.scientific, year=2025)
    second = await service.get_taxonomy(
        handler, DataEntryTypeEnum.scientific, year=2025
    )

    service.factor_service.list_by_data_entry_type.assert_awaited_once()
    assert second is first


@pytest.mark.asyncio
async def test_get_taxonomy_strips_coefficients_from_the_tree(service):
    """#2391 decision 3: bulk taxonomy payloads must never carry emission
    coefficients -- the only client consumer of factor values is the narrow
    GET factors/{det}/classes/{kind}/values prefill endpoint, not this tree.
    """
    handler = _make_handler()
    factors = [
        Factor(
            emission_type_id=1,
            classification={"kind": "A", "subkind": "A1"},
            values={
                "ef_kg_co2eq_per_kwh": 0.42,
                "active_power_w": 150,
                "standby_power_w": 5,
            },
        )
    ]
    service.factor_service.list_by_data_entry_type = AsyncMock(return_value=factors)

    result = await service.get_taxonomy(
        handler, DataEntryTypeEnum.scientific, year=2025
    )

    dumped = result.model_dump_json()
    for forbidden in (
        "values",
        "classification",
        "ef_kg_co2eq_per_kwh",
        "active_power_w",
        "standby_power_w",
    ):
        assert forbidden not in dumped


# ── get_taxonomy display metadata (#2391 decision 1) ────────


_RF_COMMON_FACTORS = [
    Factor(
        emission_type_id=1,
        classification={
            "researchfacility_id": "1902",
            "researchfacility_name": "SCITAS-GE",
        },
        values={"use_unit": "CHF", "total_use": 2195625.795, "kg_co2eq_sum": 42.0},
    )
]

# Deliberately two housing types with *different* units: meta copied onto the
# kind node only (or onto every subkind from the first row) would still label
# both "housings" and the bug would pass unnoticed.
_RF_ANIMAL_FACTORS = [
    Factor(
        emission_type_id=1,
        classification={
            "researchfacility_id": "1321",
            "researchfacility_name": "CPG",
            "researchfacility_type": "rodent",
        },
        values={"use_unit": "housings", "total_use": 3917},
    ),
    Factor(
        emission_type_id=1,
        classification={
            "researchfacility_id": "1321",
            "researchfacility_name": "CPG",
            "researchfacility_type": "fish",
        },
        values={"use_unit": "tanks", "total_use": 602},
    ),
]


@pytest.mark.asyncio
async def test_taxonomy_carries_declared_meta_on_a_flat_tree(service):
    """research_facilities has no subkind: one level of facility nodes, each
    labelled by acronym and carrying its own metric unit.
    """
    det = DataEntryTypeEnum.research_facilities
    handler = BaseModuleHandler.get_by_type(det)
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=_RF_COMMON_FACTORS
    )

    taxonomy = await service.get_taxonomy(handler, det, year=2025)

    (facility,) = taxonomy.children
    assert (facility.name, facility.label) == ("1902", "SCITAS-GE")
    assert facility.children is None
    assert facility.meta == {"use_unit": "CHF"}


@pytest.mark.asyncio
async def test_taxonomy_meta_follows_the_subkind_row_not_the_kind(service):
    """animal_facilities keys factors by (facility, housing type), so the unit
    is a per-subkind value — the planner reads it off the child node.
    """
    det = DataEntryTypeEnum.animal_facilities
    handler = BaseModuleHandler.get_by_type(det)
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=_RF_ANIMAL_FACTORS
    )

    taxonomy = await service.get_taxonomy(handler, det, year=2025)

    (facility,) = taxonomy.children
    assert (facility.name, facility.label) == ("1321", "CPG")
    assert {(c.name, c.meta["use_unit"]) for c in facility.children} == {
        ("rodent", "housings"),
        ("fish", "tanks"),
    }


@pytest.mark.asyncio
async def test_meta_only_carries_whitelisted_fields(service):
    """`total_use`/`kg_co2eq_sum` are coefficients, not display metadata — a
    generic values passthrough is exactly what #2396 removed.
    """
    det = DataEntryTypeEnum.research_facilities
    handler = BaseModuleHandler.get_by_type(det)
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=_RF_COMMON_FACTORS
    )

    taxonomy = await service.get_taxonomy(handler, det, year=2025)

    dumped = taxonomy.model_dump_json()
    for forbidden in ("total_use", "kg_co2eq_sum", "values", "classification"):
        assert forbidden not in dumped


@pytest.mark.asyncio
async def test_no_meta_key_for_a_module_that_declares_none(service):
    """Unaffected modules' payloads must not grow — `meta` is None and
    `response_model_exclude_none` drops it (asserted on the route in
    tests/unit/v1/test_taxonomies_batch_endpoint.py).
    """
    det = DataEntryTypeEnum.scientific
    handler = BaseModuleHandler.get_by_type(det)
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=[
            Factor(
                emission_type_id=1,
                classification={"equipment_class": "Centrifuge", "sub_class": "Ultra"},
                values={"active_power_w": 150},
            )
        ]
    )

    taxonomy = await service.get_taxonomy(handler, det, year=2025)

    (kind,) = taxonomy.children
    assert kind.meta is None
    assert all(child.meta is None for child in kind.children)


@pytest.mark.asyncio
async def test_get_taxonomy_different_year_is_not_cached_together(service):
    """Cache key includes year — a different year must still hit the DB."""
    handler = _make_handler()
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=[Factor(emission_type_id=1, classification={"kind": "A"})]
    )

    await service.get_taxonomy(handler, DataEntryTypeEnum.scientific, year=2025)
    await service.get_taxonomy(handler, DataEntryTypeEnum.scientific, year=2026)

    assert service.factor_service.list_by_data_entry_type.await_count == 2


@pytest.mark.asyncio
async def test_get_taxonomy_cache_cleared_forces_requery(service):
    """Simulates what a factor write does (``FactorRepository`` calls
    ``taxonomy_cache.clear()`` on every write, see test_factor_repo.py):
    once cleared, the next call must hit the DB again rather than serve the
    now-stale cached tree.
    """
    handler = _make_handler()
    service.factor_service.list_by_data_entry_type = AsyncMock(
        return_value=[Factor(emission_type_id=1, classification={"kind": "A"})]
    )

    await service.get_taxonomy(handler, DataEntryTypeEnum.scientific, year=2025)
    taxonomy_cache.clear()
    await service.get_taxonomy(handler, DataEntryTypeEnum.scientific, year=2025)

    assert service.factor_service.list_by_data_entry_type.await_count == 2
