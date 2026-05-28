#!/usr/bin/env python3
"""Add ``origin_country_code`` / ``destination_country_code`` columns to
train CSV seed + fixture files (issue #1183, Phase 1).

The columns are inserted directly after their corresponding ``*_name``
columns and every existing row is defaulted to ``CH`` (the project's
data center of mass — see ``ProfessionalTravelTrainModuleHandler.
enrich_csv_row`` which already falls back to ``CH`` when the column is
absent or blank).

Targets (per issue #1183):
  - ``backend/seed_data/travel_trains_data.csv`` (gitignored, dev-only)
  - ``backend/seed_data/travel_trains_test.csv`` (gitignored, dev-only)

Also covers the committed CI-safe trimmed fixtures so the visible
ingest contract evolves alongside the seed data:
  - ``backend/tests/fixtures/csv/travel_trains_smoke.csv``
  - ``backend/tests/fixtures/csv/travel_trains_unknown_station.csv``

Idempotent: files that already carry both columns are left untouched.
Missing seed CSVs (typical on a fresh clone — ``seed_data/`` is
gitignored) are skipped with a printed note rather than treated as an
error.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

DEFAULT_COUNTRY_CODE = "CH"

ROLES = ("origin", "destination")

BACKEND_ROOT = Path(__file__).resolve().parent.parent

TARGET_CSVS: tuple[Path, ...] = (
    BACKEND_ROOT / "seed_data" / "travel_trains_data.csv",
    BACKEND_ROOT / "seed_data" / "travel_trains_test.csv",
    BACKEND_ROOT / "tests" / "fixtures" / "csv" / "travel_trains_smoke.csv",
    BACKEND_ROOT / "tests" / "fixtures" / "csv" / "travel_trains_unknown_station.csv",
)


def _new_header(header: list[str]) -> list[str]:
    """Return ``header`` with ``{role}_country_code`` inserted right
    after each ``{role}_name`` column. If the country_code column is
    already present elsewhere in the header it is left in place."""
    name_to_country = {f"{role}_name": f"{role}_country_code" for role in ROLES}
    result: list[str] = []
    for col in header:
        result.append(col)
        country_col = name_to_country.get(col)
        if country_col and country_col not in header:
            result.append(country_col)
    return result


def _augment_row(row: dict[str, str], header: list[str]) -> list[str]:
    """Render ``row`` in ``header`` order, filling new country_code
    columns with the project default."""
    out: list[str] = []
    for col in header:
        if col.endswith("_country_code") and not row.get(col):
            out.append(DEFAULT_COUNTRY_CODE)
        else:
            out.append(row.get(col, ""))
    return out


def _process_csv(path: Path) -> str:
    """Rewrite ``path`` in place. Returns a one-word status:
    ``"missing"``, ``"unchanged"``, or ``"updated"``."""
    if not path.exists():
        return "missing"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)
    if not rows:
        return "unchanged"
    header = rows[0]
    needed = [f"{role}_country_code" for role in ROLES]
    if all(col in header for col in needed):
        return "unchanged"
    new_header = _new_header(header)
    dict_rows = [dict(zip(header, row)) for row in rows[1:]]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(new_header)
        for row in dict_rows:
            writer.writerow(_augment_row(row, new_header))
    return "updated"


def main() -> int:
    statuses: dict[str, list[Path]] = {"updated": [], "unchanged": [], "missing": []}
    for path in TARGET_CSVS:
        statuses[_process_csv(path)].append(path)
    for label in ("updated", "unchanged", "missing"):
        for path in statuses[label]:
            try:
                shown = path.relative_to(BACKEND_ROOT.parent)
            except ValueError:
                shown = path
            print(f"{label:>9}: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
