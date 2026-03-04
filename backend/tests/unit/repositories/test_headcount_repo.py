"""Unit tests for headcount_repo.py (HeadCountRepository and helpers)."""

from datetime import date as dt_date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.repositories.headcount_repo import (
    ROLE_CATEGORY_MAPPING,
    HeadCountRepository,
    get_function_role,
)


# ----------------------
# Utility: get_function_role
# ----------------------
def test_get_function_role_known():
    for fr, en in ROLE_CATEGORY_MAPPING.items():
        assert get_function_role(fr) == en


def test_get_function_role_unknown():
    assert get_function_role("Nonexistent Role") == "other"


# ----------------------
# HeadCountRepository: fixtures
# ----------------------
@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repo(mock_session):
    return HeadCountRepository(mock_session)


# ----------------------
# get_module_stats
# ----------------------
@pytest.mark.asyncio
async def test_get_module_stats_basic(repo, mock_session):
    # Setup mock result
    mock_result = MagicMock()
    mock_result.all.return_value = [("foo", 2), (None, 1)]
    mock_session.exec.return_value = mock_result
    stats = await repo.get_module_stats("unit1", 2025, aggregate_by="submodule")
    assert stats == {"foo": 2, "unknown": 1}


# ----------------------
# create_headcount
# ----------------------
@pytest.mark.asyncio
async def test_create_headcount_sets_fields(repo, mock_session):
    data = HeadCountCreate(
        date=dt_date(2025, 1, 1),
        unit_id=1,
        unit_name="Unit",
        cf="cf1",
        cf_name="CF Name",
        cf_user_id=None,
        display_name="John Doe",
        status=None,
        function="Professeur titulaire",
        sciper="1234",
        fte=1.0,
        submodule="member",
    )
    with patch(
        "app.models.headcount.HeadCount.model_validate",
        return_value=MagicMock(spec=HeadCount),
    ) as mv:
        await repo.create_headcount(data, provider_source="csv", user_id="u42")
        assert mock_session.add.called
        assert mock_session.commit.called
        assert mock_session.refresh.called
        mv.assert_called()


@pytest.mark.asyncio
async def test_create_headcount_student_forces_role_student(repo, mock_session):
    data = HeadCountCreate(
        date=dt_date(2025, 1, 1),
        unit_id=1,
        unit_name="Unit",
        cf="cf1",
        cf_name="CF Name",
        cf_user_id=None,
        display_name="Jane",
        status=None,
        function="Professeur titulaire",
        sciper="1234",
        fte=1.0,
        submodule="student",
    )
    with patch(
        "app.models.headcount.HeadCount.model_validate",
        return_value=MagicMock(spec=HeadCount),
    ) as mv:
        await repo.create_headcount(data, provider_source="csv", user_id="u42")
        args = mv.call_args[0][0]
        assert args["function_role"] == "student"


# ----------------------
# update_headcount
# ----------------------
@pytest.mark.asyncio
async def test_update_headcount_found_and_updates_fields(repo, mock_session):
    db_obj = MagicMock(spec=HeadCount)
    db_obj.submodule = "member"
    result = MagicMock()
    result.one_or_none.return_value = db_obj
    mock_session.exec.return_value = result
    data = HeadCountUpdate(function="Professeur titulaire", fte=0.5)
    updated = await repo.update_headcount(1, data, user_id="u42")
    assert updated is db_obj
    assert db_obj.updated_by == "u42"
    assert db_obj.fte == 0.5
    assert db_obj.function_role == "professor"


@pytest.mark.asyncio
async def test_update_headcount_student_forces_role_student(repo, mock_session):
    db_obj = MagicMock(spec=HeadCount)
    db_obj.submodule = "student"
    result = MagicMock()
    result.one_or_none.return_value = db_obj
    mock_session.exec.return_value = result
    data = HeadCountUpdate(function="Professeur titulaire")
    await repo.update_headcount(1, data, user_id="u42")
    assert db_obj.function_role == "student"


@pytest.mark.asyncio
async def test_update_headcount_not_found_returns_none(repo, mock_session):
    result = MagicMock()
    result.one_or_none.return_value = None
    mock_session.exec.return_value = result
    data = HeadCountUpdate(function="Professeur titulaire")
    assert await repo.update_headcount(1, data, user_id="u42") is None


