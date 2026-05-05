"""Unit tests for ``app.tasks._poller.dispatch_job``.

Pinning the dispatcher's job_type → handler routing.  Plan 310B Part 5
added a ``unit_sync`` branch (Copilot follow-up): the endpoint creates
NOT_STARTED unit_sync jobs and fires the task in-process, so if the pod
crashes between the endpoint commit and the task's claim_job, the
poller picks up the orphaned row and re-runs it via this dispatcher.
Without the unit_sync branch the row would be stuck NOT_STARTED forever.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import DataIngestionJob
from app.tasks._poller import dispatch_job


def _make_job(
    job_id: int,
    job_type: str,
    *,
    module_type_id: int | None = None,
    data_entry_type_id: int | None = None,
    year: int | None = None,
    meta: dict | None = None,
):
    """Build a minimal mock DataIngestionJob.  ``spec=DataIngestionJob``
    so attribute typos in the dispatcher are caught (would AttributeError
    rather than silently return a Mock)."""
    job = MagicMock(spec=DataIngestionJob)
    job.id = job_id
    job.job_type = job_type
    job.module_type_id = module_type_id
    job.data_entry_type_id = data_entry_type_id
    job.year = year
    job.meta = meta or {}
    return job


@pytest.mark.asyncio
async def test_dispatch_job_routes_unit_sync_to_run_sync_task_accred():
    """A NOT_STARTED unit_sync job picked up by the poller must be
    routed to ``run_sync_task_accred``, with the target_year extracted
    from ``meta["config"]["target_year"]`` (or job.year as fallback).

    Before this branch existed, the dispatcher's else-clause logged
    "Unknown job_type 'unit_sync' — skipping" and the row stayed
    NOT_STARTED forever.
    """
    job = _make_job(
        99,
        "unit_sync",
        year=2025,
        meta={"config": {"target_year": 2025}},
    )

    with patch(
        "app.tasks.unit_sync_tasks.run_sync_task_accred",
        new_callable=AsyncMock,
    ) as mock_run:
        await dispatch_job(job, "test-pod")

    # Routed exactly once, with the unwrapped SyncUnitRequest + job_id.
    assert mock_run.await_count == 1
    sync_request, kwargs = mock_run.await_args.args, mock_run.await_args.kwargs
    assert sync_request[0].target_year == 2025
    assert kwargs["job_id"] == 99


@pytest.mark.asyncio
async def test_dispatch_job_unit_sync_skips_when_year_missing():
    """``unit_sync`` job without a target_year (corrupted meta or
    bug at enqueue time) must be skipped with a warning, NOT raise."""
    job = _make_job(
        99,
        "unit_sync",
        year=None,
        meta={"config": {}},
    )

    with patch(
        "app.tasks.unit_sync_tasks.run_sync_task_accred",
        new_callable=AsyncMock,
    ) as mock_run:
        await dispatch_job(job, "test-pod")

    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_job_unknown_job_type_skips_silently():
    """Sanity check on the else-clause — unknown job_type doesn't
    raise.  If a future refactor accidentally routes ``unit_sync`` here
    again (i.e. removes the elif branch), the test_dispatch_job_routes
    test above will catch it via the unrouted call to run_sync_task_accred.
    """
    job = _make_job(99, "totally_unknown_type")

    # Should not raise.
    await dispatch_job(job, "test-pod")
