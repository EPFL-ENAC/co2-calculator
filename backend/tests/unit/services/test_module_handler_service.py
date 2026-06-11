"""Tests for ModuleHandlerService."""

import csv
from pathlib import Path
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


# ── resolve_primary_factor_id ──────────────────────────────


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_with_subkind(service):
    handler = _make_handler()
    factor = SimpleNamespace(id=42)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    payload = {"kind": "ClassA", "subkind": "SubA1"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.scientific, year=2025
    )

    assert result["primary_factor_id"] == 42
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.scientific,
        kind="ClassA",
        subkind="SubA1",
        year=2025,
    )


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_no_subkind_field(service):
    """When handler has subkind_field=None (e.g. EnergyCombustion)."""
    handler = _make_handler(kind_field="name", subkind_field=None)
    factor = SimpleNamespace(id=7)
    service.factor_service.get_by_classification = AsyncMock(return_value=factor)

    payload = {"name": "natural_gas"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.energy_combustion, year=2025
    )

    assert result["primary_factor_id"] == 7
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.energy_combustion,
        kind="natural_gas",
        subkind=None,
        year=2025,
    )


@pytest.mark.asyncio
async def test_resolve_primary_factor_id_no_kind_field(service):
    """When handler has no kind_field, payload is returned unchanged."""
    handler = _make_handler(kind_field=None, subkind_field=None)

    payload = {"foo": "bar"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.scientific, year=2025
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
        handler,
        payload,
        DataEntryTypeEnum.scientific,
        year=2025,
        existing_data=existing,
    )

    assert result["primary_factor_id"] == 10
    service.factor_service.get_by_classification.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.scientific,
        kind="ClassA",
        subkind="SubB1",
        year=2025,
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
        year=2025,
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
        year=2025,
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
        year=2025,
    )

    assert "primary_factor_id" not in result


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


# ── purchase factor resolution (additional_code overrides) ──
#
# Contract under test:
# - purchase_additional_code is the primary lookup key when present:
#   the factor whose classification carries that additional_code wins,
#   regardless of institutional code.
# - unknown additional_code falls back to the institutional-code rule.
# - without additional_code, only factors WITHOUT an additional_code in
#   their classification are eligible (those rows are the implicit
#   averages); match on purchase_institutional_code.
# - several eligible rows for the same institutional code = ambiguous
#   factor data → raise, never pick silently.


def _purchase_handler():
    return SimpleNamespace(
        kind_field="purchase_institutional_code",
        subkind_field=None,
        kind_field_override="purchase_additional_code",
        kind_label_field=None,
        subkind_label_field=None,
        to_label=lambda x: x.capitalize(),
    )


def _purchase_factor(factor_id, institutional_code, additional_code=None):
    classification = {"purchase_institutional_code": institutional_code}
    if additional_code is not None:
        classification["purchase_additional_code"] = additional_code
    return SimpleNamespace(id=factor_id, classification=classification)


@pytest.mark.asyncio
async def test_purchase_additional_code_overrides_institutional_code(service):
    """A matching additional_code wins, even over an exact institutional match."""
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(
        return_value=[_purchase_factor(11, "10897564", additional_code="ADD-1")]
    )

    payload = {
        "purchase_institutional_code": "A",
        "purchase_additional_code": "ADD-1",
    }
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result["primary_factor_id"] == 11
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_additional_code="ADD-1",
    )


@pytest.mark.asyncio
async def test_purchase_unknown_additional_code_falls_back_to_institutional(service):
    """Unknown additional_code → institutional-code rule applies instead."""
    handler = _purchase_handler()
    fallback_factor = _purchase_factor(22, "B")
    service.factor_service.get_factors = AsyncMock(side_effect=[[], [fallback_factor]])

    payload = {
        "purchase_institutional_code": "B",
        "purchase_additional_code": "TYPO",
    }
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result["primary_factor_id"] == 22
    assert service.factor_service.get_factors.await_count == 2
    service.factor_service.get_factors.assert_awaited_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_institutional_code="B",
    )


@pytest.mark.asyncio
async def test_purchase_no_additional_code_uses_average_row_only(service):
    """Without additional_code, factors carrying one are excluded from fallback."""
    handler = _purchase_handler()
    specific = _purchase_factor(31, "C", additional_code="ADD-9")
    average = _purchase_factor(32, "C")
    service.factor_service.get_factors = AsyncMock(return_value=[specific, average])

    payload = {"purchase_institutional_code": "C"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result["primary_factor_id"] == 32
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_institutional_code="C",
    )


