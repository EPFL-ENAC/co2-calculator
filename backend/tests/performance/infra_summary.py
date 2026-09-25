"""Backend CPU milliseconds per request, per load stage (#2295).

Usage::

    GRAFANA_SESSION=... uv run python -m tests.performance.infra_summary \
        --reports DIR --grafana-url URL --datasource-uid UID --namespace NS \
        TAG [TAG ...]

The denominator is locust's own request count over the steady window
(``<tag>_stats_history.csv``); the numerator is backend CPU-seconds from
cAdvisor over the same window. OTel request counters are never used: they
export every ~60 s and read about half of locust's rate on 2026-09-24.
Writes ``<tag>_infra.json`` per tag and prints a markdown table.
"""

import argparse
import csv
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

SETTLE_S = 15
# cAdvisor scrape interval on the dev cluster; rate() needs two scrapes in
# its range, so a slice is the trailing 60 s, stepped every 30 s.
SCRAPE_S = 30
SLICE_S = 2 * SCRAPE_S
MIN_WINDOW_S = SLICE_S
BACKEND = "co2-calculator-backend"
AUTH_ERROR = "Grafana session expired or token invalid: export a fresh GRAFANA_SESSION"
COARSE = "coarse, OTel 60 s export"


@dataclass(frozen=True)
class HistoryRow:
    ts: int
    users: int
    requests: int
    failures: int


@dataclass(frozen=True)
class Window:
    start: int
    end: int
    requests: int
    failures: int

    @property
    def seconds(self) -> int:
        return self.end - self.start

    @property
    def rps(self) -> float:
        return self.requests / self.seconds


@dataclass(frozen=True)
class RunStats:
    """Whole-run aggregate from ``<tag>_stats.csv``, ramp-up included."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    failures: int


@dataclass(frozen=True)
class CpuStats:
    cpu_s: float
    ms_per_request: float
    slice_ms_per_request: list[float]
    slice_median_ms: float
    slice_p95_ms: float
    busiest_pod_cores: float
    mean_pod_cores: float
    imbalance: float
    throttled_share: float | None


@dataclass(frozen=True)
class FleetStats:
    hpa_replicas_min: float
    hpa_replicas_max: float
    db_server_connections_max: float  # coarse: OTel 60 s export
    pool_checked_out_max: float  # coarse: OTel 60 s export


@dataclass(frozen=True)
class Summary:
    tag: str
    window: Window
    run: RunStats
    cpu: CpuStats
    fleet: FleetStats


def read_history(path: Path) -> list[HistoryRow]:
    with path.open(newline="") as handle:
        return [
            HistoryRow(
                int(row["Timestamp"]),
                int(row["User Count"]),
                int(row["Total Request Count"]),
                int(row["Total Failure Count"]),
            )
            for row in csv.DictReader(handle)
            if row["Name"] == "Aggregated"
        ]


def steady_window(rows: list[HistoryRow], settle_s: int = SETTLE_S) -> Window:
    """Steady-load span of one stage: from the first row at the final user
    count plus ``settle_s``, to the last row with users still running.
    """
    # PERF_UI runs idle at 0 users after -t expires; those rows are not load.
    last = max((i for i, row in enumerate(rows) if row.users > 0), default=None)
    if last is None:
        raise ValueError("no history row with running users")
    end = rows[last]
    reached = next(row.ts for row in rows if row.users >= end.users)
    start = next((row for row in rows if row.ts >= reached + settle_s), end)
    if start.ts >= end.ts:
        raise ValueError(f"no rows {settle_s} s after reaching {end.users} users")
    return Window(
        start.ts, end.ts, end.requests - start.requests, end.failures - start.failures
    )


def requests_at(rows: list[HistoryRow], ts: int) -> int:
    """Cumulative locust requests at the last history row at or before ``ts``."""
    before = [row.requests for row in rows if row.ts <= ts]
    if not before:
        raise ValueError(f"no history row at or before {ts}")
    return before[-1]


def cpu_ms_per_request(cpu_s: float, requests: int) -> float:
    return 1000 * cpu_s / requests


def cores_by_step(per_pod: list[list[tuple[int, float]]]) -> list[tuple[int, float]]:
    """Fleet CPU (cores) at each Prometheus step, summed over pods."""
    totals: dict[int, float] = {}
    for series in per_pod:
        for ts, cores in series:
            totals[ts] = totals.get(ts, 0.0) + cores
    return sorted(totals.items())


def slice_ms_per_request(
    cores: list[tuple[int, float]], rows: list[HistoryRow], slice_s: int = SLICE_S
) -> list[float]:
    """CPU ms per request of each trailing ``slice_s`` slice ending at a
    Prometheus step: fleet CPU rate ÷ locust rps over that same slice.
    """
    return [
        cpu_ms_per_request(
            fleet * slice_s, requests_at(rows, ts) - requests_at(rows, ts - slice_s)
        )
        for ts, fleet in cores
    ]


def pod_cpu_stats(per_pod: list[list[tuple[int, float]]]) -> tuple[float, float]:
    """Busiest pod's peak CPU and the mean over every pod sample (cores)."""
    samples = [cores for series in per_pod for _, cores in series]
    return max(samples), statistics.fmean(samples)


