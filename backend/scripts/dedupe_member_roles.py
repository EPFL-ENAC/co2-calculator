#!/usr/bin/env python3
"""Report — and optionally clean — duplicate member roles (#2050 J4).

``uq_member_role_per_module`` allows one ``(carbon_report_module_id,
user_institutional_id, sius_code)`` per member row. A module is already scoped
to one (unit, year, module type), so that key is the unit/year key. Run this
against an environment **before** deploying the migration that creates the
index: the migration refuses to run while duplicates exist.

Duplicates are not cosmetic. Module stats sum FTE across member rows and every
row carries its own emissions, so a duplicate has been inflating that unit's
published total for as long as it has existed.

Usage::

    uv run python -m scripts.dedupe_member_roles              # report only
    uv run python -m scripts.dedupe_member_roles --fix        # delete safe dupes
    uv run python -m scripts.dedupe_member_roles --fix --yes  # no confirmation

``--fix`` only ever deletes rows in a group whose payload is **identical** to
the row it keeps (lowest id wins, so provenance stays with the oldest). A group
whose rows differ — a different FTE, a different name — is reported and left
alone: choosing which one is real changes a published number, and that is a
decision for a maintainer, not for a script.
"""

import argparse
import asyncio
import sys

from dotenv import load_dotenv
from sqlalchemy import text

from app.db import engine
from app.models.data_entry import DataEntryTypeEnum

load_dotenv()

_GROUPS = text(
    """
    SELECT carbon_report_module_id,
           data ->> 'user_institutional_id' AS user_institutional_id,
           data ->> 'sius_code' AS sius_code,
           count(*) AS row_count,
           array_agg(id ORDER BY id) AS ids
    FROM data_entries
    WHERE data_entry_type_id = :member_type
      AND data ->> 'user_institutional_id' IS NOT NULL
    GROUP BY 1, 2, 3
    HAVING count(*) > 1
    ORDER BY count(*) DESC, 1, 2, 3
    """
)

# Compared without the note field: an operator-entered note differing between
# two otherwise identical rows should not block an obviously safe merge. The
# ::jsonb cast is required — data is a JSON column, and - is jsonb-only.
_PAYLOADS = text(
    """
    SELECT id,
           data::jsonb - 'note' AS payload,
           (SELECT count(*) FROM data_entry_emissions e
             WHERE e.data_entry_id = d.id) AS emission_rows
    FROM data_entries d
    WHERE id = ANY(:ids)
    ORDER BY id
    """
)

_DELETE_EMISSIONS = text(
    "DELETE FROM data_entry_emissions WHERE data_entry_id = ANY(:ids)"
)
_DELETE_ENTRIES = text("DELETE FROM data_entries WHERE id = ANY(:ids)")


async def _classify(conn) -> tuple[list[dict], list[dict]]:
    """Split duplicate groups into identical-payload and differing."""
    groups = (
        await conn.execute(_GROUPS, {"member_type": DataEntryTypeEnum.member.value})
    ).all()
    identical: list[dict] = []
    differing: list[dict] = []
    for group in groups:
        rows = (await conn.execute(_PAYLOADS, {"ids": list(group.ids)})).all()
        payloads = {str(row.payload) for row in rows}
        entry = {
            "module": group.carbon_report_module_id,
            "user_institutional_id": group.user_institutional_id,
            "sius_code": group.sius_code,
            "keep": rows[0].id,
            "drop": [row.id for row in rows[1:]],
            "emission_rows": sum(row.emission_rows for row in rows[1:]),
        }
        (identical if len(payloads) == 1 else differing).append(entry)
    return identical, differing


def _report(identical: list[dict], differing: list[dict]) -> None:
    if not identical and not differing:
        print("No duplicate member roles. The index can be created.")
        return
    if identical:
        print(f"\n{len(identical)} duplicate group(s) with an identical payload:")
        for group in identical:
            print(
                f"  module={group['module']} "
                f"user_institutional_id={group['user_institutional_id']!r} "
                f"sius_code={group['sius_code']!r} "
                f"keep id={group['keep']} drop={group['drop']} "
                f"({group['emission_rows']} emission row(s) go with them)"
            )
        print("  → --fix deletes these.")
    if differing:
        print(f"\n{len(differing)} duplicate group(s) whose rows DIFFER:")
        for group in differing:
            print(
                f"  module={group['module']} "
                f"user_institutional_id={group['user_institutional_id']!r} "
                f"sius_code={group['sius_code']!r} "
                f"ids={[group['keep'], *group['drop']]}"
            )
        print(
            "  → left alone on purpose: picking one changes a published total.\n"
            "    Decide per group, then re-run."
        )


async def main(fix: bool, assume_yes: bool) -> int:
    async with engine.connect() as conn:
        identical, differing = await _classify(conn)
        _report(identical, differing)

        if not fix:
            return 1 if (identical or differing) else 0
        if not identical:
            print("\nNothing safe to delete.")
            return 1 if differing else 0

        drop_ids = [entry_id for group in identical for entry_id in group["drop"]]
        if not assume_yes:
            print(f"\nDelete {len(drop_ids)} duplicate row(s) and their emissions?")
            if input("Type 'yes' to proceed: ").strip() != "yes":
                print("Aborted.")
                return 1

        # The reads above already autobegan this connection's transaction, so
        # the deletes join it and one commit ends it — which also means they
        # act on exactly the rows the report classified, with no window in
        # between for the data to change under us.
        await conn.execute(_DELETE_EMISSIONS, {"ids": drop_ids})
        await conn.execute(_DELETE_ENTRIES, {"ids": drop_ids})
        await conn.commit()
        print(f"Deleted {len(drop_ids)} duplicate member row(s).")
        print(
            "Recompute the affected modules' stats (admin recompute-stats) so "
            "their totals stop reflecting the deleted rows."
        )
        return 1 if differing else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="delete duplicates whose payload is identical to the kept row",
    )
    parser.add_argument(
        "--yes", action="store_true", help="skip the confirmation prompt"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(fix=args.fix, assume_yes=args.yes)))
