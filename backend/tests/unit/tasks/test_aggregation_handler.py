"""Unit tests for the Plan 310-D ``aggregation`` handler.

Pins the contract:

- ``@register("aggregation")`` ran at import time.
- Reads ``module_type_id`` and ``year`` from the job row; raises
  ``ValueError`` if either is missing so the runner records
  FINISHED+ERROR with a clear message.
- Calls ``CarbonReportModuleService.recompute_stats_many`` once with the affected
  module; returns ``modules_refreshed`` in the meta dict.
- Empty module set → ``modules_refreshed: 0`` and no recompute calls.

The integration shape (the dedup partial unique index) lives in
``tests/integration/services/data_ingestion/``; this file stays in
``tests/unit/`` because it patches the service layer.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionResult
from app.tasks import aggregation_tasks as aggregation_mod
from app.tasks.registry import _REGISTRY, get_handler


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Snapshot+restore the registry so test order doesn't matter and
    re-importing ``aggregation_tasks`` between test files doesn't trip
    the duplicate-registration guard."""
    snapshot = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


def _make_job(
    *,
    job_id: int = 1,
    module_type_id: int | None = 11,
    year: int | None = 2025,
    meta: dict | None = None,
    pipeline_id=None,
) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.job_type = "aggregation"
    job.module_type_id = module_type_id
    job.year = year
    job.meta = meta or {}
    # 4A.3: helper falls back when pipeline_id is None — keep that as
    # the default so existing tests exercise the legacy/full-slice path.
    job.pipeline_id = pipeline_id
    return job


# ---------------------------------------------------------------------------
# Registration smoke
# ---------------------------------------------------------------------------


def test_aggregation_registered():
    assert get_handler("aggregation") is aggregation_mod.aggregation_handler


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregation_calls_recompute_stats_for_each_affected_module():
    """N modules in the (module_type, year) slice → one batched
    ``recompute_stats_many`` call with every module id."""
    job = _make_job()
    job_session = MagicMock()
    data_session = MagicMock()

    modules = [MagicMock(id=101), MagicMock(id=202), MagicMock(id=303)]
    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=modules)
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc):
        meta = await aggregation_mod.aggregation_handler(job, job_session, data_session)

    svc.list_modules_for.assert_awaited_once_with(module_type_id=11, year=2025)
    svc.recompute_stats_many.assert_awaited_once_with([101, 202, 303])
    assert meta["modules_refreshed"] == 3
    assert meta["status_message"] == "Aggregation completed"
    assert meta["result"] == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_aggregation_returns_modules_refreshed_in_meta():
    """Single module case — meta dict shape pinned (status_message,
    result, modules_refreshed)."""
    job = _make_job()
    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=[MagicMock(id=42)])
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc):
        meta = await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())

    assert set(meta.keys()) == {"status_message", "result", "modules_refreshed"}
    assert meta["modules_refreshed"] == 1


