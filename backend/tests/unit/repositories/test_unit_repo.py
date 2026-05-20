"""Tests for UnitRepository."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.unit import Unit
from app.models.user import UserProvider
from app.repositories.unit_repo import UnitRepository
from app.schemas.unit import UnitUpdate


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
async def test_get_by_institutional_id(repo):
    unit = SimpleNamespace(institutional_code="U1")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_institutional_id("U1")

    assert result == unit
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_institutional_id_none(repo):
    result = await repo.get_by_institutional_id(None)
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
    unit = SimpleNamespace(institutional_code="U1")
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = unit
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_id_or_code("U1")

    assert result == unit


@pytest.mark.asyncio
async def test_get_by_institutional_ids(repo):
    units = [
        SimpleNamespace(institutional_code="U1"),
        SimpleNamespace(institutional_code="U2"),
    ]
    result_mock = MagicMock()
    result_mock.all.return_value = units
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.get_by_institutional_ids(["U1", "U2"])

    assert result == units
    repo.session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_create(repo):
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    result = await repo.create(
        Unit(
            institutional_code="U1",
            name="Unit 1",
            level=4,
            principal_user_institutional_id="user1",
            path_name=None,
            provider=UserProvider.DEFAULT,
            institutional_id=None,
        )
    )

    assert result.institutional_code == "U1"
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

    result = await repo.update(UnitUpdate(id=1, name="new"))

    assert result == unit
    assert unit.name == "new"
    repo.session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_not_found(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)

    result = await repo.update(UnitUpdate(id=999, name="new"))
    assert result is None


@pytest.mark.asyncio
async def test_upsert_create(repo):
    result_mock = MagicMock()
    result_mock.one_or_none.return_value = None
    repo.session.exec = AsyncMock(return_value=result_mock)
    repo.session.add = MagicMock()
    repo.session.flush = AsyncMock()
    repo.session.refresh = AsyncMock()

    unit_data = Unit(institutional_code="U1", name="Unit 1", level=4)

    result = await repo.upsert(unit_data)

    assert result.institutional_code == "U1"
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

    unit_data = Unit(institutional_code="U1", name="new", level=4)

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


# ---------------------------------------------------------------------------
# bulk_upsert race-safety (#1236) — Postgres path uses INSERT … ON
# CONFLICT DO UPDATE so two parallel unit_sync jobs no longer crash on
# ``ix_units_institutional_code``.  User-reported 2026-05-20: creating
# year 2025 + 2026 in parallel had the second handler fail with
# ``UniqueViolation`` on code 14270.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_upsert_postgresql_uses_on_conflict():
    """Postgres backend → bulk_upsert issues an INSERT statement that
    carries ON CONFLICT (institutional_code) DO UPDATE.  Race-safe by
    construction: two concurrent transactions both INSERT, the loser
    gets the DO UPDATE branch instead of a UniqueViolation."""
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "postgresql"

    # First execute(): SELECT existing codes (used for created/updated
    # count).  Returns an empty result so every unit looks "new".
    pre_select_result = MagicMock()
    pre_select_result.all = MagicMock(return_value=[])
    # Second execute(): the INSERT … ON CONFLICT itself.  RETURNING
    # bounces the inserted/updated row back.
    upsert_result = MagicMock()
    upsert_result.scalars.return_value.all.return_value = [MagicMock(id=1)]

    session.execute = AsyncMock(side_effect=[pre_select_result, upsert_result])

    repo = UnitRepository(session)
    unit = Unit(
        provider=UserProvider.DEFAULT,
        institutional_code="14270",
        name="180C",
        level=4,
    )

    res = await repo.bulk_upsert([unit])

    # Two execute() calls: SELECT for created-count, INSERT…ON CONFLICT.
    assert session.execute.await_count == 2
    insert_sql = str(session.execute.await_args_list[1].args[0])
    assert "ON CONFLICT" in insert_sql.upper()
    assert "institutional_code" in insert_sql
    assert res.total == 1


@pytest.mark.asyncio
async def test_bulk_upsert_sqlite_uses_legacy_select_merge():
    """SQLite test fixture (single-writer) → no race possible, keep the
    legacy SELECT-then-merge path.  Pinned so a refactor doesn't break
    the test fixture by forcing ON CONFLICT (which SQLAlchemy's
    sqlite dialect supports but the existing tests don't expect)."""
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "sqlite"

    rows_result = MagicMock()
    rows_result.all = MagicMock(return_value=[("X1", 1), ("X2", 2)])
    session.exec = AsyncMock(return_value=rows_result)
    session.merge = AsyncMock(side_effect=lambda u: u)

    repo = UnitRepository(session)
    units = [
        Unit(
            provider=UserProvider.DEFAULT,
            institutional_code="X1",
            name="A",
            level=4,
        ),
        Unit(
            provider=UserProvider.DEFAULT,
            institutional_code="NEW",
            name="C",
            level=4,
        ),
    ]

    res = await repo.bulk_upsert(units)

    # Legacy path uses session.exec (not session.execute) for the SELECT.
    session.exec.assert_awaited_once()
    # No ON CONFLICT statement on this path.
    for call in session.execute.await_args_list:
        assert "ON CONFLICT" not in str(call.args[0]).upper()
    assert res.created == 1  # NEW
    assert res.updated == 1  # X1 matched


@pytest.mark.asyncio
async def test_bulk_upsert_empty_input_short_circuits():
    """Defensive — empty input must short-circuit BEFORE the dialect
    check (no DB queries) so a no-op upsert is free."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.exec = AsyncMock()
    repo = UnitRepository(session)

    res = await repo.bulk_upsert([])

    assert res.total == 0
    assert res.data == []
    # No DB queries on the no-op path.
    session.execute.assert_not_awaited()
    session.exec.assert_not_awaited()
