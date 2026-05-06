"""Unit tests for the Plan 310-C registered handlers.

These cover only the handler bodies (not ``run_job``).  The runner's
own behavior — claim, preempt-check, FINISHED state-write,
heartbeat — is tested in ``test_runner.py``; this file pins the
contract handlers must satisfy:

- Read scope from the ``DataIngestionJob`` row (or its ``meta.config``).
- Use the runner-supplied ``job_session`` / ``data_session`` (do not
  open new ``SessionLocal`` connections).
- Do NOT call ``claim_job`` or write the FINISHED state — the
  runner owns both.
- Return a dict the runner persists as ``meta``; ``status_message``
  and ``result`` keys are read by the runner for the FINISHED-state
  write.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult
from app.tasks import emission_recalculation_tasks as recalc_mod
from app.tasks import unit_sync_tasks as unit_sync_mod
from app.tasks.registry import _REGISTRY, get_handler


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Snapshot+restore the registry so test order doesn't matter once
    Tier-2 PRs add more registrations next to the runner suite."""
    snapshot = dict(_REGISTRY)
    yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


def _make_job(
    *,
    job_id: int = 1,
    job_type: str = "emission_recalc",
    module_type_id: int = 11,
    data_entry_type_id: int | None = DataEntryTypeEnum.it.value,
    year: int | None = 2025,
    meta: dict | None = None,
) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.job_type = job_type
    job.module_type_id = module_type_id
    job.data_entry_type_id = data_entry_type_id
    job.year = year
    job.meta = meta or {}
    return job


# ---------------------------------------------------------------------------
# Registration smoke (PR #2's main proof that the @register decorators ran)
# ---------------------------------------------------------------------------


def test_emission_recalc_registered():
    assert get_handler("emission_recalc") is recalc_mod.emission_recalc_handler


def test_module_emission_recalc_registered():
    assert (
        get_handler("module_emission_recalc")
        is recalc_mod.module_emission_recalc_handler
    )


def test_unit_sync_registered():
    assert get_handler("unit_sync") is unit_sync_mod.unit_sync_handler


