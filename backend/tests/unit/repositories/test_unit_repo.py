"""Unit tests for unit_repo.py (UnitRepository)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit import Unit
from app.repositories.unit_repo import UnitRepository


# ----------------------
# Fixtures
# ----------------------
@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session):
    return UnitRepository(mock_session)


# ----------------------
# get_by_id
# ----------------------
@pytest.mark.asyncio
async def test_get_by_id_found(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = MagicMock(spec=Unit)
    mock_session.exec.return_value = result
    found = await repo.get_by_id("u1")
    assert found is not None


@pytest.mark.asyncio
async def test_get_by_id_none(repo, mock_session):
    found = await repo.get_by_id(None)
    assert found is None


# ----------------------
# get_by_ids
# ----------------------
@pytest.mark.asyncio
async def test_get_by_ids(repo, mock_session):
    result = MagicMock()
    result.all.return_value = [MagicMock(spec=Unit)]
    mock_session.exec.return_value = result
    items = await repo.get_by_ids(["u1", "u2"])
    assert isinstance(items, list)


# ----------------------
# list
# ----------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unit_id_filter,visibility_filter",
    [
        (None, None),
        (["u1"], None),
        (None, ["public"]),
        (["u1"], ["public"]),
    ],
)
async def test_list_variants(repo, mock_session, unit_id_filter, visibility_filter):
    result = MagicMock()
    result.all.return_value = [MagicMock(spec=Unit)]
    mock_session.exec.return_value = result
    items = await repo.list(
        0, 10, visibility_filter=visibility_filter, unit_id_filter=unit_id_filter
    )
    assert isinstance(items, list)


# ----------------------
# create
# ----------------------
@pytest.mark.asyncio
async def test_create_sets_fields_and_commits(repo, mock_session):
    mock_session.add.return_value = None
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    unit = await repo.create(
        unit_id="u1",
        name="Unit Name",
        visibility="public",
        principal_user_id="p1",
        principal_user_function="func",
        affiliations=["aff1"],
        created_by="user42",
        provider="testprov",
    )
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called
    assert unit is not None


# ----------------------
# update
# ----------------------
@pytest.mark.asyncio
async def test_update_found_and_updates_fields(repo, mock_session):
    db_obj = MagicMock(spec=Unit)
    result = MagicMock()
    result.one_or_none.return_value = db_obj
    mock_session.exec.return_value = result
    mock_session.commit.return_value = None
    mock_session.refresh.return_value = None
    updated = await repo.update(
        unit_id="u1",
        name="New Name",
        visibility="unit",
        principal_user_id="p2",
        principal_user_function="func2",
        affiliations=["aff2"],
        updated_by="user43",
        provider="prov2",
    )
    assert updated is db_obj
    assert db_obj.name == "New Name"
    assert db_obj.visibility == "unit"
    assert db_obj.principal_user_id == "p2"
    assert db_obj.principal_user_function == "func2"
    assert db_obj.affiliations == ["aff2"]
    assert db_obj.provider == "prov2"
    assert db_obj.updated_by == "user43"


@pytest.mark.asyncio
async def test_update_not_found_raises(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = None
    mock_session.exec.return_value = result
    with pytest.raises(ValueError):
        await repo.update(unit_id="u1")


# ----------------------
# upsert
# ----------------------
@pytest.mark.asyncio
async def test_upsert_existing_calls_update(repo, mock_session):
    repo_obj = UnitRepository(mock_session)
    unit_data = MagicMock(spec=Unit)
    unit_data.id = "u1"
    with (
        patch.object(repo_obj, "get_by_id", new=AsyncMock(return_value=unit_data)),
        patch.object(
            repo_obj, "update", new=AsyncMock(return_value=unit_data)
        ) as update_mock,
    ):
        result = await repo_obj.upsert(unit_data, user_id="user1", provider="prov")
        update_mock.assert_called()
        assert result is unit_data


@pytest.mark.asyncio
async def test_upsert_new_calls_create(repo, mock_session):
    repo_obj = UnitRepository(mock_session)
    unit_data = MagicMock(spec=Unit)
    unit_data.id = "u2"
    unit_data.name = "Unit2"
    unit_data.visibility = "public"
    unit_data.principal_user_id = "p1"
    unit_data.principal_user_function = "func"
    unit_data.affiliations = ["aff1"]
    with (
        patch.object(repo_obj, "get_by_id", new=AsyncMock(return_value=None)),
        patch.object(
            repo_obj, "create", new=AsyncMock(return_value=unit_data)
        ) as create_mock,
    ):
        result = await repo_obj.upsert(unit_data, user_id="user2", provider="prov2")
        create_mock.assert_called()
        assert result is unit_data


@pytest.mark.asyncio
async def test_upsert_missing_id_raises(repo, mock_session):
    repo_obj = UnitRepository(mock_session)
    unit_data = MagicMock(spec=Unit)
    unit_data.id = None
    with patch.object(repo_obj, "get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(ValueError):
            await repo_obj.upsert(unit_data, user_id="user3", provider="prov3")


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
async def test_count_with_filters(repo, mock_session):
    result = MagicMock()
    result.scalar_one.return_value = 7
    mock_session.execute.return_value = result
    count = await repo.count(filters={"visibility": "public"})
    assert count == 7
