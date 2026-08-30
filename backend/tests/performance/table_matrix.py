"""Latency matrix for the table endpoint (#2295, table-pagination plan).

Sweeps GET /v1/carbon-reports/{id}/modules/{slug}/{sub} for every
calculator submodule: limit {20,100,500,1000} × every sortable column ×
asc/desc at page=2, plus filter search, deep pagination (last page),
single-item GETs, and the module chart companions.

Usage::

    uv run python -m tests.performance.table_matrix --user USR000001
    uv run python -m tests.performance.table_matrix --host https://x --cookie "$TOK"

Sort columns are discovered from each handler's ``sort_map`` (the same
source the repo validates against) plus the computed columns the repo
layers on. Auth: mint a cookie for a seeded DEFAULT user (--user, local
only — needs the target's JWT_HMAC_KEY) or pass --cookie.
"""

import argparse
import csv
import math
import statistics
import sys
import time
from pathlib import Path

import requests

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES
from tests.performance.perf_common import (
    TABLE_PAGE_LIMITS as LIMITS,
)
from tests.performance.perf_common import (
    mint_auth_cookie,
    module_of,
    slug,
    sort_columns,
)

OVER_BUDGET_MS = 1000
WARN_MS = 400

CALCULATOR_TYPES = [
    t
    for types in MODULE_TYPE_TO_DATA_ENTRY_TYPES.values()
    for t in types
    if not t.is_planner_kind
]


class Runner:
    def __init__(self, host: str, cookie: str, year: int, repeat: int):
        self.session = requests.Session()
        self.session.cookies.set("auth_token", cookie)
        self.session.headers["Sec-Fetch-Site"] = "none"
        self.host = host.rstrip("/")
        self.year = year
        self.repeat = repeat
        self.rows: list[dict] = []

    def timed_get(self, kind: str, entry_type, column, order, limit, page, url, params):
        timings = []
        response = None
        for _ in range(self.repeat):
            start = time.perf_counter()
            response = self.session.get(self.host + url, params=params, timeout=120)
            timings.append((time.perf_counter() - start) * 1000)
        body = {}
        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
        self.rows.append(
            {
                "kind": kind,
                "submodule": entry_type.name if entry_type else "",
                "column": column,
                "order": order,
                "limit": limit,
                "page": page,
                "rows_returned": len(body.get("items", []))
                if isinstance(body, dict)
                else "",
                "response_bytes": len(response.content),
                "status": response.status_code,
                "ms": round(statistics.median(timings), 1),
            }
        )
        return response, body

    def run_submodule(self, report_id: int, entry_type: DataEntryTypeEnum):
        module_slug = slug(module_of(entry_type))
        url = f"/v1/carbon-reports/{report_id}/modules/{module_slug}/{entry_type.name}"

        count = 0
        first_item_id = None
        for limit in LIMITS:
            for column in sort_columns(entry_type):
                for order in ("asc", "desc"):
                    _, body = self.timed_get(
                        "sort",
                        entry_type,
                        column,
                        order,
                        limit,
                        2,
                        url,
                        {
                            "page": 2,
                            "limit": limit,
                            "sort_by": column,
                            "sort_order": order,
                        },
                    )
                    count = body.get("count", count) or count
            # Filter search: the table's search box path.
            self.timed_get(
                "filter",
                entry_type,
                "",
                "asc",
                limit,
                1,
                url,
                {"page": 1, "limit": limit, "filter": "er"},
            )

        # Deep pagination: the last page at small page sizes.
        for limit in (20, 100):
            last_page = max(1, math.ceil((count or 1) / limit))
            self.timed_get(
                "deep-page",
                entry_type,
                "id",
                "asc",
                limit,
                last_page,
                url,
                {"page": last_page, "limit": limit},
            )

        # Single-item GET (row expand).
        _, body = self.timed_get(
            "page1", entry_type, "id", "asc", 20, 1, url, {"page": 1, "limit": 20}
        )
        items = body.get("items") or []
        if items and isinstance(items[0], dict):
            first_item_id = items[0].get("id")
        if first_item_id is not None:
            self.timed_get(
                "item", entry_type, "", "", 1, 1, f"{url}/{first_item_id}", {}
            )

        # Unknown sort key must be a 4xx, never a 500 (user-triggerable).
        response, _ = self.timed_get(
            "bad-sort",
            entry_type,
            "__nope__",
            "asc",
            20,
            1,
            url,
            {"page": 1, "limit": 20, "sort_by": "__nope__"},
        )
        if response.status_code >= 500:
            print(f"BUG: unknown sort_by returns {response.status_code} on {url}")

    def run_module_charts(self, report_id: int, module_slug: str):
        for endpoint in ("stats-by-class", "top-class-breakdown"):
            self.timed_get(
                f"chart:{endpoint}",
                None,
                "",
                "",
                0,
                0,
                f"/v1/carbon-reports/{report_id}/modules/{module_slug}/{endpoint}",
                {},
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://127.0.0.1:8010")
    parser.add_argument("--user", help="seeded institutional_id to mint a cookie for")
    parser.add_argument("--cookie", help="raw auth_token value (remote hosts)")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--out", default="tests/performance/reports/table_matrix.csv")
    args = parser.parse_args()

    if not args.user and not args.cookie:
        raise SystemExit("pass --user (local) or --cookie (remote)")
    cookie = args.cookie or mint_auth_cookie(args.user)
    runner = Runner(args.host, cookie, args.year, args.repeat)

    session = runner.session.get(runner.host + "/v1/session", timeout=30).json()
    units = session.get("units") or []
    if not units:
        raise SystemExit(f"user has no units — session: {str(session)[:200]}")
    unit_id = units[0]["id"]
    report = runner.session.get(
        f"{runner.host}/v1/carbon-reports/unit/{unit_id}/year/{args.year}/", timeout=30
    ).json()
    report_id = report["id"]
    print(f"unit={unit_id} year={args.year} report={report_id}")

    for entry_type in CALCULATOR_TYPES:
        print(f"  {entry_type.name} ...")
        runner.run_submodule(report_id, entry_type)
    for module_slug in {slug(module_of(t)) for t in CALCULATOR_TYPES}:
        runner.run_module_charts(report_id, module_slug)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runner.rows[0].keys()))
        writer.writeheader()
        writer.writerows(runner.rows)

    failures = [r for r in runner.rows if int(r["status"]) >= 400]
    # bad-sort rows are EXPECTED to be 4xx — only flag them when 5xx.
    failures = [
        r for r in failures if r["kind"] != "bad-sort" or int(r["status"]) >= 500
    ]
    slow = sorted(
        (r for r in runner.rows if r["ms"] > WARN_MS and int(r["status"]) < 400),
        key=lambda r: -r["ms"],
    )
    print(f"\n{len(runner.rows)} requests -> {out}")
    if failures:
        print(f"\n{len(failures)} unexpected non-2xx:")
        for r in failures[:20]:
            print(f"  {r['status']}  {r['kind']:10} {r['submodule']:30} {r['column']}")
    if slow:
        print(f"\ncombos over {WARN_MS}ms (>{OVER_BUDGET_MS}ms marked !):")
        for r in slow[:40]:
            marker = "!" if r["ms"] > OVER_BUDGET_MS else " "
            print(
                f" {marker}{r['ms']:>8.0f}ms  {r['kind']:10} {r['submodule']:30} "
                f"{r['column']:28} {r['order']:4} limit={r['limit']} page={r['page']}"
            )
    if not slow:
        print(f"no combo over {WARN_MS}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
