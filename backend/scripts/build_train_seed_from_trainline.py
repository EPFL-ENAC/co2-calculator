#!/usr/bin/env python3
"""Build the train-station location seed from the trainline-eu ``stations.csv``.

Issue #1183: the train location seed is sourced from the open trainline-eu
dataset (https://github.com/trainline-eu/stations), which already carries an
ISO-2 ``country`` per station. This replaces the old name-only seed plus the
``CH``-backfill workaround — country codes now come from the source, so the
trip resolver can require them.

Input  : ``backend/stations.csv``     (``;``-delimited, 70+ columns; gitignored)
Output : ``backend/seed_data/seed_travel_location_train.csv``
         (comma-delimited, LF, the 10-column schema the reference CSV
         ingestion expects — see ``ReferenceDataCSVProvider``)

Kept rows (suggestable train stations with usable coordinates):
  - ``is_suggestable = t``  — stations trainline actually surfaces to users
  - ``is_airport != t``     — airports belong to the plane seed, not train
  - ``latitude`` / ``longitude`` non-empty — both are NOT NULL in ``locations``
  - ``country`` non-empty   — country_code is required downstream

``continent`` / ``municipality`` / ``iata_code`` / ``airport_size`` are not in
the source and stay blank (all optional for trains). ``keywords`` mirrors the
name so station search keeps working.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT = BACKEND_ROOT / "stations.csv"
OUTPUT_PATH = BACKEND_ROOT / "seed_data" / "seed_travel_location_train.csv"

# The exact column order the reference CSV ingestion COPYs into locations_staging.
OUTPUT_COLUMNS = [
    "transport_mode",
    "airport_size",
    "name",
    "latitude",
    "longitude",
    "continent",
    "country_code",
    "municipality",
    "iata_code",
    "keywords",
]


def _keep(row: dict[str, str]) -> bool:
    return (
        (row.get("is_suggestable") or "").strip() == "t"
        and (row.get("is_airport") or "").strip() != "t"
        and bool((row.get("latitude") or "").strip())
        and bool((row.get("longitude") or "").strip())
        and bool((row.get("country") or "").strip())
    )


def _to_seed_row(row: dict[str, str]) -> list[str]:
    name = (row.get("name") or "").strip()
    return [
        "train",  # transport_mode
        "",  # airport_size (planes only)
        name,  # name
        (row.get("latitude") or "").strip(),  # latitude
        (row.get("longitude") or "").strip(),  # longitude
        "",  # continent (not in source)
        (row.get("country") or "").strip(),  # country_code (ISO-2)
        "",  # municipality (not in source)
        "",  # iata_code (planes only)
        name,  # keywords (for station search)
    ]


def build(input_path: Path, output_path: Path) -> int:
    """Write the seed file. Returns the number of station rows written."""
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    written = 0
    with (
        input_path.open(newline="", encoding="utf-8") as src,
        output_path.open("w", newline="", encoding="utf-8") as dst,
    ):
        reader = csv.DictReader(src, delimiter=";")
        writer = csv.writer(dst, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        for row in reader:
            if not _keep(row):
                continue
            writer.writerow(_to_seed_row(row))
            written += 1
    return written


def main(argv: list[str]) -> int:
    input_path = Path(argv[0]) if argv else DEFAULT_INPUT
    written = build(input_path, OUTPUT_PATH)
    try:
        shown = OUTPUT_PATH.relative_to(BACKEND_ROOT.parent)
    except ValueError:
        shown = OUTPUT_PATH
    print(f"wrote {written} train stations → {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