@pytest.mark.asyncio
async def test_purchase_multiple_average_rows_is_ambiguous(service):
    """Two no-additional-code rows for one institutional code is bad factor data."""
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(
        return_value=[_purchase_factor(41, "D"), _purchase_factor(42, "D")]
    )

    payload = {"purchase_institutional_code": "D"}
    with pytest.raises(ValueError, match="purchase_institutional_code"):
        await service.resolve_primary_factor_id(
            handler, payload, DataEntryTypeEnum.services, year=2025
        )


@pytest.mark.asyncio
async def test_purchase_no_match_at_all_sets_none(service):
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(return_value=[])

    payload = {"purchase_institutional_code": "ZZZ"}
    result = await service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result["primary_factor_id"] is None


@pytest.mark.asyncio
async def test_purchase_additional_code_from_existing_data(service):
    """On update, the stored additional_code still drives the lookup."""
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(
        return_value=[_purchase_factor(51, "E", additional_code="ADD-5")]
    )

    payload = {"total_spent_amount": 100.0}
    existing = {
        "purchase_institutional_code": "E",
        "purchase_additional_code": "ADD-5",
    }
    result = await service.resolve_primary_factor_id(
        handler,
        payload,
        DataEntryTypeEnum.services,
        year=2025,
        existing_data=existing,
    )

    assert result["primary_factor_id"] == 51
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_additional_code="ADD-5",
    )


# ── resolve_primary_factor_if_changed with additional_code ──


@pytest.mark.asyncio
async def test_purchase_if_changed_additional_code_change_re_resolves(service):
    """Changing only purchase_additional_code must trigger re-resolution."""
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(
        return_value=[_purchase_factor(61, "F", additional_code="ADD-NEW")]
    )

    result = await service.resolve_primary_factor_if_changed(
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

    assert result["primary_factor_id"] == 61


@pytest.mark.asyncio
async def test_purchase_if_changed_additional_code_cleared_falls_back(service):
    """Clearing additional_code re-resolves via the institutional-code rule."""
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock(
        return_value=[_purchase_factor(72, "G")]
    )

    result = await service.resolve_primary_factor_if_changed(
        handler,
        {"purchase_additional_code": None},
        DataEntryTypeEnum.services,
        item_data={"purchase_additional_code": None},
        existing_data={
            "purchase_institutional_code": "G",
            "purchase_additional_code": "ADD-OLD",
        },
        year=2025,
    )

    assert result["primary_factor_id"] == 72
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_institutional_code="G",
    )


@pytest.mark.asyncio
async def test_purchase_if_changed_kind_change_clears_stale_override(service):
    """Changing A without sending B must clear the stored B, not reuse it.

    Regression: with A=41112200/B=VC02 stored, updating only A to 41112201
    left VC02 in the merged data, so the override lookup kept resolving the
    OLD code's factor and the A change was silently ignored.
    """
    handler = _purchase_handler()
    new_factor = _purchase_factor(81, "41112201")
    service.factor_service.get_factors = AsyncMock(return_value=[new_factor])

    result = await service.resolve_primary_factor_if_changed(
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
    assert result["primary_factor_id"] == 81
    assert "" not in result
    # Resolution went through the new institutional code, not the stale B.
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_institutional_code="41112201",
    )


