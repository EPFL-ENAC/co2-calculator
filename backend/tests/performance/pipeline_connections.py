"""Measure how many DB connections a CSV pipeline really holds (#2854).

The connection-budget doc says "3 per running job" and "a backend at rest
holds 2"; both were estimates.  This samples ``pg_stat_activity`` on the
local Postgres every ``--interval`` seconds while one upload per module
type runs through upload → dispatch → poll, then joins the samples with
the pipeline's job rows to give, per job phase, the peak number of
connections that were **held** (state other than ``idle``: an idle row is
a pooled connection nobody is using, which is what ``pool_size`` keeps
open on purpose).

Server-side on purpose: the budget is about what Postgres and the bouncer
see, and the app's pool gauge cannot tell idle-in-pool from held.

    uv run python -m tests.performance.pipeline_connections \
        --host http://127.0.0.1:8010 --parallel 1

Prerequisites: local Docker Postgres in ``DB_URL``, ``make seed-data``,
``make perf-csvs``, and a backend started with ``RUN_BACKGROUND_POLLER=True``
(local DB only) so jobs run in that one process.  ``--parallel N`` uploads
the same CSV for N distinct units at once (raise ``MAX_CONCURRENT_JOBS``
on the backend to match) to check whether the per-job number is additive.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import requests

from app.core.config import get_settings
from app.models.data_entry import DataEntryTypeEnum
from tests.performance.perf_common import (
    CSV_BY_TYPE,
    CSV_DIR,
    JOB_TIMEOUT,
    POLL_INTERVAL,
    RESULT_ERROR,
    STATE_FINISHED,
    module_of,
    slug,
)

REPORTS = Path(__file__).parent / "reports"
ROLE = os.environ.get("PERF_ROLE", "calco2.user.principal")

# pg_stat_activity for the measured backend only: the app names every
# connection ``co2-<POD_ID>`` (#2689), so a second local backend on the
# same database is invisible to the sampler.
ACTIVITY_SQL = """
    select application_name, state
    from pg_stat_activity
    where datname = current_database()
      and application_name = %s
      and pid <> pg_backend_pid()
"""
JOBS_SQL = """
    select id, job_type, data_entry_type_id, started_at, finished_at, locked_by
    from data_ingestion_jobs
    where pipeline_id = %s
    order by id
"""


def sync_dsn() -> str:
    """The app's DB_URL as a plain libpq DSN (psycopg wants no +driver)."""
    url = get_settings().DB_URL
    if url is None:
        raise SystemExit("DB_URL is not set")
    for driver in ("+psycopg", "+asyncpg"):
        url = url.replace(driver, "")
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit(
            f"refusing to sample a non-local database: {url.split('@')[-1]}"
        )
    return url


@dataclass
class Sample:
    ts: float
    held: int
    idle: int


class ActivitySampler(threading.Thread):
    """Poll pg_stat_activity until stopped; one Sample per tick."""

    def __init__(self, dsn: str, interval: float, app_name: str) -> None:
        super().__init__(daemon=True)
        self._dsn = dsn
        self._interval = interval
        self._app_name = app_name
        self._stop = threading.Event()
        self.samples: list[Sample] = []

    def run(self) -> None:
        with psycopg.connect(
            self._dsn, application_name="pipeline-connections-sampler"
        ) as conn:
            while not self._stop.is_set():
                rows = conn.execute(ACTIVITY_SQL, (self._app_name,)).fetchall()
                conn.rollback()  # end the sampler's own transaction between ticks
                held = sum(1 for _, state in rows if state != "idle")
                idle = sum(1 for _, state in rows if state == "idle")
                self.samples.append(Sample(time.time(), held, idle))
                time.sleep(self._interval)

    def stop(self) -> None:
        self._stop.set()
        self.join(timeout=5)

    def between(self, start: float, end: float) -> list[int]:
        return [s.held for s in self.samples if start <= s.ts <= end]


@dataclass
class JobWindow:
    job_id: int
    job_type: str
    data_entry_type_id: int | None
    start: float
    end: float
    peak: int = 0
    median: float = 0.0


@dataclass
class PipelineRun:
    entry_type: DataEntryTypeEnum
    unit_id: int
    pipeline_id: str
    start: float
    end: float = 0.0
    jobs: list[JobWindow] = field(default_factory=list)
    peak: int = 0
    error: str = ""


