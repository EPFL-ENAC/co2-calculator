"""Tests for seed_helper utilities."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.seed import seed_helper


def test_normalize_kind_trims_and_lowercases():
    assert seed_helper.normalize_kind("  KiNd  ") == "kind"


def test_is_in_factors_map_requires_subkind():
    factors_map = {
        "1:kind:sub": SimpleNamespace(id=1),
    }

    assert (
        seed_helper.is_in_factors_map(
            kind="kind",
            subkind=None,
            factors_map=factors_map,
            require_subkind=True,
        )
        is False
    )


def test_is_in_factors_map_with_subkind_match():
    factors_map = {
        "1:kind:sub": SimpleNamespace(id=1),
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
        "1:kind": SimpleNamespace(id=1),
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
        "1:kind:sub": SimpleNamespace(id=1),
    }

    assert (
        seed_helper.lookup_factor(kind="other", subkind=None, factors_map=factors_map)
        is None
    )


def test_lookup_factor_single_match():
    factor = SimpleNamespace(id=1)
    factors_map = {
        "1:kind:sub": factor,
    }

    result = seed_helper.lookup_factor(
        kind="kind", subkind="sub", factors_map=factors_map
    )

    assert result is factor


def test_lookup_factor_ambiguous_match_logs_warning(caplog):
    factor_one = SimpleNamespace(id=1)
    factor_two = SimpleNamespace(id=2)
    factors_map = {
        "1:kind:sub": factor_one,
        "2:kind:sub": factor_two,
    }

    with caplog.at_level("WARNING"):
        result = seed_helper.lookup_factor(
            kind="kind", subkind="sub", factors_map=factors_map
        )

    assert result in (factor_one, factor_two)
    assert "Ambiguous factor lookup" in caplog.text


@pytest.mark.asyncio
async def test_load_factors_map_builds_keys(monkeypatch):
    factor_one = SimpleNamespace(
        data_entry_type_id=DataEntryTypeEnum.member.value,
        classification={"kind": "Kind", "subkind": "Sub"},
    )
    factor_two = SimpleNamespace(
        data_entry_type_id=DataEntryTypeEnum.member.value,
        classification={"kind": "Kind"},
    )

    service = MagicMock()
    service.list_by_data_entry_type = AsyncMock(return_value=[factor_one, factor_two])

    monkeypatch.setattr(seed_helper, "FactorService", MagicMock(return_value=service))

    factors_map = await seed_helper.load_factors_map(
        session=MagicMock(), data_entry_type=DataEntryTypeEnum.member
    )

    assert f"{DataEntryTypeEnum.member.value}:kind:sub" in factors_map
    assert f"{DataEntryTypeEnum.member.value}:kind" in factors_map