@pytest.mark.asyncio
async def test_aggregation_handles_empty_module_set():
    """Empty slice → ``modules_refreshed: 0`` and no recompute calls.

    Defensive but realistic: a fan-out can chain an aggregation job for a
    scope whose modules were deleted between schedule and execute; we
    must finish SUCCESS with a no-op result rather than fail.
    """
    job = _make_job()
    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=[])
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc):
        meta = await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())

    svc.recompute_stats_many.assert_awaited_once_with([])
    assert meta["modules_refreshed"] == 0
    assert meta["result"] == IngestionResult.SUCCESS


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregation_raises_on_missing_module_type_id():
    """Missing ``module_type_id`` → ValueError so the runner records
    FINISHED+ERROR with a clear scope-error message."""
    job = _make_job(module_type_id=None)
    with pytest.raises(ValueError, match="missing module_type_id or year"):
        await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_aggregation_raises_on_missing_year():
    job = _make_job(year=None)
    with pytest.raises(ValueError, match="missing module_type_id or year"):
        await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_aggregation_raises_on_missing_job_id():
    """Defensive — a job without an id isn't persisted, so we shouldn't
    try to recompute on its behalf.  Mirrors the pattern in
    ``emission_recalc_handler``."""
    job = _make_job(job_id=None)
    with pytest.raises(ValueError, match="job has no id"):
        await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# Phase 4A.2 — per-year pg_advisory_xact_lock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregation_acquires_advisory_lock_on_postgres():
    """Postgres backend → handler calls ``pg_advisory_xact_lock(cat, year)``
    before doing work. Serialises cross-pipeline aggregations of the
    same year against the shared ``carbon_reports.stats`` row."""
    job = _make_job(year=2026)
    data_session = MagicMock()
    data_session.get_bind = MagicMock(
        return_value=MagicMock(dialect=MagicMock(name="postgresql"))
    )
    # name= kwarg to MagicMock() is special — set explicitly so it's a str.
    data_session.get_bind.return_value.dialect.name = "postgresql"
    data_session.execute = AsyncMock()

    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=[])
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc):
        await aggregation_mod.aggregation_handler(job, MagicMock(), data_session)

    # First execute call is the advisory-lock SQL.
    assert data_session.execute.await_count >= 1
    first_call = data_session.execute.await_args_list[0]
    sql_text = str(first_call.args[0])
    assert "pg_advisory_xact_lock" in sql_text
    params = first_call.args[1]
    assert params["year"] == 2026
    assert params["cat"] == aggregation_mod._AGGREGATION_LOCK_CATEGORY


@pytest.mark.asyncio
async def test_aggregation_skips_advisory_lock_on_non_postgres():
    """SQLite / other backends → no advisory-lock attempt (skipped
    cleanly, single-writer model serialises tests)."""
    job = _make_job(year=2026)
    data_session = MagicMock()
    data_session.get_bind.return_value.dialect.name = "sqlite"
    data_session.execute = AsyncMock()

    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=[])
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc):
        await aggregation_mod.aggregation_handler(job, MagicMock(), data_session)

    # No advisory-lock SQL issued.
    for call in data_session.execute.await_args_list:
        assert "pg_advisory_xact_lock" not in str(call.args[0])


# ---------------------------------------------------------------------------
# Phase 4A.3 — affected_module_ids scoping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregation_scopes_to_affected_module_ids():
    """When recalc siblings recorded affected_module_ids, the aggregation
    recomputes ONLY those modules, not the full (module, year) slice."""
    job = _make_job(pipeline_id="dummy")
    modules = [MagicMock(id=101), MagicMock(id=202), MagicMock(id=303)]
    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=modules)
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with (
        patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc),
        patch.object(
            aggregation_mod,
            "_collect_affected_module_ids",
            new=AsyncMock(return_value={101, 303}),
        ),
    ):
        meta = await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())

    svc.recompute_stats_many.assert_awaited_once_with([101, 303])
    assert meta["modules_refreshed"] == 2


@pytest.mark.asyncio
async def test_aggregation_falls_back_to_full_slice_when_no_affected_meta():
    """Helper returns None (legacy / no recalc meta) → preserves prior
    behavior of recomputing every module in the (module, year) slice."""
    job = _make_job(pipeline_id="dummy")
    modules = [MagicMock(id=101), MagicMock(id=202), MagicMock(id=303)]
    svc = MagicMock()
    svc.list_modules_for = AsyncMock(return_value=modules)
    svc.recompute_stats_many = AsyncMock(side_effect=lambda ids: len(ids))

    with (
        patch.object(aggregation_mod, "CarbonReportModuleService", return_value=svc),
        patch.object(
            aggregation_mod,
            "_collect_affected_module_ids",
            new=AsyncMock(return_value=None),
        ),
    ):
        meta = await aggregation_mod.aggregation_handler(job, MagicMock(), MagicMock())

    svc.recompute_stats_many.assert_awaited_once_with([101, 202, 303])
    assert meta["modules_refreshed"] == 3