def p95(values: list[float]) -> float:
    # Inclusive: never extrapolates past the largest of a handful of slices.
    return statistics.quantiles(values, n=20, method="inclusive")[18]


def read_run_stats(path: Path) -> RunStats:
    with path.open(newline="") as handle:
        row = next(r for r in csv.DictReader(handle) if r["Name"] == "Aggregated")
    return RunStats(
        float(row["50%"]),
        float(row["95%"]),
        float(row["99%"]),
        int(row["Failure Count"]),
    )


def checked_window(tag: str, rows: list[HistoryRow]) -> Window:
    window = steady_window(rows)
    print(
        f"{tag}: steady window {window.start}→{window.end} ({window.seconds} s), "
        f"{window.requests} requests, {window.failures} failures, "
        f"{window.rps:.1f} rps",
        file=sys.stderr,
    )
    if window.seconds < MIN_WINDOW_S:
        raise ValueError(
            f"{tag}: steady window {window.seconds} s < {MIN_WINDOW_S} s (two "
            f"{SCRAPE_S} s Prometheus scrapes); rerun the stage with PERF_TIME=3m"
        )
    return window


@dataclass(frozen=True)
class Prometheus:
    base_url: str
    headers: dict[str, str] = field(repr=False)

    def get(self, path: str, params: dict[str, str | int]) -> list[dict]:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            f"{self.base_url}/api/v1/{path}?{query}", headers=self.headers
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(AUTH_ERROR) from None
            detail = exc.read()[:300].decode(errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {params['query']}: {detail}")
        if body.get("status") != "success":
            raise RuntimeError(f"Prometheus error for {params['query']}: {body}")
        return body["data"]["result"]

    def scalar(self, query: str, at: int) -> float:
        result = self.get("query", {"query": query, "time": at})
        if len(result) != 1:
            raise RuntimeError(f"expected 1 series, got {len(result)}: {query}")
        return float(result[0]["value"][1])

    def matrix(
        self, query: str, start: int, end: int, step: int
    ) -> list[list[tuple[int, float]]]:
        params: dict[str, str | int] = {
            "query": query,
            "start": start,
            "end": end,
            "step": step,
        }
        result = self.get("query_range", params)
        if not result:
            raise RuntimeError(f"no series between {start} and {end}: {query}")
        return [[(int(t), float(v)) for t, v in s["values"]] for s in result]


def throttled_share(
    prom: Prometheus, selector: str, span: str, at: int
) -> float | None:
    """Throttled / total CFS periods; None when the container has no CPU limit.

    cAdvisor emits CFS counters only under a quota, and the usage query has
    already proven this selector matches, so no series means no limit.
    """
    periods_query = f"sum(increase(container_cpu_cfs_periods_total{selector}{span}))"
    periods = prom.get("query", {"query": periods_query, "time": at})
    if not periods or float(periods[0]["value"][1]) == 0:
        return None
    throttled = prom.scalar(
        f"sum(increase(container_cpu_cfs_throttled_periods_total{selector}{span}))",
        at,
    )
    return throttled / float(periods[0]["value"][1])


def cpu_stats(
    prom: Prometheus, namespace: str, window: Window, rows: list[HistoryRow]
) -> CpuStats:
    selector = f'{{namespace="{namespace}",container="backend"}}'
    span = f"[{window.seconds}s]"
    usage = f"container_cpu_usage_seconds_total{selector}"
    cpu_s = prom.scalar(f"sum(increase({usage}{span}))", window.end)
    per_pod = prom.matrix(
        f"sum by (pod) (rate({usage}[{SLICE_S}s]))",
        window.start + SLICE_S,
        window.end,
        SCRAPE_S,
    )
    slices = slice_ms_per_request(cores_by_step(per_pod), rows)
    busiest, mean = pod_cpu_stats(per_pod)
    return CpuStats(
        cpu_s=cpu_s,
        ms_per_request=cpu_ms_per_request(cpu_s, window.requests),
        slice_ms_per_request=slices,
        slice_median_ms=statistics.median(slices),
        slice_p95_ms=p95(slices),
        busiest_pod_cores=busiest,
        mean_pod_cores=mean,
        imbalance=busiest / mean,
        throttled_share=throttled_share(prom, selector, span, window.end),
    )


def fleet_stats(prom: Prometheus, namespace: str, window: Window) -> FleetStats:
    hpa = (
        "kube_horizontalpodautoscaler_status_current_replicas"
        f'{{namespace="{namespace}",horizontalpodautoscaler="{BACKEND}"}}'
    )
    server = f'db_server_connections{{namespace="{namespace}"}}'
    # The worker's pool is not the API's: keep backend pods only.
    pool = (
        f'db_pool_connections{{namespace="{namespace}",state="checked_out",'
        f'k8s_pod_name=~"{BACKEND}-.*"}}'
    )
    span = f"[{window.seconds}s]"
    return FleetStats(
        hpa_replicas_min=prom.scalar(f"min(min_over_time({hpa}{span}))", window.end),
        hpa_replicas_max=prom.scalar(f"max(max_over_time({hpa}{span}))", window.end),
        db_server_connections_max=prom.scalar(
            f"max(max_over_time({server}{span}))", window.end
        ),
        pool_checked_out_max=prom.scalar(
            f"max(max_over_time({pool}{span}))", window.end
        ),
    )


def _share(value: float | None) -> str:
    if value is None:
        return "no CPU limit (no CFS periods)"
    return f"{value:.1%}"


ROWS: list[tuple[str, Callable[[Summary], str]]] = [
    ("steady window (s)", lambda s: f"{s.window.seconds}"),
    ("requests in window (locust)", lambda s: f"{s.window.requests}"),
    ("failures in window (locust)", lambda s: f"{s.window.failures}"),
    ("rps in window (locust)", lambda s: f"{s.window.rps:.1f}"),
    (
        "p50 / p95 / p99 ms (whole run)",
        lambda s: f"{s.run.p50_ms:.0f} / {s.run.p95_ms:.0f} / {s.run.p99_ms:.0f}",
    ),
    ("failures (whole run)", lambda s: f"{s.run.failures}"),
    ("backend CPU-seconds (cAdvisor)", lambda s: f"{s.cpu.cpu_s:.1f}"),
    ("**CPU ms / request**", lambda s: f"**{s.cpu.ms_per_request:.1f}**"),
    ("slice stability: median ms/req", lambda s: f"{s.cpu.slice_median_ms:.1f}"),
    ("slice stability: p95 ms/req", lambda s: f"{s.cpu.slice_p95_ms:.1f}"),
    ("busiest pod CPU max (cores)", lambda s: f"{s.cpu.busiest_pod_cores:.2f}"),
    ("mean pod CPU (cores)", lambda s: f"{s.cpu.mean_pod_cores:.2f}"),
    ("imbalance (busiest / mean)", lambda s: f"{s.cpu.imbalance:.2f}"),
    ("CPU throttled share", lambda s: _share(s.cpu.throttled_share)),
    (
        "HPA replicas min–max",
        lambda s: f"{s.fleet.hpa_replicas_min:.0f}–{s.fleet.hpa_replicas_max:.0f}",
    ),
    (
        f"DB server connections max ({COARSE})",
        lambda s: f"{s.fleet.db_server_connections_max:.0f}",
    ),
    (
        f"pod pool checked_out max ({COARSE})",
        lambda s: f"{s.fleet.pool_checked_out_max:.0f}",
    ),
]


def render_table(summaries: list[Summary]) -> str:
    lines = [
        "| metric | " + " | ".join(s.tag for s in summaries) + " |",
        "| --- |" + " ---: |" * len(summaries),
    ]
    lines += [
        f"| {label} | " + " | ".join(cell(s) for s in summaries) + " |"
        for label, cell in ROWS
    ]
    lines.append(
        f"\nSlice stability: spread of CPU ms/request across {SLICE_S} s slices "
        f"stepped every {SCRAPE_S} s. Not a per-request percentile."
    )
    return "\n".join(lines)


def write_json(reports: Path, summary: Summary) -> None:
    payload = asdict(summary)
    payload["window"] |= {"seconds": summary.window.seconds, "rps": summary.window.rps}
    path = reports / f"{summary.tag}_infra.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")


