"""#1236 Phase 4B — ``acquire_factor_recalc_lock`` helper.

Per-``(module, year)`` advisory lock used by ``factor_ingest_handler``
and ``emission_recalc_handler`` (+ ``module_emission_recalc_handler``)
to serialise factor writes vs concurrent recalcs of the same scope.

Tests pin: lock IS attempted on Postgres with the right
``(category, key)`` pair; SKIPPED on non-Postgres backends; SKIPPED
when scope is missing (defensive).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tasks._locks import (
    _FACTOR_RECALC_LOCK_CATEGORY,
    _encode_module_year_key,
    acquire_factor_recalc_lock,
)


def test_encode_module_year_key_is_collision_free():
    """Distinct (module, year) pairs hash to distinct keys."""
    seen: dict[int, tuple[int, int]] = {}
    for module in (1, 2, 4, 7, 8, 99):
        for year in (2023, 2024, 2025, 2026):
            key = _encode_module_year_key(module, year)
            assert key not in seen, (
                f"collision: ({module},{year}) and {seen[key]} → {key}"
            )
            seen[key] = (module, year)


@pytest.mark.asyncio
async def test_acquires_lock_on_postgres():
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "postgresql"
    data_session.execute = AsyncMock()

    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=4,
        year=2026,
        handler_label="test",
    )

    data_session.execute.assert_awaited_once()
    args = data_session.execute.await_args
    sql_text = str(args.args[0])
    assert "pg_advisory_xact_lock" in sql_text
    params = args.args[1]
    assert params["cat"] == _FACTOR_RECALC_LOCK_CATEGORY
    assert params["key"] == _encode_module_year_key(4, 2026)


@pytest.mark.asyncio
async def test_skips_lock_on_non_postgres():
    """SQLite / other → single-writer model already serialises; no-op."""
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "sqlite"
    data_session.execute = AsyncMock()

    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=4,
        year=2026,
        handler_label="test",
    )

    data_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_lock_when_module_type_id_missing():
    """Defensive: job without scope shouldn't crash the handler at the
    lock step — skip and let the handler's own scope validation raise."""
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "postgresql"
    data_session.execute = AsyncMock()

    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=None,
        year=2026,
        handler_label="test",
    )

    data_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_lock_when_year_missing():
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "postgresql"
    data_session.execute = AsyncMock()

    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=4,
        year=None,
        handler_label="test",
    )

    data_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_lock_category_distinct_from_aggregation_lock():
    """4B's category must not collide with 4A.2's aggregation lock —
    they're in the same advisory-lock namespace and accidental
    collisions would cross-serialise unrelated work."""
    from app.tasks.aggregation_tasks import _AGGREGATION_LOCK_CATEGORY

    assert _FACTOR_RECALC_LOCK_CATEGORY != _AGGREGATION_LOCK_CATEGORY
