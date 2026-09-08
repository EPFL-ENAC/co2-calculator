"""Unit tests for FactorResolver (plan 1661).

Ports the kind/subkind and override-key-first lookup case matrix from
``tests/unit/workflows/test_emission_recalculation.py`` (the in-memory
rematch helpers being promoted out of the recalc workflow), exercised
here through the public ``FactorResolver.resolve`` / ``factors_by_id``
API instead of the private static methods it used to live on.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
from app.services.factor_resolver import FactorResolver, unresolved_reason


def _factor(
    fid: int, det: DataEntryTypeEnum, year: int, classification: dict
) -> Factor:
    return Factor(
        id=fid,
        data_entry_type_id=det.value,
        emission_type_id=1,
        classification=classification,
        values={"kw": 1.0},
        year=year,
    )


def _patch_factors(factors: list[Factor]):
    return patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=AsyncMock(return_value=factors),
    )


# it/scientific/other share EquipmentModuleHandler: kind_field + subkind_field,
# no kind_field_override — exercises the plain kind→subkind→kind-only chain.
EQUIPMENT = DataEntryTypeEnum.it
HANDLER = BaseModuleHandler.get_by_type(EQUIPMENT)

# consumable_accessories uses PurchaseModuleHandler: kind_field_override is
# set, so its lookup goes through the override-key-first path instead.
OVERRIDE_DET = DataEntryTypeEnum.consumable_accessories
OVERRIDE_HANDLER = BaseModuleHandler.get_by_type(OVERRIDE_DET)
assert OVERRIDE_HANDLER.kind_field is not None
assert OVERRIDE_HANDLER.kind_field_override is not None
_KIND = OVERRIDE_HANDLER.kind_field
_OVERRIDE = OVERRIDE_HANDLER.kind_field_override


# ===================== kind/subkind (non-override) =====================


@pytest.mark.asyncio
async def test_exact_kind_subkind_match():
    factors = [
        _factor(
            1,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
        _factor(2, EQUIPMENT, 2025, {HANDLER.kind_field: "Mill"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            HANDLER,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
            EQUIPMENT,
            2025,
        )
    assert got is not None and got.id == 1


@pytest.mark.asyncio
async def test_kind_only_fallback_when_subkind_misses():
    """No (Mill, Unknown) row exists, but (Mill, None) does — fall back."""
    factors = [
        _factor(
            1,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
        _factor(2, EQUIPMENT, 2025, {HANDLER.kind_field: "Mill"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            HANDLER,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "Unknown"},
            EQUIPMENT,
            2025,
        )
    assert got is not None and got.id == 2


@pytest.mark.asyncio
async def test_miss_returns_none():
    factors = [
        _factor(
            1,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            HANDLER,
            {HANDLER.kind_field: "Absent", HANDLER.subkind_field: "CNC"},
            EQUIPMENT,
            2025,
        )
    assert got is None


@pytest.mark.asyncio
async def test_duplicate_kind_subkind_first_row_wins():
    """Setdefault semantics: two factors share (kind, subkind) → first wins."""
    factors = [
        _factor(
            1,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
        _factor(
            2,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            HANDLER,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
            EQUIPMENT,
            2025,
        )
    assert got is not None and got.id == 1


@pytest.mark.asyncio
async def test_kind_field_none_returns_none():
    """Handlers without kind_field never rematch — repo isn't even queried."""
    stub_handler = SimpleNamespace(kind_field=None)
    repo_mock = AsyncMock(return_value=[])
    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=repo_mock,
    ):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(stub_handler, {}, EQUIPMENT, 2025)
    assert got is None
    repo_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_memoized_single_bulk_select():
    factors = [
        _factor(
            1,
            EQUIPMENT,
            2025,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
        ),
    ]
    repo_mock = AsyncMock(return_value=factors)
    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=repo_mock,
    ):
        resolver = FactorResolver(session=AsyncMock())
        data = {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"}
        await resolver.resolve(HANDLER, data, EQUIPMENT, 2025)
        await resolver.resolve(HANDLER, data, EQUIPMENT, 2025)
    assert repo_mock.await_count == 1


@pytest.mark.asyncio
async def test_factors_by_id_returns_bulk_map():
    factors = [
        _factor(1, EQUIPMENT, 2025, {HANDLER.kind_field: "Mill"}),
        _factor(2, EQUIPMENT, 2025, {HANDLER.kind_field: "Lathe"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        by_id = await resolver.factors_by_id(EQUIPMENT, 2025)
    assert set(by_id) == {1, 2}
    assert by_id[1].id == 1


# ================= override-key-first (purchase-style) =================


@pytest.mark.asyncio
async def test_override_single_match_wins():
    """Override code present and matches exactly one factor → return it."""
    factors = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
        _factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER,
            {_KIND: "FOOD", _OVERRIDE: "FR-001"},
            OVERRIDE_DET,
            2025,
        )
    assert got is not None and got.id == 10


@pytest.mark.asyncio
async def test_override_multiple_disambiguated_by_kind():
    """Same code on two different kinds → entry's kind narrows to one."""
    factors = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
        _factor(11, OVERRIDE_DET, 2025, {_KIND: "TRAVEL", _OVERRIDE: "FR-001"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER,
            {_KIND: "FOOD", _OVERRIDE: "FR-001"},
            OVERRIDE_DET,
            2025,
        )
    assert got is not None and got.id == 10


@pytest.mark.asyncio
async def test_override_ambiguous_raises_value_error():
    """Two factors share the same code AND the same kind → ValueError."""
    factors = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
        _factor(11, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        with pytest.raises(ValueError, match="Ambiguous"):
            await resolver.resolve(
                OVERRIDE_HANDLER,
                {_KIND: "FOOD", _OVERRIDE: "FR-001"},
                OVERRIDE_DET,
                2025,
            )


@pytest.mark.asyncio
async def test_override_code_miss_falls_back_to_kind_average():
    """Code set on entry but absent from factors → fall through to the
    kind-only average row.
    """
    factors = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
        _factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER,
            {_KIND: "FOOD", _OVERRIDE: "XX-999"},
            OVERRIDE_DET,
            2025,
        )
    assert got is not None and got.id == 20


@pytest.mark.asyncio
async def test_kind_fallback_requires_single_average_row():
    """No override code on the entry: a single average row for the kind
    wins; two average rows sharing a kind are ambiguous.
    """
    single_average = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
        _factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"}),
    ]
    with _patch_factors(single_average):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER, {_KIND: "FOOD"}, OVERRIDE_DET, 2025
        )
    assert got is not None and got.id == 20

    two_averages = [
        _factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"}),
        _factor(21, OVERRIDE_DET, 2025, {_KIND: "FOOD"}),
    ]
    with _patch_factors(two_averages):
        resolver = FactorResolver(session=AsyncMock())
        with pytest.raises(ValueError, match="Ambiguous"):
            await resolver.resolve(
                OVERRIDE_HANDLER, {_KIND: "FOOD"}, OVERRIDE_DET, 2025
            )


@pytest.mark.asyncio
async def test_override_no_code_single_factor_that_carries_code():
    """Single factor row for the kind even though it has an override code is
    authoritative — mirrors _resolve_with_kind_override's 'len(factors)==1'
    rule (the averages-only filter alone would find zero rows and raise).
    """
    factors = [
        _factor(10, OVERRIDE_DET, 2025, {_KIND: "FOOD", _OVERRIDE: "FR-001"}),
    ]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER, {_KIND: "FOOD"}, OVERRIDE_DET, 2025
        )
    assert got is not None and got.id == 10


@pytest.mark.asyncio
async def test_override_missing_kind_returns_none():
    factors = [_factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"})]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(OVERRIDE_HANDLER, {}, OVERRIDE_DET, 2025)
    assert got is None


@pytest.mark.asyncio
async def test_override_empty_kind_returns_none():
    factors = [_factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"})]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(OVERRIDE_HANDLER, {_KIND: ""}, OVERRIDE_DET, 2025)
    assert got is None


@pytest.mark.asyncio
async def test_override_kind_miss_returns_none():
    """Kind not present in the current factor set at all → strict miss."""
    factors = [_factor(20, OVERRIDE_DET, 2025, {_KIND: "FOOD"})]
    with _patch_factors(factors):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            OVERRIDE_HANDLER, {_KIND: "UNKNOWN"}, OVERRIDE_DET, 2025
        )
    assert got is None


@pytest.mark.asyncio
async def test_kind_value_missing_short_circuits_without_bulk_load():
    """A handler with a kind_field but no kind value on the entry resolves
    to None BEFORE the bulk factor load — callers need no gate of their
    own (Strategy-B entries derive the kind at compute time, so it is
    absent from entry.data on every list/enrichment path).
    """
    repo_mock = AsyncMock()
    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=repo_mock,
    ):
        resolver = FactorResolver(session=AsyncMock())
        for data in ({}, {HANDLER.kind_field: ""}, {HANDLER.kind_field: None}):
            got = await resolver.resolve(HANDLER, data, EQUIPMENT, 2025)
            assert got is None
    repo_mock.assert_not_awaited()


# ===================== entry-time check: unresolved_reason (#2591) =============

PROCESS = DataEntryTypeEnum.process_emissions
PROCESS_HANDLER = BaseModuleHandler.get_by_type(PROCESS)
ENERGY = DataEntryTypeEnum.energy_combustion
ENERGY_HANDLER = BaseModuleHandler.get_by_type(ENERGY)

_PROCESS_FACTORS = [
    _factor(1, PROCESS, 2025, {"category": "HFCs", "subcategory": "R134a"}),
    _factor(2, PROCESS, 2025, {"category": "HFCs", "subcategory": "R32"}),
    _factor(3, PROCESS, 2025, {"category": "CO2", "subcategory": None}),
]


def test_subcategory_required_when_every_factor_of_the_category_has_one():
    reason = unresolved_reason(PROCESS_HANDLER, {"category": "HFCs"}, _PROCESS_FACTORS)
    assert (
        reason == "subcategory is required for category='HFCs': one of ['R134a', 'R32']"
    )


def test_unknown_subcategory_named_with_the_accepted_ones():
    reason = unresolved_reason(
        PROCESS_HANDLER, {"category": "HFCs", "subcategory": "R999"}, _PROCESS_FACTORS
    )
    assert (
        reason
        == "Unknown subcategory='R999' for category='HFCs': one of ['R134a', 'R32']"
    )


@pytest.mark.parametrize(
    "data",
    [
        {"category": "HFCs", "subcategory": "R32"},
        {"category": "CO2"},
        {"category": "CO2", "subcategory": ""},
        # unknown category stays a plain miss: not this check's job
        {"category": "Unobtainium"},
        {},
    ],
)
def test_resolvable_or_out_of_scope_rows_pass(data: dict):
    assert unresolved_reason(PROCESS_HANDLER, data, _PROCESS_FACTORS) is None


def test_energy_combustion_unit_must_equal_the_factor_unit():
    factors = [_factor(9, ENERGY, 2025, {"name": "pellets", "unit": "kg"})]
    assert (
        unresolved_reason(ENERGY_HANDLER, {"name": "pellets", "unit": "kWh"}, factors)
        == "unit='kWh' does not match the factor's unit='kg' for name='pellets'"
    )
    assert (
        unresolved_reason(ENERGY_HANDLER, {"name": "pellets", "unit": "kg"}, factors)
        is None
    )


@pytest.mark.asyncio
async def test_resolver_method_uses_the_year_set():
    with _patch_factors(_PROCESS_FACTORS):
        reason = await FactorResolver(session=AsyncMock()).unresolved_reason(
            PROCESS_HANDLER, {"category": "HFCs"}, PROCESS, 2025
        )
    assert reason is not None and reason.startswith("subcategory is required")