class Client:
    """Minimal port of the locust CO2User bootstrap onto requests."""

    def __init__(self, host: str) -> None:
        self.host = host.rstrip("/")
        self.http = requests.Session()
        self.http.headers.update({"Sec-Fetch-Site": "none"})
        cookie = os.environ.get("PERF_AUTH_COOKIE", "")
        if cookie:
            self.http.cookies.set("auth_token", cookie)
        else:
            resp = self.http.get(
                f"{self.host}/v1/auth/login-test",
                params={"role": ROLE},
                allow_redirects=False,
            )
            if resp.status_code != 302:
                raise SystemExit(
                    f"login-test returned {resp.status_code}: DEBUG build needed"
                )
        session = self.http.get(f"{self.host}/v1/session").json()
        self.years = [y["year"] for y in session.get("configured_years", [])]
        self.unit_ids = [u["id"] for u in session.get("units", [])]
        if not self.unit_ids:
            self.unit_ids = [
                u["id"] for u in self.http.get(f"{self.host}/v1/units").json()
            ]
        # A local seed may have carbon reports without a year configuration;
        # PERF_YEAR names the year to upload into in that case.
        forced_year = os.environ.get("PERF_YEAR", "")
        if forced_year:
            self.years = [int(forced_year)]
        if not self.unit_ids or not self.years:
            raise SystemExit(
                f"no units ({self.unit_ids}) or years ({self.years}) for {ROLE}; "
                "the login-test principal needs units 13032-13035 to exist "
                "(make perf-seed maps them), or set PERF_YEAR"
            )

    def module_id(self, unit_id: int, year: int, entry_type: DataEntryTypeEnum) -> int:
        report = self.http.get(
            f"{self.host}/v1/carbon-reports/unit/{unit_id}/year/{year}/"
        )
        report.raise_for_status()
        module = self.http.get(
            f"{self.host}/v1/carbon-reports/{report.json()['id']}/modules/"
            f"{slug(module_of(entry_type))}"
        )
        module.raise_for_status()
        return module.json()["carbon_report_module_id"]

    def dispatch(self, unit_id: int, year: int, entry_type: DataEntryTypeEnum) -> str:
        csv_path = CSV_DIR / CSV_BY_TYPE[entry_type]
        module_id = self.module_id(unit_id, year, entry_type)
        with csv_path.open("rb") as handle:
            uploaded = self.http.post(
                f"{self.host}/v1/files/temp-upload",
                files={"files": (csv_path.name, handle, "text/csv")},
            )
        uploaded.raise_for_status()
        dispatched = self.http.post(
            f"{self.host}/v1/sync/dispatch",
            json={
                "ingestion_method": 1,
                "target_type": 0,
                "year": year,
                "filters": {},
                "file_path": uploaded.json()[0]["path"],
                "config": {
                    "carbon_report_module_id": module_id,
                    "module_type_id": int(module_of(entry_type)),
                    "data_entry_type_id": int(entry_type),
                },
            },
        )
        if dispatched.status_code >= 400:
            raise RuntimeError(f"dispatch failed: {dispatched.text[:200]}")
        return dispatched.json()["pipeline_id"]

    def finished(self, pipeline_id: str) -> str | None:
        """None while running; "" when every job succeeded; else the error."""
        jobs = (
            self.http.get(f"{self.host}/v1/sync/pipelines/{pipeline_id}")
            .json()
            .get("jobs", [])
        )
        if not jobs or not all(j.get("state") == STATE_FINISHED for j in jobs):
            return None
        failed = [j for j in jobs if j.get("result") == RESULT_ERROR]
        if failed:
            return f"{failed[0].get('job_type')}: {failed[0].get('status_message')}"
        return ""


