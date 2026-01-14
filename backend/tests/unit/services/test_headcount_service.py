from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.models.user import User
from app.services.headcount_service import HeadcountService


# ----------------------
# Fixtures
# ----------------------
@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def service(mock_session):
    return HeadcountService(mock_session)


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = "user1"
    user.has_role = MagicMock(return_value=True)
    return user


# ----------------------
# get_module_stats
# ----------------------
@pytest.mark.asyncio
async def test_get_module_stats_delegates(service):
    with patch.object(
        service.repo, "get_module_stats", new=AsyncMock(return_value={"foo": 1})
    ) as mock_stats:
        stats = await service.get_module_stats("u1", 2025, aggregate_by="submodule")
        mock_stats.assert_called_with(unit_id="u1", year=2025, aggregate_by="submodule")
        assert stats == {"foo": 1}


# ----------------------
# create_headcount
# ----------------------
@pytest.mark.asyncio
async def test_create_headcount_delegates(service):
    data = MagicMock(spec=HeadCountCreate)
    with patch.object(
        service.repo,
        "create_headcount",
        new=AsyncMock(return_value=MagicMock(spec=HeadCount)),
    ) as mock_create:
        result = await service.create_headcount(
            data, provider_source="csv", user_id="u1"
        )
        mock_create.assert_called_with(data=data, provider_source="csv", user_id="u1")
        assert result is not None


# ----------------------
# update_headcount
# ----------------------
@pytest.mark.asyncio
async def test_update_headcount_delegates(service, mock_user):
    data = MagicMock(spec=HeadCountUpdate)
    with patch.object(
        service.repo,
        "update_headcount",
        new=AsyncMock(return_value=MagicMock(spec=HeadCount)),
    ) as mock_update:
        result = await service.update_headcount(1, data, user=mock_user)
        mock_update.assert_called_with(headcount_id=1, data=data, user_id=mock_user.id)
        assert result is not None


# ----------------------
# delete_headcount
# ----------------------
# NOTE: Authorization is now handled at the route level via require_permission().
# Service-level tests no longer need to test authorization logic.
@pytest.mark.asyncio
async def test_delete_headcount_delegates(service):
    """Test that delete_headcount delegates to repository correctly."""
    with patch.object(
        service.repo, "delete_headcount", new=AsyncMock(return_value=True)
    ) as mock_delete:
        result = await service.delete_headcount(1)
        mock_delete.assert_called_with(1)
        assert result is True


# ----------------------
# get_by_id
# ----------------------
@pytest.mark.asyncio
async def test_get_by_id_delegates(service):
    with patch.object(
        service.repo, "get_by_id", new=AsyncMock(return_value=MagicMock(spec=HeadCount))
    ) as mock_get:
        result = await service.get_by_id(1)
        mock_get.assert_called_with(1)
        assert result is not None


# ----------------------
# get_headcounts
# ----------------------
@pytest.mark.asyncio
async def test_get_headcounts_delegates(service):
    """Test that get_headcounts delegates to repository with filters."""
    with patch.object(
        service.repo,
        "get_headcounts",
        new=AsyncMock(return_value=[MagicMock(spec=HeadCount)]),
    ) as mock_get:
        result = await service.get_headcounts(
            "u1", 2025, 10, 0, "id", "asc", filter=None
        )
        # Service adds filters=None when user context is not available
        mock_get.assert_called_with("u1", 2025, 10, 0, "id", "asc", None, filters=None)
        assert isinstance(result, list)


# ----------------------
# get_module_data
# ----------------------
@pytest.mark.asyncio
async def test_get_module_data_aggregates(service):
    # Patch repo.get_summary_by_submodule to return fake summary
    fake_summary = {
        "member": {"total_items": 2, "annual_fte": 1.5},
        "student": {"total_items": 1, "annual_fte": 0.5},
    }
    with patch.object(
        service.repo,
        "get_summary_by_submodule",
        new=AsyncMock(return_value=fake_summary),
    ):
        resp = await service.get_module_data("u1", 2025)
        assert resp.totals.total_items == 3
        assert resp.totals.total_annual_fte == 2.0
        assert set(resp.submodules.keys()) == {"member", "student"}


# ----------------------
# get_submodule_data
# ----------------------
@pytest.mark.asyncio
async def test_get_submodule_data_delegates(service):
    with patch.object(
        service.repo, "get_submodule_data", new=AsyncMock(return_value=MagicMock())
    ) as mock_get:
        result = await service.get_submodule_data(
            "u1", 2025, "member", 10, 0, "date", "asc", filter=None
        )
        mock_get.assert_called_with(
            unit_id="u1",
            year=2025,
            submodule_key="member",
            limit=10,
            offset=0,
            sort_by="date",
            sort_order="asc",
            filter=None,
        )
        assert result is not None


# ----------------------
# get_by_unit_and_date
# ----------------------
@pytest.mark.asyncio
async def test_get_by_unit_and_date_delegates(service):
    with patch.object(
        service.repo,
        "get_by_unit_and_date",
        new=AsyncMock(return_value=MagicMock(spec=HeadCount)),
    ) as mock_get:
        result = await service.get_by_unit_and_date("u1", "2025-01-01")
        mock_get.assert_called_with("u1", "2025-01-01")
        assert result is not None