# ---------------------------------------------------------------------------
# emission_recalc_handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emission_recalc_handler_calls_workflow_and_returns_meta():
    job = _make_job()
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()

    workflow = MagicMock()
    workflow.recalculate_for_data_entry_type = AsyncMock(
        return_value={"recalculated": 7, "errors": 0, "modules_refreshed": 1}
    )

    with (
        patch.object(recalc_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
    ):
        meta = await recalc_mod.emission_recalc_handler(job, job_session, data_session)

    workflow.recalculate_for_data_entry_type.assert_awaited_once_with(
        DataEntryTypeEnum(DataEntryTypeEnum.it.value), 2025
    )
    assert meta["status_message"] == "Emission recalculation completed"
    assert meta["result"] == IngestionResult.SUCCESS
    assert meta["recalculation"]["recalculated"] == 7


@pytest.mark.asyncio
async def test_emission_recalc_handler_warning_when_errors_present():
    """``errors > 0`` flips the result to WARNING (per-entry isolation
    means the run still finished; some rows just failed)."""
    job = _make_job()
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()

    workflow = MagicMock()
    workflow.recalculate_for_data_entry_type = AsyncMock(
        return_value={"recalculated": 5, "errors": 2, "modules_refreshed": 1}
    )

    with (
        patch.object(recalc_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
    ):
        meta = await recalc_mod.emission_recalc_handler(job, job_session, data_session)

    assert meta["result"] == IngestionResult.WARNING


@pytest.mark.asyncio
async def test_emission_recalc_handler_raises_on_missing_scope():
    """Missing ``data_entry_type_id`` or ``year`` → ValueError so the
    runner records FINISHED+ERROR with a clear message."""
    job = _make_job(data_entry_type_id=None)
    with pytest.raises(ValueError, match="missing data_entry_type_id or year"):
        await recalc_mod.emission_recalc_handler(job, MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# module_emission_recalc_handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_module_emission_recalc_iterates_all_types():
    job = _make_job(
        job_type="module_emission_recalc",
        data_entry_type_id=None,
        meta={"config": {"data_entry_type_ids": [1, 2]}},
    )
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()
    data_session.begin_nested = MagicMock()
    data_session.begin_nested.return_value.__aenter__ = AsyncMock()
    data_session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()
    repo.create_ingestion_job = AsyncMock(side_effect=lambda j: j)
    repo.mark_job_as_current = AsyncMock()

    workflow = MagicMock()
    workflow.recalculate_for_data_entry_type = AsyncMock(
        return_value={"recalculated": 3, "errors": 0, "modules_refreshed": 1}
    )

    with (
        patch.object(recalc_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
    ):
        meta = await recalc_mod.module_emission_recalc_handler(
            job, job_session, data_session
        )

    # Both data_entry_type_ids processed.
    assert workflow.recalculate_for_data_entry_type.await_count == 2
    # Per-type stub jobs created (one per type).
    assert repo.create_ingestion_job.await_count == 2
    assert repo.mark_job_as_current.await_count == 2
    assert meta["status_message"] == "Module emission recalculation completed"
    assert meta["result"] == IngestionResult.SUCCESS
    assert meta["total_recalculated"] == 6
    assert meta["total_errors"] == 0


@pytest.mark.asyncio
async def test_module_emission_recalc_partial_failure_returns_warning():
    """One type fails entirely (savepoint rollback) → WARNING; remaining
    types continue."""
    job = _make_job(
        job_type="module_emission_recalc",
        data_entry_type_id=None,
        meta={"config": {"data_entry_type_ids": [1, 2]}},
    )
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()
    data_session.begin_nested = MagicMock()
    data_session.begin_nested.return_value.__aenter__ = AsyncMock()
    data_session.begin_nested.return_value.__aexit__ = AsyncMock(return_value=False)

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()
    repo.create_ingestion_job = AsyncMock(side_effect=lambda j: j)
    repo.mark_job_as_current = AsyncMock()

    workflow = MagicMock()
    # Type 1 succeeds, Type 2 raises.
    workflow.recalculate_for_data_entry_type = AsyncMock(
        side_effect=[
            {"recalculated": 3, "errors": 0, "modules_refreshed": 1},
            RuntimeError("type 2 blew up"),
        ]
    )

    with (
        patch.object(recalc_mod, "DataIngestionRepository", return_value=repo),
        patch.object(
            recalc_mod, "EmissionRecalculationWorkflow", return_value=workflow
        ),
    ):
        meta = await recalc_mod.module_emission_recalc_handler(
            job, job_session, data_session
        )

    assert meta["result"] == IngestionResult.WARNING
    assert meta["total_errors"] == 1


@pytest.mark.asyncio
async def test_module_emission_recalc_raises_when_config_missing():
    job = _make_job(
        job_type="module_emission_recalc",
        data_entry_type_id=None,
        meta={},
    )
    with pytest.raises(ValueError, match="missing config.data_entry_type_ids"):
        await recalc_mod.module_emission_recalc_handler(job, MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# unit_sync_handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unit_sync_handler_runs_full_chain_and_returns_summary():
    job = _make_job(
        job_type="unit_sync",
        meta={"config": {"target_year": 2025}},
    )
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()

    unit_provider = MagicMock()
    unit_provider.fetch_all_units = AsyncMock(return_value=([{}, {}], [{}]))
    unit_provider.map_api_unit = MagicMock(side_effect=lambda u: MagicMock())

    role_provider = MagicMock()
    role_provider.map_api_user = MagicMock(return_value=MagicMock())

    seeded_units = [MagicMock(id=1), MagicMock(id=2)]
    unit_service = MagicMock()
    unit_upsert_result = MagicMock(data=seeded_units)
    unit_service.bulk_upsert = AsyncMock(return_value=unit_upsert_result)

    user_service = MagicMock()
    user_upsert_result = MagicMock(data=[MagicMock()])
    user_service.bulk_upsert = AsyncMock(return_value=user_upsert_result)

    carbon_report_service = MagicMock()
    carbon_report_service.bulk_upsert = AsyncMock(
        return_value=[MagicMock(), MagicMock()]
    )
    carbon_report_service.ensure_modules_for_reports = AsyncMock()

    with (
        patch.object(unit_sync_mod, "DataIngestionRepository", return_value=repo),
        patch.object(unit_sync_mod, "get_unit_provider", return_value=unit_provider),
        patch.object(unit_sync_mod, "get_role_provider", return_value=role_provider),
        patch.object(unit_sync_mod, "UnitService", return_value=unit_service),
        patch.object(unit_sync_mod, "UserService", return_value=user_service),
        patch.object(
            unit_sync_mod,
            "CarbonReportService",
            return_value=carbon_report_service,
        ),
    ):
        meta = await unit_sync_mod.unit_sync_handler(job, job_session, data_session)

    assert meta["status_message"] == "Unit sync completed"
    assert meta["result"] == IngestionResult.SUCCESS
    assert meta["units_synced"] == 2
    assert meta["carbon_reports_created"] == 2
    assert meta["carbon_report_year"] == 2025


@pytest.mark.asyncio
async def test_unit_sync_handler_falls_back_to_job_year_when_config_missing():
    """Plan 310-B's poller branch reads ``meta.config.target_year``;
    when ``meta`` doesn't carry one, fall back to ``job.year`` so
    legacy callers keep working."""
    job = _make_job(job_type="unit_sync", meta={}, year=2024)
    job_session = MagicMock()
    job_session.commit = AsyncMock()
    data_session = MagicMock()

    repo = MagicMock()
    repo.update_ingestion_job = AsyncMock()

    unit_provider = MagicMock()
    unit_provider.fetch_all_units = AsyncMock(return_value=([], []))
    unit_provider.map_api_unit = MagicMock(side_effect=lambda u: MagicMock())
    role_provider = MagicMock()
    role_provider.map_api_user = MagicMock(return_value=MagicMock())

    unit_service = MagicMock()
    unit_service.bulk_upsert = AsyncMock(return_value=MagicMock(data=[]))
    user_service = MagicMock()
    user_service.bulk_upsert = AsyncMock(return_value=MagicMock(data=[]))
    carbon_report_service = MagicMock()
    carbon_report_service.bulk_upsert = AsyncMock(return_value=[])
    carbon_report_service.ensure_modules_for_reports = AsyncMock()

    with (
        patch.object(unit_sync_mod, "DataIngestionRepository", return_value=repo),
        patch.object(unit_sync_mod, "get_unit_provider", return_value=unit_provider),
        patch.object(unit_sync_mod, "get_role_provider", return_value=role_provider),
        patch.object(unit_sync_mod, "UnitService", return_value=unit_service),
        patch.object(unit_sync_mod, "UserService", return_value=user_service),
        patch.object(
            unit_sync_mod,
            "CarbonReportService",
            return_value=carbon_report_service,
        ),
    ):
        meta = await unit_sync_mod.unit_sync_handler(job, job_session, data_session)

    assert meta["carbon_report_year"] == 2024


@pytest.mark.asyncio
async def test_unit_sync_handler_raises_when_no_target_year_anywhere():
    job = _make_job(job_type="unit_sync", meta={}, year=None)
    with pytest.raises(ValueError, match="missing config.target_year"):
        await unit_sync_mod.unit_sync_handler(job, MagicMock(), MagicMock())
