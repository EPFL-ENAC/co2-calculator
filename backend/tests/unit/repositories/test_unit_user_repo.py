"""Unit tests for unit_user_repo.py (UnitUserRepository)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.app.models.user import RoleName
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit_user import UnitUser
from app.repositories.unit_user_repo import UnitUserRepository


# Dummy RoleName enum for tests
class DummyRole:
    def __init__(self, value):
        self.value = value


ROLE_STD = DummyRole(RoleName.CO2_USER_STD.value)
ROLE_ADMIN = DummyRole(RoleName.CO2_USER_ADMIN.value)


# ----------------------
# Fixtures
# ----------------------
@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session):
    return UnitUserRepository(mock_session)


# ----------------------
# get_by_unit_and_user
# ----------------------
@pytest.mark.asyncio
async def test_get_by_unit_and_user_found(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = MagicMock(spec=UnitUser)
    mock_session.exec.return_value = result
    found = await repo.get_by_unit_and_user("u1", "user1")
    assert found is not None


@pytest.mark.asyncio
async def test_get_by_unit_and_user_not_found(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = None
    mock_session.exec.return_value = result
    found = await repo.get_by_unit_and_user("u1", "user1")
    assert found is None


# ----------------------
# get_by_user
# ----------------------
@pytest.mark.asyncio
async def test_get_by_user(repo, mock_session):
    result = MagicMock()
    result.all.return_value = [MagicMock(spec=UnitUser)]
    mock_session.exec.return_value = result
    items = await repo.get_by_user("user1")
    assert isinstance(items, list)


# ----------------------
# get_by_unit
# ----------------------
@pytest.mark.asyncio
async def test_get_by_unit(repo, mock_session):
    result = MagicMock()
    result.all.return_value = [MagicMock(spec=UnitUser)]
    mock_session.exec.return_value = result
    items = await repo.get_by_unit("u1")
    assert isinstance(items, list)


# ----------------------
# create
# ----------------------
@pytest.mark.asyncio
async def test_create_sets_fields_and_commits(repo, mock_session):
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    entity = await repo.create("u1", "user1", ROLE_STD)
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called
    assert entity is not None


# ----------------------
# update_role
# ----------------------
@pytest.mark.asyncio
async def test_update_role_found_and_updates(repo, mock_session):
    db_obj = MagicMock(spec=UnitUser)
    result = MagicMock()
    result.one_or_none.return_value = db_obj
    mock_session.exec.return_value = result
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    updated = await repo.update_role("u1", "user1", ROLE_ADMIN)
    assert updated is db_obj
    assert db_obj.role == ROLE_ADMIN.value


@pytest.mark.asyncio
async def test_update_role_not_found_raises(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = None
    mock_session.exec.return_value = result
    with pytest.raises(ValueError):
        await repo.update_role("u1", "user1", ROLE_ADMIN)


# ----------------------
# upsert
# ----------------------
@pytest.mark.asyncio
async def test_upsert_existing_role_diff_calls_update(repo, mock_session):
    repo_obj = UnitUserRepository(mock_session)
    existing = MagicMock(spec=UnitUser)
    existing.role = ROLE_STD.value
    with (
        patch.object(
            repo_obj, "get_by_unit_and_user", new=AsyncMock(return_value=existing)
        ),
        patch.object(
            repo_obj, "update_role", new=AsyncMock(return_value=existing)
        ) as update_mock,
    ):
        result = await repo_obj.upsert("u1", "user1", ROLE_ADMIN)
        update_mock.assert_called()
        assert result is existing


@pytest.mark.asyncio
async def test_upsert_existing_role_same_returns_existing(repo, mock_session):
    repo_obj = UnitUserRepository(mock_session)
    existing = MagicMock(spec=UnitUser)
    existing.role = ROLE_STD
    with (
        patch.object(
            repo_obj, "get_by_unit_and_user", new=AsyncMock(return_value=existing)
        ),
        patch.object(repo_obj, "update_role", new=AsyncMock()) as update_mock,
    ):
        result = await repo_obj.upsert("u1", "user1", ROLE_STD)
        update_mock.assert_not_called()
        assert result is existing


@pytest.mark.asyncio
async def test_upsert_new_calls_create(repo, mock_session):
    repo_obj = UnitUserRepository(mock_session)
    with (
        patch.object(
            repo_obj, "get_by_unit_and_user", new=AsyncMock(return_value=None)
        ),
        patch.object(
            repo_obj, "create", new=AsyncMock(return_value=MagicMock(spec=UnitUser))
        ) as create_mock,
    ):
        result = await repo_obj.upsert("u1", "user1", ROLE_STD)
        create_mock.assert_called()
        assert result is not None


# ----------------------
# delete
# ----------------------
@pytest.mark.asyncio
async def test_delete_found_deletes(repo, mock_session):
    db_obj = MagicMock(spec=UnitUser)
    result = MagicMock()
    result.one_or_none.return_value = db_obj
    mock_session.exec.return_value = result
    mock_session.delete.return_value = AsyncMock()
    mock_session.commit.return_value = None
    assert await repo.delete("u1", "user1") is True
    assert mock_session.delete.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_delete_not_found_returns_false(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = None
    mock_session.exec.return_value = result
    assert await repo.delete("u1", "user1") is False


# ----------------------
# count
# ----------------------
@pytest.mark.asyncio
async def test_count_no_filters(repo, mock_session):
    result = MagicMock()
    result.scalar_one.return_value = 42
    mock_session.execute.return_value = result
    count = await repo.count()
    assert count == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filters,expected",
    [
        ({"unit_id": "u1"}, 5),
        ({"user_id": "user1"}, 6),
        ({"role": RoleName.CO2_USER_ADMIN.value}, 7),
        (
            {
                "unit_id": "u1",
                "user_id": "user1",
                "role": RoleName.CO2_USER_ADMIN.value,
            },
            8,
        ),
    ],
)
async def test_count_with_filters(repo, mock_session, filters, expected):
    result = MagicMock()
    result.scalar_one.return_value = expected
    mock_session.execute.return_value = result
    count = await repo.count(filters=filters)
    assert count == expected