@pytest.mark.asyncio
async def test_purchase_if_changed_kind_and_override_both_change(service):
    """When the request supplies both A and B, the new B is used, not cleared."""
    handler = _purchase_handler()
    new_factor = _purchase_factor(91, "41112201", additional_code="VC99")
    service.factor_service.get_factors = AsyncMock(return_value=[new_factor])

    result = await service.resolve_primary_factor_if_changed(
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
    assert result["primary_factor_id"] == 91
    service.factor_service.get_factors.assert_awaited_once_with(
        data_entry_type=DataEntryTypeEnum.services,
        year=2025,
        purchase_additional_code="VC99",
    )


@pytest.mark.asyncio
async def test_purchase_if_changed_nothing_changed_no_lookup(service):
    handler = _purchase_handler()
    service.factor_service.get_factors = AsyncMock()

    result = await service.resolve_primary_factor_if_changed(
        handler,
        {"note": "updated"},
        DataEntryTypeEnum.services,
        item_data={"note": "updated"},
        existing_data={
            "purchase_institutional_code": "H",
            "purchase_additional_code": "ADD-1",
        },
        year=2025,
    )

    assert "primary_factor_id" not in result
    service.factor_service.get_factors.assert_not_awaited()


# ── resolution truth table (A=institutional, B=additional) ──
#
# A = purchase_institutional_code (kind_field, mandatory on entries)
# B = purchase_additional_code (kind_field_override, optional but always
#     right when present — it is the discrete, authoritative key)
#
# ┌──────────────────┬──────────────────────────────────────────────────┐
# │       data       │                      result                      │
# ├──────────────────┼──────────────────────────────────────────────────┤
# │ A=1, B=6         │ 1                                                │
# │ A=1, B=4         │ 2                                                │
# │ A=1, B=None      │ 3 (average row: no B in its classification)      │
# │ A=4, B=644       │ 4                                                │
# │ A=4, B=None      │ 5                                                │
# │ A=None, B=3      │ ValueError (A mandatory, even when B matches)    │
# │ A=3, B=3         │ 7 (B matches 6+7; the entry's A disambiguates)   │
# │ A=None, B=None   │ ValueError (A mandatory)                         │
# │ A=1, B=unknown   │ 3 (typo'd B falls back to A's average row)       │
# │ A=unknown, B=None│ None (no factor; require_factor_to_match=False)  │
# │ A=999, B=3       │ ValueError (B ambiguous, no factor agrees on A)  │
# │ A=X, 2 avg rows  │ ValueError (ambiguous factor data, never guess)  │
# │ A=5, B=None      │ 9 (single row for A wins even though it has a B) │
# └──────────────────┴──────────────────────────────────────────────────┘
#
# The single-row rule (last line) reflects real factor data: most
# institutional codes have exactly one row and it carries an additional
# code (e.g. 23152900 → FA0).  The average-row exclusion only applies
# when SEVERAL rows share the institutional code.
#
# Factor pool below includes rows that factor validation should reject
# (ids 6 and 8 have no institutional code — see
# PurchaseCommonFactorCreate.validate_institutional_code) so resolution
# stays correct even against bad data already in base.

_TRUTH_TABLE_FACTORS = [
    _purchase_factor(1, "1", additional_code="6"),
    _purchase_factor(2, "1", additional_code="4"),
    _purchase_factor(3, "1"),
    _purchase_factor(4, "4", additional_code="644"),
    _purchase_factor(5, "4"),
    SimpleNamespace(id=6, classification={"purchase_additional_code": "3"}),
    _purchase_factor(7, "3", additional_code="3"),
    SimpleNamespace(id=8, classification={}),
    # Sole row for A=5 — carries a B but is still the authoritative match.
    _purchase_factor(9, "5", additional_code="99"),
]


@pytest.fixture
def truth_table_service(service):
    async def fake_get_factors(data_entry_type, year=None, **classification):
        return [
            f
            for f in _TRUTH_TABLE_FACTORS
            if all(f.classification.get(k) == v for k, v in classification.items())
        ]

    service.factor_service.get_factors = AsyncMock(side_effect=fake_get_factors)
    return service


@pytest.mark.parametrize(
    ("institutional", "additional", "expected_id"),
    [
        ("1", "6", 1),
        ("1", "4", 2),
        ("1", None, 3),
        ("4", "644", 4),
        ("4", None, 5),
        # B=3 matches factors 6 and 7; the entry's A=3 disambiguates to 7.
        ("3", "3", 7),
        # Unknown B falls back to A's average row.
        ("1", "NOPE", 3),
        # Unknown A without B → no factor (require_factor_to_match=False).
        ("999", None, None),
        # Single row for A wins even though it carries a B (real-data shape).
        ("5", None, 9),
    ],
)
@pytest.mark.asyncio
async def test_purchase_resolution_truth_table(
    truth_table_service, institutional, additional, expected_id
):
    handler = _purchase_handler()
    payload = {
        "purchase_institutional_code": institutional,
        "purchase_additional_code": additional,
    }
    result = await truth_table_service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    assert result["primary_factor_id"] == expected_id


@pytest.mark.parametrize(
    ("institutional", "additional"),
    [
        (None, "3"),  # A is mandatory even when B alone would match
        (None, None),
    ],
)
@pytest.mark.asyncio
async def test_purchase_resolution_missing_institutional_code_fails(
    truth_table_service, institutional, additional
):
    handler = _purchase_handler()
    payload = {
        "purchase_institutional_code": institutional,
        "purchase_additional_code": additional,
    }
    with pytest.raises(ValueError, match="purchase_institutional_code is required"):
        await truth_table_service.resolve_primary_factor_id(
            handler, payload, DataEntryTypeEnum.services, year=2025
        )


@pytest.mark.asyncio
async def test_purchase_resolution_override_ambiguous_fails(truth_table_service):
    """B matches several factors and the entry's A agrees with none → fail."""
    handler = _purchase_handler()
    payload = {
        "purchase_institutional_code": "999",
        "purchase_additional_code": "3",
    }
    with pytest.raises(ValueError, match="Ambiguous factor data"):
        await truth_table_service.resolve_primary_factor_id(
            handler, payload, DataEntryTypeEnum.services, year=2025
        )


# ── resolution against the committed factors smoke CSV ──────
#
# Uses tests/fixtures/csv/purchases_common_factors_smoke.csv as the factor
# pool, with a fake get_factors that filters on classification equality the
# way FactorRepository.get_factors does.  Pins that the fixture rows support
# the override/average rules (51100000 exists both with additional_code LA05
# and as a code-less average row).

_FACTORS_SMOKE_CSV = (
    Path(__file__).parents[2]
    / "fixtures"
    / "csv"
    / "purchases_common_factors_smoke.csv"
)


def _load_smoke_factors():
    factors = []
    with _FACTORS_SMOKE_CSV.open() as fh:
        for i, row in enumerate(csv.DictReader(fh), start=1):
            classification = {
                "purchase_institutional_code": row["purchase_institutional_code"],
                "currency": row["currency"],
            }
            if row["purchase_additional_code"]:
                classification["purchase_additional_code"] = row[
                    "purchase_additional_code"
                ]
            factors.append(
                SimpleNamespace(
                    id=i,
                    data_entry_type=DataEntryTypeEnum[row["purchase_category"]],
                    classification=classification,
                    values={
                        "ef_kg_co2eq_per_currency": float(
                            row["ef_kg_co2eq_per_currency"]
                        )
                    },
                )
            )
    return factors


@pytest.fixture
def smoke_service(service):
    factors = _load_smoke_factors()

    async def fake_get_factors(data_entry_type, year=None, **classification):
        return [
            f
            for f in factors
            if f.data_entry_type == data_entry_type
            and all(f.classification.get(k) == v for k, v in classification.items())
        ]

    service.factor_service.get_factors = AsyncMock(side_effect=fake_get_factors)
    return service


@pytest.mark.asyncio
async def test_smoke_csv_additional_code_wins(smoke_service):
    """LA05 row (ef=0.41) wins over the 51100000 average row (ef=0.455)."""
    handler = _purchase_handler()
    payload = {
        "purchase_institutional_code": "51100000",
        "purchase_additional_code": "LA05",
    }
    result = await smoke_service.resolve_primary_factor_id(
        handler,
        payload,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        year=2025,
    )

    factors = _load_smoke_factors()
    chosen = next(f for f in factors if f.id == result["primary_factor_id"])
    assert chosen.classification["purchase_additional_code"] == "LA05"
    assert chosen.values["ef_kg_co2eq_per_currency"] == 0.41


@pytest.mark.asyncio
async def test_smoke_csv_no_additional_code_picks_average_row(smoke_service):
    """Without additional_code, 51100000 resolves to the code-less average row."""
    handler = _purchase_handler()
    payload = {"purchase_institutional_code": "51100000"}
    result = await smoke_service.resolve_primary_factor_id(
        handler,
        payload,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        year=2025,
    )

    factors = _load_smoke_factors()
    chosen = next(f for f in factors if f.id == result["primary_factor_id"])
    assert "purchase_additional_code" not in chosen.classification
    assert chosen.values["ef_kg_co2eq_per_currency"] == 0.455


@pytest.mark.asyncio
async def test_smoke_csv_unknown_additional_code_falls_back(smoke_service):
    """A typo'd additional_code still resolves via the institutional average."""
    handler = _purchase_handler()
    payload = {
        "purchase_institutional_code": "51100000",
        "purchase_additional_code": "NOPE",
    }
    result = await smoke_service.resolve_primary_factor_id(
        handler,
        payload,
        DataEntryTypeEnum.biological_chemical_gaseous_product,
        year=2025,
    )

    factors = _load_smoke_factors()
    chosen = next(f for f in factors if f.id == result["primary_factor_id"])
    assert chosen.values["ef_kg_co2eq_per_currency"] == 0.455


@pytest.mark.asyncio
async def test_smoke_csv_single_row_with_code_is_authoritative(smoke_service):
    """A code whose ONLY row carries an additional_code still matches it.

    This is the common shape in real factor data (e.g. 23152900 →  FA0):
    most institutional codes have exactly one row, and that row carries an
    additional code.  The average-row exclusion only kicks in when several
    rows share the institutional code.
    """
    handler = _purchase_handler()
    # 91111500 only exists with additional_code AA66.
    payload = {"purchase_institutional_code": "91111500"}
    result = await smoke_service.resolve_primary_factor_id(
        handler, payload, DataEntryTypeEnum.services, year=2025
    )

    factors = _load_smoke_factors()
    chosen = next(f for f in factors if f.id == result["primary_factor_id"])
    assert chosen.classification["purchase_additional_code"] == "AA66"
