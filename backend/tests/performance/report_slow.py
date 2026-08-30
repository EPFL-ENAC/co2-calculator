"""Scan locust stats CSVs for endpoints whose p95 exceeds a threshold.

Usage::

    uv run python -m tests.performance.report_slow [--ms 1000] [reports_dir]

Reads every ``*_stats.csv`` a `make perf-load` / `make perf-sweep` run wrote
and prints one line per (stage, endpoint) over budget, worst first.
"""

import argparse
import csv
import sys
from pathlib import Path


def over_budget(stats_csv: Path, threshold_ms: float) -> list[tuple[float, str, str]]:
    rows = []
    with stats_csv.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("Name") in ("", "Aggregated"):
                continue
            p95 = float(row.get("95%") or 0)
            if p95 > threshold_ms:
                stage = stats_csv.name.removesuffix("_stats.csv")
                rows.append((p95, stage, f"{row['Type']} {row['Name']}"))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports_dir", nargs="?", default="tests/performance/reports")
    parser.add_argument("--ms", type=float, default=1000)
    args = parser.parse_args()

    files = sorted(Path(args.reports_dir).glob("*_stats.csv"))
    if not files:
        print(f"no *_stats.csv under {args.reports_dir} — run make perf-load first")
        return 1

    offenders: list[tuple[float, str, str]] = []
    for stats_csv in files:
        offenders.extend(over_budget(stats_csv, args.ms))

    if not offenders:
        print(f"all endpoints under {args.ms:.0f}ms p95 across {len(files)} stage(s)")
        return 0

    print(f"endpoints over {args.ms:.0f}ms p95:\n")
    for p95, stage, endpoint in sorted(offenders, reverse=True):
        print(f"  {p95:>8.0f}ms  {stage:<24} {endpoint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
