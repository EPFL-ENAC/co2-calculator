"""Job queue-wait and duration histograms, per job type (#2854).

``created_at → started_at`` is queue wait: semaphore, poller latency, a
pod with no free slot. ``started_at → finished_at`` is the job itself,
lock waits included. Both existed only as columns nobody queried; a
p95 by job type in Grafana is what tells whether to add a worker, raise
``MAX_CONCURRENT_JOBS`` or leave the pod count alone (connection-budget
doc, "Sizing formula").

Boundaries are seconds up to an hour: the OTel defaults top out at 10 s
and a csv_ingest or aggregation regularly runs minutes.
"""

import time
from datetime import UTC, datetime

from opentelemetry.metrics import get_meter

from app.models.data_ingestion import DataIngestionJob, IngestionResult

# 1 s to 1 h; anything above lands in the +Inf bucket, which is itself
# the signal (a job running longer than an hour is stuck or huge).
JOB_SECONDS_BOUNDARIES = [1, 2, 5, 10, 30, 60, 120, 300, 600, 1200, 1800, 3600]

_queue_wait_seconds = get_meter(__name__).create_histogram(
    "job.queue_wait_seconds",
    unit="s",
    description=(
        "created_at to started_at per job: time a job sat NOT_STARTED before a "
        "pod claimed it. Rising with worker CPU saturated: add a worker; "
        "rising with CPU idle: raise MAX_CONCURRENT_JOBS."
    ),
    explicit_bucket_boundaries_advisory=JOB_SECONDS_BOUNDARIES,
)
_duration_seconds = get_meter(__name__).create_histogram(
    "job.duration_seconds",
    unit="s",
    description=(
        "claim to FINISHED per job, lock waits included; labelled by job_type "
        "and result."
    ),
    explicit_bucket_boundaries_advisory=JOB_SECONDS_BOUNDARIES,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def record_queue_wait(job: DataIngestionJob) -> float:
    """Record how long ``job`` waited to be claimed; returns the seconds.

    Called right after the post-claim re-fetch, when ``started_at`` is
    authoritative. A row without both stamps records nothing: the
    columns are the source, and a missing one is not a zero wait.
    """
    created, started = job.created_at, job.started_at
    if not isinstance(created, datetime) or not isinstance(started, datetime):
        return 0.0
    waited = (_as_utc(started) - _as_utc(created)).total_seconds()
    waited = max(waited, 0.0)
    _queue_wait_seconds.record(waited, {"job_type": job.job_type or "unknown"})
    return waited


def record_duration(job_type: str, result: IngestionResult, claimed_at: float) -> float:
    """Record wall time from claim to FINISHED; ``claimed_at`` is monotonic."""
    elapsed = max(time.monotonic() - claimed_at, 0.0)
    _duration_seconds.record(elapsed, {"job_type": job_type, "result": result.name})
    return elapsed
