"""Tests for UnitRepository."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.unit import Unit
from app.models.user import UserProvider
from app.repositories.unit_repo import UnitRepository


@pytest.fixture
def repo():
    session = MagicMock()
    return UnitRepository(session)


@pytest.mark.asyncio
async def test_get_by_id(repo):
    unit = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id(1)

    assert result == unit
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_id_none(repo):
    result = await repo.get_by_id(None)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_code(repo):
    unit = SimpleNamespace(provider_code="U1")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_code("U1")

    assert result == unit
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_code_none(repo):
    result = await repo.get_by_code(None)
    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_or_code_int(repo):
    unit = SimpleNamespace(id=1)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id_or_code(1)

    assert result == unit


@pytest.mark.asyncio
async def test_get_by_id_or_code_string(repo):
    unit = SimpleNamespace(provider_code="U1")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id_or_code("U1")

    assert result == unit


@pytest.mark.asyncio
async def test_get_by_codes(repo):
    units = [SimpleNamespace(provider_code="U1"), SimpleNamespace(provider_code="U2")]
    result_mock = MagicMock()
    result_mock.all.return_value = units
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_codes(["U1", "U2"])

    assert result == units
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_create(repo):
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(
        provider_code="U1",
        name="Unit 1",
        principal_user_provider_code="user1",
        affiliations=["aff1"],
        provider=UserProvider.DEFAULT,
        cost_centers=["c1"],
    )

    assert result.provider_code == "U1"
    assert result.name == "Unit 1"
    repo.session.add.assert_called_once()
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update(repo):
    unit = SimpleNamespace(id=1, name="old", provider=UserProvider.DEFAULT)
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.update(1, name="new")

    assert result == unit
    assert unit.name == "new"
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    with pytest.raises(ValueError, match="Unit not found"):
        await repo.update(999, name="new")


@pytest.mark.asyncio
async def test_upsert_create(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    unit_data = Unit(provider_code="U1", name="Unit 1")

    result = await repo.upsert(unit_data)

    assert result.provider_code == "U1"
    repo.session.add.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_update(repo):
    existing = SimpleNamespace(id=1, name="old", provider=UserProvider.DEFAULT)
    result_mock_existing = MagicMock()
    result_mock_existing.one_or_none.return_value = existing
    result_mock_updated = MagicMock()
    result_mock_updated.one_or_none.return_value = existing
    repo.session.exec = AsyncMock(
        side_effect=[result_mock_existing, result_mock_updated]
    )
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    unit_data = Unit(provider_code="U1", name="new")

    result = await repo.upsert(unit_data)

    assert result.name == "new"
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_count(repo):
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = 42
    repo.session.execute = AsyncMock(return_value=result_mock)

    result = await repo.count()

    assert result == 42
    repo.session.execute.assert_awaited_once()
