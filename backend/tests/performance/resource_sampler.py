"""Samples backend + Postgres CPU/memory while a load stage runs (#2295).

`make perf-load` starts one sampler per stage and kills it when locust
exits, leaving `<tag>_resources.csv` rows of
(ts, backend_cpu_pct, backend_rss_mb, pg_cpu_pct, pg_mem_mb).

Summarize every stage into the capacity table (joined with the locust
stats CSVs):

    uv run python -m tests.performance.resource_sampler --summarize
"""

import argparse
import csv
import subprocess  # nosec B404 — ps/docker sampling of local processes
import sys
import time
from pathlib import Path

REPORTS = Path(__file__).parent / "reports"


def backend_usage() -> tuple[float, float]:
    """Sum CPU%% and RSS(MB) of the uvicorn app processes."""
    out = subprocess.run(  # nosec B603 B607
        ["ps", "-Ao", "%cpu,rss,command"], capture_output=True, text=True
    ).stdout
    cpu = rss_kb = 0.0
    for line in out.splitlines():
        if "uvicorn" in line and "app.main:app" in line:
            parts = line.split(None, 2)
            cpu += float(parts[0])
            rss_kb += float(parts[1])
    return cpu, rss_kb / 1024


def postgres_usage() -> tuple[float, float]:
    """CPU%% and memory(MB) of the postgres container via docker stats."""
    out = subprocess.run(  # nosec B603 B607
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.CPUPerc}} {{.MemUsage}}",
            "co2-calculator-postgres",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not out:
        return 0.0, 0.0
    cpu_str, mem_str = out.split()[0], out.split()[1]
    cpu = float(cpu_str.rstrip("%"))
    factor = {"KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0}
    for unit, mult in factor.items():
        if mem_str.endswith(unit):
            return cpu, float(mem_str[: -len(unit)]) * mult
    return cpu, 0.0


def sample(out_path: Path, interval: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["ts", "backend_cpu_pct", "backend_rss_mb", "pg_cpu_pct", "pg_mem_mb"]
        )
        while True:  # killed by perf-load when locust exits
            backend_cpu, backend_rss = backend_usage()
            pg_cpu, pg_mem = postgres_usage()
            writer.writerow(
                [
                    round(time.time(), 1),
                    round(backend_cpu, 1),
                    round(backend_rss, 1),
                    round(pg_cpu, 1),
                    round(pg_mem, 1),
                ]
            )
            handle.flush()
            time.sleep(interval)


def summarize(reports_dir: Path) -> int:
    """Capacity table: one row per stage that has both stats + resources."""
    rows = []
    for resources_csv in sorted(reports_dir.glob("*_resources.csv")):
        tag = resources_csv.name.removesuffix("_resources.csv")
        stats_csv = reports_dir / f"{tag}_stats.csv"
        if not stats_csv.exists():
            continue
        samples = list(csv.DictReader(resources_csv.open()))
        if not samples:
            continue

        def peak(key):
            return max(float(s[key]) for s in samples)

        agg = next(
            (r for r in csv.DictReader(stats_csv.open()) if r["Name"] == "Aggregated"),
            None,
        )
        if agg is None:
            continue
        rows.append(
            {
                "stage": tag,
                "requests": int(agg["Request Count"]),
                "fail_pct": round(
                    100 * int(agg["Failure Count"]) / max(1, int(agg["Request Count"])),
                    2,
                ),
                "rps": round(float(agg["Requests/s"]), 1),
                "p95_ms": agg["95%"],
                "backend_cpu_peak_pct": peak("backend_cpu_pct"),
                "backend_rss_peak_mb": peak("backend_rss_mb"),
                "pg_cpu_peak_pct": peak("pg_cpu_pct"),
                "pg_mem_peak_mb": peak("pg_mem_mb"),
            }
        )
    if not rows:
        print("no *_resources.csv with matching stats found")
        return 1
    headers = list(rows[0].keys())
    print(" | ".join(headers))
    print(" | ".join("---" for _ in headers))
    for row in rows:
        print(" | ".join(str(row[h]) for h in headers))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", nargs="?", help="csv to write samples into")
    parser.add_argument("--interval", type=float, default=3)
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--reports", default=str(REPORTS))
    args = parser.parse_args()

    if args.summarize:
        return summarize(Path(args.reports))
    if not args.out:
        raise SystemExit("pass an output csv or --summarize")
    sample(Path(args.out), args.interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