def auth_headers() -> dict[str, str]:
    token = os.environ.get("GRAFANA_TOKEN", "")
    session = os.environ.get("GRAFANA_SESSION", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    if session:
        return {"Cookie": f"grafana_session={session}"}
    raise SystemExit("export GRAFANA_SESSION (browser cookie) or GRAFANA_TOKEN")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tags", nargs="+")
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--grafana-url", required=True)
    parser.add_argument("--datasource-uid", required=True)
    parser.add_argument("--namespace", required=True)
    args = parser.parse_args()

    # Every window is checked before the first network call.
    rows = {t: read_history(args.reports / f"{t}_stats_history.csv") for t in args.tags}
    windows = {tag: checked_window(tag, rows[tag]) for tag in args.tags}
    prom = Prometheus(
        f"{args.grafana_url}/api/datasources/proxy/uid/{args.datasource_uid}",
        auth_headers(),
    )
    summaries = [
        Summary(
            tag=tag,
            window=windows[tag],
            run=read_run_stats(args.reports / f"{tag}_stats.csv"),
            cpu=cpu_stats(prom, args.namespace, windows[tag], rows[tag]),
            fleet=fleet_stats(prom, args.namespace, windows[tag]),
        )
        for tag in args.tags
    ]
    for summary in summaries:
        write_json(args.reports, summary)
    print(render_table(summaries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
