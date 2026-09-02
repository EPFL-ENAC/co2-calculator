#!/usr/bin/env python3
"""Find data entries that never received emissions (#2531 dedup bug fallout).

Read-only. Detects the fallout of the `EMISSION_RECALC_DEDUP` scoping bug:
between `a6dd48692` (2026-06-12) and the fix in PR #2541, two concurrent
uploads to the same `(module_type, data_entry_type, year)` in DIFFERENT
units collapsed — the second upload's `emission_recalc` child was skipped
as a duplicate, the pipeline reported success, and those rows never got
`data_entry_emissions`. Silently wrong totals, invisible from the UI.

The signature this looks for is deliberately narrow. A whole
`(carbon_report_module, data_entry_type)` group with **zero** emissions is
what a skipped recalc child looks like, because the child covers exactly
that scope. Groups where only *some* entries lack emissions are a
different failure and are reported separately rather than mixed in.

False positives are suppressed by only considering data entry types that
produce emissions *somewhere* in this database — some types legitimately
resolve to no emission leaf, and flagging those would bury the real hits.

Usage::

    uv run python -m scripts.check_missing_emissions
    uv run python -m scripts.check_missing_emissions --dsn postgresql://...
    uv run python -m scripts.check_missing_emissions --since 2026-06-12

Point it at STAGE or PROD — those hold real data. Run it before the next
release; the fix stops new damage but repairs nothing already written.
"""

import argparse
import asyncio
import sys
from datetime import datetime

import asyncpg

from app.core.config import get_settings

# The commit that pinned carbon_report_module_ids onto the recalc child
# without updating the dedup key.
BUG_INTRODUCED = "2026-06-12"

FULLY_MISSING_SQL = """
WITH emitting_types AS (
    SELECT DISTINCT de.data_entry_type_id
    FROM data_entries de
    JOIN data_entry_emissions dee ON dee.data_entry_id = de.id
),
per_group AS (
    SELECT
        u.institutional_id,
        u.name AS unit_name,
        cr.year,
        crm.module_type_id,
        de.data_entry_type_id,
        crm.id AS carbon_report_module_id,
        COUNT(*) AS entries,
        COUNT(*) FILTER (WHERE e.data_entry_id IS NULL) AS missing
    FROM data_entries de
    JOIN carbon_report_modules crm ON crm.id = de.carbon_report_module_id
    JOIN carbon_reports cr ON cr.id = crm.carbon_report_id
    JOIN units u ON u.id = cr.unit_id
    LEFT JOIN LATERAL (
        SELECT 1 AS data_entry_id
        FROM data_entry_emissions dee
        WHERE dee.data_entry_id = de.id
        LIMIT 1
    ) e ON TRUE
    WHERE de.data_entry_type_id IN (SELECT data_entry_type_id FROM emitting_types)
      AND de.status <> 'REJECTED'::dataentrystatusenum
      AND de.created_at >= $1
    GROUP BY 1, 2, 3, 4, 5, 6
)
SELECT * FROM per_group
WHERE missing = entries
ORDER BY entries DESC
"""

PARTIAL_SQL = FULLY_MISSING_SQL.replace(
    "WHERE missing = entries", "WHERE missing > 0 AND missing < entries"
)


def _print_rows(rows: list, title: str) -> None:
    print(f"\n{title}: {len(rows)} group(s)")
    if not rows:
        return
    print(
        f"  {'unit':<12} {'name':<26} {'year':>5} {'mod':>4} "
        f"{'type':>5} {'module_id':>10} {'entries':>8}"
    )
    for r in rows[:60]:
        print(
            f"  {str(r['institutional_id'])[:12]:<12} {str(r['unit_name'])[:26]:<26} "
            f"{r['year']:>5} {r['module_type_id']:>4} {r['data_entry_type_id']:>5} "
            f"{r['carbon_report_module_id']:>10} {r['entries']:>8}"
        )
    if len(rows) > 60:
        print(f"  ... and {len(rows) - 60} more")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="target database (default: settings.DB_URL)")
    parser.add_argument(
        "--since",
        default=BUG_INTRODUCED,
        help=f"only entries created on/after this date (default {BUG_INTRODUCED}); "
        "pass 1970-01-01 to scan everything",
    )
    args = parser.parse_args()

    dsn = args.dsn or (get_settings().DB_URL or "")
    if not dsn:
        raise SystemExit("no DSN: pass --dsn or set DB_URL")
    dsn = dsn.replace("postgresql+psycopg", "postgresql").replace(
        "postgresql+asyncpg", "postgresql"
    )
    host = dsn.split("@")[-1].split("/")[0]
    print(f"database: {host}   entries created since: {args.since}")

    # data_entries.created_at is a naive TIMESTAMP (this schema mixes naive
    # and tz-aware columns), so pass a naive datetime or asyncpg refuses.
    since = datetime.strptime(args.since, "%Y-%m-%d")  # noqa: DTZ007

    conn = await asyncpg.connect(dsn)
    try:
        fully = await conn.fetch(FULLY_MISSING_SQL, since)
        partial = await conn.fetch(PARTIAL_SQL, since)
    finally:
        await conn.close()

    _print_rows(
        fully,
        "FULLY MISSING — whole (module, type) group has no emissions "
        "(the skipped-recalc signature)",
    )
    _print_rows(
        partial,
        "PARTIAL — some entries missing (a DIFFERENT failure; investigate "
        "separately, not dedup fallout)",
    )

    entries = sum(r["entries"] for r in fully)
    if fully:
        pairs = sorted({(r["module_type_id"], r["year"]) for r in fully})
        print(
            f"\n{entries} data entries across {len(fully)} group(s) carry no "
            f"emissions and should.\nAffected reports show totals that look "
            f"complete but are too low.\n\nRemediate per (module_type_id, year) "
            f"— {len(pairs)} call(s), each idempotent:"
        )
        for module_type_id, year in pairs[:20]:
            print(f"  POST /v1/sync/recalculate-emissions/{module_type_id}?year={year}")
        if len(pairs) > 20:
            print(f"  ... and {len(pairs) - 20} more")
        print(
            "\nRe-run this script afterwards; FULLY MISSING should be empty.\n"
            "Do this only AFTER PR #2541 is deployed, or a concurrent upload "
            "can recreate the gap."
        )
    else:
        print("\nNo fully-missing groups found in this window.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
