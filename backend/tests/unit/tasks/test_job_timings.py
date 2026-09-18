"""#2854 — queue wait and duration histograms per job type."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionResult
from app.tasks import _job_timings


def _job(created: datetime | None, started: datetime | None, job_type="csv_ingest"):
    job = MagicMock()
    job.created_at = created
    job.started_at = started
    job.job_type = job_type
    return job


def test_queue_wait_is_started_minus_created_labelled_by_job_type():
    created = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)
    job = _job(created, created + timedelta(seconds=326))
    with patch.object(_job_timings, "_queue_wait_seconds") as hist:
        assert _job_timings.record_queue_wait(job) == 326.0
    hist.record.assert_called_once_with(326.0, {"job_type": "csv_ingest"})


def test_queue_wait_treats_naive_stamps_as_utc():
    """The jobs table stores naive UTC; mixing naive and aware must not raise."""
    created = datetime(2026, 9, 18, 8, 0)
    job = _job(created, datetime(2026, 9, 18, 8, 0, 5, tzinfo=UTC))
    with patch.object(_job_timings, "_queue_wait_seconds") as hist:
        assert _job_timings.record_queue_wait(job) == 5.0
    hist.record.assert_called_once()


@pytest.mark.parametrize("created,started", [(None, None), (datetime.now(UTC), None)])
def test_queue_wait_records_nothing_without_both_stamps(created, started):
    with patch.object(_job_timings, "_queue_wait_seconds") as hist:
        assert _job_timings.record_queue_wait(_job(created, started)) == 0.0
    hist.record.assert_not_called()


def test_duration_is_monotonic_elapsed_labelled_by_type_and_result():
    claimed_at = time.monotonic() - 12.5
    with patch.object(_job_timings, "_duration_seconds") as hist:
        elapsed = _job_timings.record_duration(
            "aggregation", IngestionResult.SUCCESS, claimed_at
        )
    assert 12.5 <= elapsed < 13.5
    value, attrs = hist.record.call_args.args
    assert value == elapsed
    assert attrs == {"job_type": "aggregation", "result": "SUCCESS"}


def test_buckets_reach_minutes_not_just_the_otel_default_ten_seconds():
    """Stage's csv_ingest p95 is 376 s; the default buckets stop at 10 s and
    would put every real job in one bucket, making p95 meaningless.
    """
    bounds = _job_timings.JOB_SECONDS_BOUNDARIES
    assert bounds == sorted(bounds)
    assert bounds[0] <= 1 and 300 in bounds and bounds[-1] >= 3600
