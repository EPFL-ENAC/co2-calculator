"""#1236 Phase 4B — ``acquire_factor_recalc_lock`` helper.

Per-``(module, year)`` advisory lock used by ``factor_ingest_handler``
and ``emission_recalc_handler`` (+ ``module_emission_recalc_handler``)
to serialise factor writes vs concurrent recalcs of the same scope.

Tests pin: lock IS attempted on Postgres with the right
``(category, key)`` pair; SKIPPED on non-Postgres backends; SKIPPED
when scope is missing (defensive); and — #2527 B1 — that passing a
``carbon_report_module_id`` downgrades the factor gate to SHARED and
adds an exclusive lock on the module, in that order.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_ingestion import DataIngestionJob
from app.tasks._locks import (
    _FACTOR_RECALC_LOCK_CATEGORY,
    _MODULE_WRITE_LOCK_CATEGORY,
    _encode_module_year_key,
    acquire_factor_recalc_lock,
)
from app.tasks.emission_recalculation_tasks import _lock_module_id, _module_scope
from app.tasks.ingestion_tasks import _pinned_module_id


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
    lock step — skip and let the handler's own scope validation raise.
    """
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
    collisions would cross-serialise unrelated work.
    """
    from app.tasks.aggregation_tasks import _AGGREGATION_LOCK_CATEGORY

    assert _FACTOR_RECALC_LOCK_CATEGORY != _AGGREGATION_LOCK_CATEGORY


def test_every_two_int_advisory_category_is_distinct():
    """#2527 B1 adds a third category to a shared namespace.

    Every 2-int ``pg_advisory_xact_lock(cat, key)`` user in the tree must
    have its own category: a collision would cross-serialise unrelated
    work, and it would look like a slow query, never like a bug.
    """
    from app.tasks.aggregation_tasks import _AGGREGATION_LOCK_CATEGORY

    categories = [
        _AGGREGATION_LOCK_CATEGORY,
        _FACTOR_RECALC_LOCK_CATEGORY,
        _MODULE_WRITE_LOCK_CATEGORY,
    ]
    assert len(set(categories)) == len(categories), categories


@pytest.mark.asyncio
async def test_module_scope_takes_shared_gate_plus_exclusive_module():
    """#2527 B1 — a unit-scoped writer shares the factor gate.

    Order matters as much as the modes: every caller takes the factor
    gate first and the module second, which is what makes the pair
    deadlock-free.
    """
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "postgresql"
    data_session.execute = AsyncMock()

    await acquire_factor_recalc_lock(
        data_session,
        module_type_id=4,
        year=2026,
        handler_label="test",
        carbon_report_module_id=101,
    )

    calls = data_session.execute.await_args_list
    assert len(calls) == 2
    gate_sql, gate_params = str(calls[0].args[0]), calls[0].args[1]
    module_sql, module_params = str(calls[1].args[0]), calls[1].args[1]

    assert "pg_advisory_xact_lock_shared" in gate_sql
    assert gate_params == {
        "cat": _FACTOR_RECALC_LOCK_CATEGORY,
        "key": _encode_module_year_key(4, 2026),
    }
    assert "pg_advisory_xact_lock_shared" not in module_sql
    assert "pg_advisory_xact_lock" in module_sql
    assert module_params == {"cat": _MODULE_WRITE_LOCK_CATEGORY, "key": 101}


@pytest.mark.asyncio
async def test_no_module_scope_keeps_the_exclusive_gate():
    """Factor writers and whole-slice recalcs must not be downgraded."""
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
    sql_text = str(data_session.execute.await_args.args[0])
    assert "pg_advisory_xact_lock_shared" not in sql_text


# ---------------------------------------------------------------------------
# #2527 B1 — the two call-site resolvers that decide the lock's scope.
# They exist only to compute the argument above, so they are pinned here.
# Both must fail towards ``None`` (= exclusive gate): over-serialising is
# slow, under-locking writes duplicate data_entry_emissions rows.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"carbon_report_module_id": 101}, 101),
        ({}, None),
        ({"carbon_report_module_id": None}, None),
        ({"carbon_report_module_id": "101"}, None),
        ({"carbon_report_module_id": [101]}, None),
    ],
)
def test_pinned_module_id_only_narrows_on_a_real_int(config, expected):
    job = DataIngestionJob(job_type="csv_ingest", meta={"config": config})
    assert _pinned_module_id(job) == expected


@pytest.mark.parametrize(
    ("module_scope", "expected"),
    [
        ([101], 101),
        (None, None),
        ([], None),
        ([101, 102], None),
    ],
)
def test_lock_module_id_only_narrows_on_exactly_one_module(module_scope, expected):
    assert _lock_module_id(1, module_scope) == expected


def test_module_scope_matches_what_the_chain_writes():
    """The recalc's lock key and its workflow scope come from one parse.

    ``_chain_emission_recalc_for_data_ingest`` writes
    ``{"carbon_report_module_ids": [id]}``; if ``_module_scope`` read it
    differently the handler would lock one module and rewrite another.
    """
    job = DataIngestionJob(
        job_type="emission_recalc",
        meta={"config": {"carbon_report_module_ids": [101]}},
    )
    scope = _module_scope(job)
    assert scope == [101]
    assert _lock_module_id(1, scope) == 101