def _epoch(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def job_windows(dsn: str, pipeline_id: str, pod_id: str) -> list[JobWindow]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(JOBS_SQL, (pipeline_id,)).fetchall()
    windows = []
    for job_id, job_type, det, started, finished, locked_by in rows:
        start, end = _epoch(started), _epoch(finished)
        if start is None or end is None:
            # A child that never ran (parent errored before the fan-out).
            continue
        if locked_by != pod_id:
            # Another backend on the same DB claimed it: its connections are
            # not in our samples, so this row would read as zero. Say so.
            print(
                f"WARNING job {job_id} ({job_type}) ran on {locked_by!r}, "
                f"not {pod_id!r}",
                file=sys.stderr,
            )
        windows.append(JobWindow(job_id, job_type, det, start, end))
    return windows


def wait_all(client: Client, runs: list[PipelineRun]) -> None:
    deadline = time.monotonic() + JOB_TIMEOUT
    pending = list(runs)
    while pending and time.monotonic() < deadline:
        for run in list(pending):
            outcome = client.finished(run.pipeline_id)
            if outcome is not None:
                run.end = time.time()
                run.error = outcome
                pending.remove(run)
        time.sleep(POLL_INTERVAL)
    if pending:
        raise TimeoutError(
            f"{len(pending)} pipeline(s) not finished after {JOB_TIMEOUT}s"
        )


def attribute(
    sampler: ActivitySampler, dsn: str, pod_id: str, run: PipelineRun
) -> None:
    run.jobs = job_windows(dsn, run.pipeline_id, pod_id)
    for job in run.jobs:
        held = sampler.between(job.start, job.end) or [0]
        job.peak, job.median = max(held), statistics.median(held)
    run.peak = max(sampler.between(run.start, run.end) or [0])


def run_batch(
    client: Client,
    sampler: ActivitySampler,
    dsn: str,
    pod_id: str,
    entry_type: DataEntryTypeEnum,
    units: list[int],
    year: int,
) -> list[PipelineRun]:
    runs = []
    for unit_id in units:
        start = time.time()
        pipeline_id = client.dispatch(unit_id, year, entry_type)
        runs.append(PipelineRun(entry_type, unit_id, pipeline_id, start))
    wait_all(client, runs)
    time.sleep(1)  # let the last samples land
    for run in runs:
        attribute(sampler, dsn, pod_id, run)
    return runs


def phase_peaks(run: PipelineRun) -> dict[str, int]:
    peaks: dict[str, int] = {}
    for job in run.jobs:
        peaks[job.job_type] = max(peaks.get(job.job_type, 0), job.peak)
    return peaks


def print_table(baseline: int, batches: list[list[PipelineRun]], parallel: int) -> None:
    print(f"\nbaseline held connections at rest: {baseline}  (parallel={parallel})")
    print(
        f"{'entry type':28} {'ingest':>7} {'recalc':>7} {'aggreg':>7} "
        f"{'pipeline':>9} {'batch':>6} {'secs':>6}"
    )
    for runs in batches:
        batch_peak = max(r.peak for r in runs)
        for run in runs:
            peaks = phase_peaks(run)
            flag = f"  ERROR {run.error[:70]}" if run.error else ""
            print(
                f"{run.entry_type.name:28} "
                f"{peaks.get('csv_ingest', 0):7d} {peaks.get('emission_recalc', 0):7d} "
                f"{peaks.get('aggregation', 0):7d} {run.peak:9d} {batch_peak:6d} "
                f"{run.end - run.start:6.0f}{flag}"
            )


def write_csv(
    path: Path, sampler: ActivitySampler, batches: list[list[PipelineRun]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "entry_type",
                "unit_id",
                "pipeline_id",
                "job_id",
                "job_type",
                "det",
                "start",
                "end",
                "peak",
                "median",
            ]
        )
        for runs in batches:
            for run in runs:
                for job in run.jobs:
                    writer.writerow(
                        [
                            run.entry_type.name,
                            run.unit_id,
                            run.pipeline_id,
                            job.job_id,
                            job.job_type,
                            job.data_entry_type_id,
                            round(job.start, 3),
                            round(job.end, 3),
                            job.peak,
                            job.median,
                        ]
                    )
    samples_path = path.with_name(path.stem + "_samples.csv")
    with samples_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ts", "held", "idle"])
        for s in sampler.samples:
            writer.writerow([round(s.ts, 3), s.held, s.idle])
    print(f"\nwrote {path} and {samples_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="http://127.0.0.1:8010")
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="uploads per entry type at once, distinct units",
    )
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument(
        "--types",
        default="",
        help="comma-separated DataEntryTypeEnum names; default all with a perf CSV",
    )
    parser.add_argument("--out", default=str(REPORTS / "pipeline_connections.csv"))
    parser.add_argument(
        "--pod-id",
        default=os.environ.get("PERF_POD_ID", "perfconn"),
        help="HOSTNAME the measured backend was started with (samples co2-<pod-id>)",
    )
    args = parser.parse_args()

    wanted = [DataEntryTypeEnum[n] for n in args.types.split(",") if n] or list(
        CSV_BY_TYPE
    )
    types = [t for t in wanted if (CSV_DIR / CSV_BY_TYPE[t]).is_file()]
    missing = sorted(t.name for t in wanted if t not in types)
    if missing:
        print(
            f"skipping {len(missing)} type(s) without a perf CSV: {', '.join(missing)}",
            file=sys.stderr,
        )
    if not types:
        raise SystemExit(f"no perf CSVs in {CSV_DIR}: run `make perf-csvs`")

    dsn = sync_dsn()
    client = Client(args.host)
    if len(client.unit_ids) < args.parallel:
        raise SystemExit(
            f"--parallel {args.parallel} needs that many units; "
            f"have {len(client.unit_ids)}"
        )
    year = max(client.years)
    units = client.unit_ids[: args.parallel]

    sampler = ActivitySampler(dsn, args.interval, f"co2-{args.pod_id}")
    sampler.start()
    time.sleep(3)
    if not sampler.samples or max(s.held + s.idle for s in sampler.samples) == 0:
        raise SystemExit(
            f"no connections named co2-{args.pod_id}: "
            f"start the backend with HOSTNAME={args.pod_id}"
        )
    baseline = max(s.held for s in sampler.samples)

    batches: list[list[PipelineRun]] = []
    try:
        for entry_type in types:
            print(
                f"{entry_type.name}: {args.parallel} upload(s) on unit(s) {units} "
                f"year {year} ...",
                flush=True,
            )
            batches.append(
                run_batch(client, sampler, dsn, args.pod_id, entry_type, units, year)
            )
    finally:
        sampler.stop()

    print_table(baseline, batches, args.parallel)
    write_csv(Path(args.out), sampler, batches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
