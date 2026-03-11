"""Tests for seed_helper utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.seed import seed_helper


def test_normalize_kind_trims_and_lowercases():
    assert seed_helper.normalize_kind("  KiNd  ") == "kind"


def test_is_in_factors_map_requires_subkind():
    factors_map = {
        "1:kind:sub": Factor(
            emission_type_id=1,
            data_entry_type_id=DataEntryTypeEnum.scientific,
            classification={"equipment_class": "Kind", "sub_class": "Sub"},
            values={"ef_kg_co2eq_per_unit": 1.0},
        ),
    }

    assert (
        seed_helper.is_in_factors_map(
            kind="equipment_class",
            subkind=None,
            factors_map=factors_map,
            require_subkind=True,
        )
        is False
    )


def test_is_in_factors_map_with_subkind_match():
    factors_map = {
        "1:kind:sub": Factor(
            emission_type_id=1,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            classification={"equipment_class": "Kind", "sub_class": "Sub"},
            values={"ef_kg_co2eq_per_unit": 1.0},
        ),
    }

    assert (
        seed_helper.is_in_factors_map(
            kind="Kind",
            subkind="Sub",
            factors_map=factors_map,
            require_subkind=True,
        )
        is True
    )


def test_is_in_factors_map_kind_only_match():
    factors_map = {
        "1:kind": Factor(
            emission_type_id=1,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            classification={"equipment_class": "Kind"},
            values={"ef_kg_co2eq_per_unit": 1.0},
        ),
    }

    assert (
        seed_helper.is_in_factors_map(
            kind="KIND",
            subkind=None,
            factors_map=factors_map,
        )
        is True
    )


def test_lookup_factor_no_match():
    factors_map = {
        "1:kind:sub": Factor(
            emission_type_id=1,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            classification={"equipment_class": "Kind", "sub_class": "Sub"},
            values={"ef_kg_co2eq_per_unit": 1.0},
        ),
    }

    assert (
        seed_helper.lookup_factor(kind="other", subkind=None, factors_map=factors_map)
        is None
    )


def test_lookup_factor_single_match():
    factor = Factor(
        emission_type_id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": "Kind", "sub_class": "Sub"},
        values={"ef_kg_co2eq_per_unit": 1.0},
    )
    factors_map = {
        "1:kind:sub": factor,
    }

    result = seed_helper.lookup_factor(
        kind="Kind", subkind="Sub", factors_map=factors_map
    )

    assert result is factor


def test_lookup_factor_ambiguous_match_logs_warning(caplog):
    factor_one = Factor(
        emission_type_id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": "Kind", "sub_class": "Sub"},
        values={"ef_kg_co2eq_per_unit": 1.0},
    )
    factor_two = Factor(
        emission_type_id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": "Kind", "sub_class": "Sub"},
        values={"ef_kg_co2eq_per_unit": 1.0},
    )
    factors_map = {
        "1:kind:sub": factor_one,
        "2:kind:sub": factor_two,
    }

    with caplog.at_level("WARNING"):
        result = seed_helper.lookup_factor(
            kind="Kind", subkind="Sub", factors_map=factors_map
        )

    assert result in (factor_one, factor_two)
    assert "Ambiguous factor lookup" in caplog.text


@pytest.mark.asyncio
async def test_load_factors_map_builds_keys(monkeypatch):
    factor_one = Factor(
        emission_type_id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": "Kind", "sub_class": "Sub"},
        values={"ef_kg_co2eq_per_unit": 1.0},
    )
    factor_two = Factor(
        emission_type_id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        classification={"equipment_class": "Kind"},
        values={"ef_kg_co2eq_per_unit": 1.0},
    )

    service = MagicMock()
    service.list_by_data_entry_type = AsyncMock(return_value=[factor_one, factor_two])

    monkeypatch.setattr(seed_helper, "FactorService", MagicMock(return_value=service))

    factors_map = await seed_helper.load_factors_map(
        session=MagicMock(), data_entry_type=DataEntryTypeEnum.scientific
    )

    assert f"{DataEntryTypeEnum.scientific.value}:kind:sub" in factors_map
    assert f"{DataEntryTypeEnum.scientific.value}:kind" in factors_map
