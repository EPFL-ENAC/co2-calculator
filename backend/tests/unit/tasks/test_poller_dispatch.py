"""Unit tests for ``app.tasks._poller.dispatch_job`` (Plan 310-C cutover).

Plan 310-C unifies dispatch under ``app.tasks.runner.run_job``.  The
poller's ``dispatch_job`` is now a thin pass-through: every job_type
funnels through ``run_job(job_id)``.  These tests pin that contract so
a future refactor doesn't accidentally re-introduce per-job_type
branching here (the registry is the single source of truth — see
``app/tasks/registry.py``).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import DataIngestionJob
from app.tasks._poller import _IN_FLIGHT_JOB_IDS, dispatch_job, schedule_job


def _make_job(job_id: int | None, job_type: str | None = "csv_ingest"):
    """Minimal mock DataIngestionJob.  ``spec=DataIngestionJob`` so
    attribute typos in the dispatcher AttributeError rather than
    silently return a Mock.
    """
    job = MagicMock(spec=DataIngestionJob)
    job.id = job_id
    job.job_type = job_type
    return job


@pytest.mark.asyncio
async def test_dispatch_job_routes_through_run_job():
    """Every job — regardless of job_type — funnels through ``run_job``.

    The registry resolution happens INSIDE ``run_job``; the poller no
    longer cares about the job_type.  This is the core 310-C invariant
    that lets us delete the per-job_type if/elif from the legacy
    ``dispatch_job``.
    """
    job = _make_job(99, "csv_ingest")
    with patch("app.tasks._poller.run_job", new_callable=AsyncMock) as mock_run:
        await dispatch_job(job, "test-pod")
    mock_run.assert_awaited_once_with(99)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_type",
    [
        "csv_ingest",
        "api_ingest",
        "factor_ingest",
        "emission_recalc",
        "module_emission_recalc",
        "unit_sync",
    ],
)
async def test_dispatch_job_routes_every_known_job_type_through_run_job(job_type):
    """All Plan 310-C job_types take the same path — there is no
    job_type-specific branching in the poller anymore.
    """
    job = _make_job(42, job_type)
    with patch("app.tasks._poller.run_job", new_callable=AsyncMock) as mock_run:
        await dispatch_job(job, "test-pod")
    mock_run.assert_awaited_once_with(42)


@pytest.mark.asyncio
async def test_dispatch_job_skips_when_id_missing():
    """A job row with no id must NOT crash the poller; just skip and
    log a warning.
    """
    job = _make_job(None, "csv_ingest")
    with patch("app.tasks._poller.run_job", new_callable=AsyncMock) as mock_run:
        await dispatch_job(job, "test-pod")
    mock_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_job_does_not_redispatch_while_in_flight():
    """A job still NOT_STARTED (e.g. queued behind MAX_CONCURRENT_JOBS or a
    pooled connection) keeps matching the poller's pending-jobs query every
    sweep. ``schedule_job`` must not fire a second ``dispatch_job`` for the
    same job_id while an earlier dispatch hasn't resolved yet — otherwise a
    slow claim turns one job into an ever-growing pile of redundant tasks.
    """
    _IN_FLIGHT_JOB_IDS.clear()
    job = _make_job(7, "csv_ingest")

    started = asyncio.Event()
    release = asyncio.Event()

    async def _slow_dispatch(_job, _pod_id):
        started.set()
        await release.wait()

    with patch(
        "app.tasks._poller.dispatch_job", new=AsyncMock(side_effect=_slow_dispatch)
    ) as mock_dispatch:
        schedule_job(job, "test-pod")
        await started.wait()

        # Second sweep, same still-pending job — must be a no-op.
        schedule_job(job, "test-pod")
        await asyncio.sleep(0)

        assert mock_dispatch.await_count == 1
        assert 7 in _IN_FLIGHT_JOB_IDS

        release.set()
        # Let the first dispatch's task finish and its done-callback fire.
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    assert 7 not in _IN_FLIGHT_JOB_IDS

    # Once resolved, a later sweep for the same job_id can dispatch again.
    with patch(
        "app.tasks._poller.dispatch_job", new_callable=AsyncMock
    ) as mock_dispatch_again:
        schedule_job(job, "test-pod")
        await asyncio.sleep(0)
        mock_dispatch_again.assert_awaited_once()