# ----------------------
# delete_headcount
# ----------------------
@pytest.mark.asyncio
async def test_delete_headcount_found_deletes(repo, mock_session):
    db_obj = MagicMock(spec=HeadCount)
    result = MagicMock()
    result.scalar_one_or_none.return_value = db_obj
    mock_session.execute.return_value = result
    mock_session.delete.return_value = AsyncMock()
    assert await repo.delete_headcount(1) is True
    assert mock_session.delete.called
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_delete_headcount_not_found_returns_false(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result
    assert await repo.delete_headcount(1) is False


# ----------------------
# get_headcounts
# ----------------------
@pytest.mark.asyncio
async def test_get_headcounts_orders_and_limits(repo, mock_session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = [MagicMock(spec=HeadCount)]
    mock_session.execute.return_value = result
    items = await repo.get_headcounts(1, 2025, 10, 0, "id", "asc")
    assert isinstance(items, list)


# ----------------------
# get_summary_by_submodule
# ----------------------
@pytest.mark.asyncio
async def test_get_summary_by_submodule_basic(repo, mock_session):
    result = MagicMock()
    result.all.return_value = [
        ("member", 2, 1.5),
        ("student", 1, 0.5),
    ]
    mock_session.execute.return_value = result
    summary = await repo.get_summary_by_submodule(1, 2025)
    assert summary["member"]["total_items"] == 2
    assert summary["member"]["annual_fte"] == 1.5


# ----------------------
# get_submodule_data
# ----------------------
@pytest.mark.asyncio
async def test_get_submodule_data_basic(repo, mock_session):
    # Patch SubmoduleResponse and SubmoduleSummary
    with (
        patch("app.repositories.headcount_repo.SubmoduleResponse") as SubmoduleResponse,
        patch("app.repositories.headcount_repo.SubmoduleSummary") as SubmoduleSummary,
    ):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [MagicMock(spec=HeadCount)]
        mock_session.execute.side_effect = [
            result,
            MagicMock(scalar_one=MagicMock(return_value=1)),
        ]
        repo_obj = HeadCountRepository(mock_session)
        await repo_obj.get_submodule_data(1, 2025, "member", 10, 0, "id", "asc")
        assert SubmoduleResponse.called
        assert SubmoduleSummary.called


@pytest.mark.asyncio
async def test_get_submodule_data_with_filter(repo, mock_session):
    with (
        patch("app.repositories.headcount_repo.SubmoduleResponse") as SubmoduleResponse,
    ):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [MagicMock(spec=HeadCount)]
        mock_session.execute.side_effect = [
            result,
            MagicMock(scalar_one=MagicMock(return_value=1)),
        ]
        repo_obj = HeadCountRepository(mock_session)
        await repo_obj.get_submodule_data(
            1, 2025, "member", 10, 0, "id", "asc", filter="foo"
        )
        assert SubmoduleResponse.called


@pytest.mark.asyncio
async def test_get_submodule_data_filter_too_long(repo, mock_session):
    with (
        patch("app.repositories.headcount_repo.SubmoduleResponse") as SubmoduleResponse,
    ):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [MagicMock(spec=HeadCount)]
        mock_session.execute.side_effect = [
            result,
            MagicMock(scalar_one=MagicMock(return_value=1)),
        ]
        repo_obj = HeadCountRepository(mock_session)
        long_filter = "x" * 200
        await repo_obj.get_submodule_data(
            1, 2025, "member", 10, 0, "id", "asc", filter=long_filter
        )
        assert SubmoduleResponse.called


# ----------------------
# get_by_id
# ----------------------
@pytest.mark.asyncio
async def test_get_by_id_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock(spec=HeadCount)
    mock_session.execute.return_value = result
    found = await repo.get_by_id(1)
    assert found is not None


@pytest.mark.asyncio
async def test_get_by_id_not_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result
    found = await repo.get_by_id(1)
    assert found is None


# ----------------------
# get_by_unit_and_date
# ----------------------
@pytest.mark.asyncio
async def test_get_by_unit_and_date_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = MagicMock(spec=HeadCount)
    mock_session.execute.return_value = result
    found = await repo.get_by_unit_and_date(1, "2025-01-01")
    assert found is not None


@pytest.mark.asyncio
async def test_get_by_unit_and_date_not_found(repo, mock_session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result
    found = await repo.get_by_unit_and_date(1, "2025-01-01")
    assert found is None
