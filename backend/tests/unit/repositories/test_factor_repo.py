"""Tests for FactorRepository."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.models.emission_type import EmissionTypeEnum

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository


@pytest.fixture
def repo():
    session = MagicMock()
    return FactorRepository(session)


@pytest.mark.asyncio
async def test_get(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get(1)

    assert result == factor
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_create(repo):
    factor = Factor(
        emission_type_id=EmissionTypeEnum.energy,
        data_entry_type_id=DataEntryTypeEnum.member,
        classification={},
        values={},
    )
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(factor)

    assert result == factor
    repo.session.add.assert_called_once_with(factor)
    repo.session.flush.assert_awaited_once()
    repo.session.refresh.assert_awaited_once_with(factor)


@pytest.mark.asyncio
async def test_bulk_create(repo):
    factors = [
        Factor(
            emission_type_id=EmissionTypeEnum.energy,
            data_entry_type_id=DataEntryTypeEnum.member,
            classification={},
            values={},
        )
        for _ in range(3)
    ]
    repo.session.add_all = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.bulk_create(factors)

    assert result == factors
    repo.session.add_all.assert_called_once_with(factors)
    repo.session.flush.assert_awaited_once()
    assert repo.session.refresh.await_count == 3


@pytest.mark.asyncio
async def test_update(repo):
    factor = SimpleNamespace(id=1, name="old")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(1, {"name": "new"})

    assert result == factor
    assert factor.name == "new"
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.update(999, {"name": "new"})

    assert result is None


@pytest.mark.asyncio
async def test_delete(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.delete = AsyncMock()
    repo.session.flush = AsyncMock()

    result = await repo.delete(1)

    assert result is True
    repo.session.delete.assert_awaited_once_with(factor)


@pytest.mark.asyncio
async def test_delete_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.delete(999)

    assert result is False


@pytest.mark.asyncio
async def test_list_by_data_entry_type(repo):
    factors = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    result_mock = MagicMock()
    result_mock.all.return_value = factors
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.list_by_data_entry_type(DataEntryTypeEnum.member)

    assert result == factors
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_class_subclass_map(repo):
    factors = [
        ("ClassA", "SubA1"),
        ("ClassA", "SubA2"),
        ("ClassB", "SubB1"),
        ("ClassA", "SubA1"),  # Duplicate
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = factors
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_class_subclass_map(DataEntryTypeEnum.scientific)

    assert result == {"ClassA": ["SubA1", "SubA2"], "ClassB": ["SubB1"]}


@pytest.mark.asyncio
async def test_get_by_classification_with_subkind(repo):
    factor = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_classification(
        DataEntryTypeEnum.member, kind="k1", subkind="s1"
    )

    assert result == factor
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_classification_fallback_to_kind_only(repo):
    factor = SimpleNamespace(id=1)
    result_mock_none = MagicMock()
    result_mock_none.one_or_none.return_value = None
    result_mock_factor = MagicMock()
    result_mock_factor.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(side_effect=[result_mock_none, result_mock_factor])

    result = await repo.get_by_classification(
        DataEntryTypeEnum.member, kind="k1", subkind="s1"
    )

    assert result == factor
    assert repo.session.exec.await_count == 2


@pytest.mark.asyncio
async def test_get_factor_with_fallback(repo):
    factor = SimpleNamespace(id=1)
    result_mock_none = MagicMock()
    result_mock_none.one_or_none.return_value = None
    result_mock_factor = MagicMock()
    result_mock_factor.one_or_none.return_value = factor
    repo.session.exec = AsyncMock(side_effect=[result_mock_none, result_mock_factor])

    result = await repo.get_factor(
        DataEntryTypeEnum.trips,
        fallbacks={"country_code": "RoW"},
        kind="train",
        country_code="FR",
    )

    assert result == factor
    assert repo.session.exec.await_count == 2
