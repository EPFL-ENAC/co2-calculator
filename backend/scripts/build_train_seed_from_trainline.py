#!/usr/bin/env python3
"""Build the train-station location seed from the trainline-eu ``stations.csv``.

Issue #1183: the train location seed is sourced from the open trainline-eu
dataset (https://github.com/trainline-eu/stations), which already carries an
ISO-2 ``country`` per station. This replaces the old name-only seed plus the
``CH``-backfill workaround — country codes now come from the source, so the
trip resolver can require them.

Issue #939: trainline is multimodal, so the seed held ~26 000 bus, tram and
coach stops, and dropped the airport railway stations. Swiss rows carry no
mode, so they are checked against the official Swiss service points.

Input  : ``backend/stations.csv``       (trainline-eu, ``;``-delimited; gitignored)
         ``backend/service_points.csv`` (opentransportdata.swiss "Service
         Points (actual date)", ``;``-delimited; gitignored)
Output : ``backend/seed_data/seed_travel_location_train.csv``
         (comma-delimited, LF, the 10-column schema the reference CSV
         ingestion expects — see ``ReferenceDataCSVProvider``)

Kept rows (suggestable railway stations with usable coordinates):
  - ``is_suggestable = t``  — stations trainline actually surfaces to users
  - ``latitude`` / ``longitude`` / ``country`` non-empty — NOT NULL downstream
  - in CH, a stop number (or failing that, a name) the service points list
    as a railway stop; a city row when one of its stations is kept
  - elsewhere, a UIC code, a railway carrier, or a country where trainline
    sells no train; and not named as a bus stop
  - airports follow the same rules: their railway stations stay

``continent`` / ``municipality`` / ``iata_code`` / ``airport_size`` are not in
the source and stay blank (all optional for trains). ``keywords`` holds the
name, the Swiss official name, the de/en/fr/it names and ``ALIASES``.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT = BACKEND_ROOT / "stations.csv"
DEFAULT_SERVICE_POINTS = BACKEND_ROOT / "service_points.csv"
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

SWISS_RAIL_MODES = {"TRAIN", "RACK_RAILWAY"}
COACH_CARRIERS = {
    f"{carrier}_is_enabled" for carrier in ("busbud", "distribusion", "flixbus")
}
# ponytail: outside CH a UIC code or a railway carrier marks a station, so a
# bus stop with one stays unless named so, and where trainline sells trains a
# station sold only by coach (Dublin DART halts) goes; a national list fixes both
BUS_NAME = re.compile(
    r"\b(bus|busbahnhof|busbf|zob|bussterminal|gare routi[eè]re|autostazione"
    r"|autobuses|coach station)\b",
    re.IGNORECASE,
)
KEYWORD_LANGUAGES = ("de", "en", "fr", "it")
# Names travellers type that no source carries (#939).
ALIASES = {
    "Genève": "Cornavin",
    "Zürich HB": "Hauptbahnhof",
    "St-Gallen": "Sankt Gallen",
    "Basel SBB": "Basle",
}


def _fold(name: str) -> str:
    return re.sub(r"[\W_]+", " ", name).strip().lower()


def _swiss_rail_stops(path: Path) -> dict[str, str]:
    """Stop number, and folded official name, → official name of a Swiss
    railway stop. The name is there for stations trainline numbers the
    German way (Thayngen, Riehen Niederholz).
    """
    with path.open(newline="", encoding="utf-8-sig") as src:
        rail = [
            point
            for point in csv.DictReader(src, delimiter=";")
            if SWISS_RAIL_MODES & set(point["meansOfTransport"].split("|"))
        ]
    official = {point["number"]: point["designationOfficial"] for point in rail}
    return official | {_fold(name): name for name in official.values()}


def _stop_number(row: dict[str, str]) -> str:
    return row["cff_id"] or row["uic"]


def _carriers(row: dict[str, str]) -> set[str]:
    return {
        column
        for column, value in row.items()
        if column.endswith("_is_enabled") and value == "t"
    }


def _is_rail(
    row: dict[str, str], swiss_rail: dict[str, str], rail_countries: set[str]
) -> bool:
    if row["country"] == "CH":
        return _stop_number(row) in swiss_rail or _fold(row["name"]) in swiss_rail
    # Sold only by coach means a bus stop only where trainline sells trains.
    rail_code = (
        bool(row["uic"])
        or bool(_carriers(row) - COACH_CARRIERS)
        or row["country"] not in rail_countries
    )
    return rail_code and not BUS_NAME.search(row["name"])


def _usable(row: dict[str, str]) -> bool:
    return row["is_suggestable"] == "t" and all(
        row[column].strip() for column in ("latitude", "longitude", "country")
    )


def _keywords(row: dict[str, str], swiss_rail: dict[str, str]) -> str:
    names = [row["name"], swiss_rail.get(_stop_number(row), "")]
    names += [row[f"info:{language}"] for language in KEYWORD_LANGUAGES]
    names.append(ALIASES.get(row["name"], ""))
    return ", ".join(dict.fromkeys(name.strip() for name in names if name.strip()))


def _to_seed_row(row: dict[str, str], swiss_rail: dict[str, str]) -> list[str]:
    return [
        "train",  # transport_mode
        "",  # airport_size (planes only)
        row["name"].strip(),  # name
        row["latitude"].strip(),  # latitude
        row["longitude"].strip(),  # longitude
        "",  # continent (not in source)
        row["country"].strip(),  # country_code (ISO-2)
        "",  # municipality (not in source)
        "",  # iata_code (planes only)
        _keywords(row, swiss_rail),  # keywords (for station search)
    ]


def build(input_path: Path, service_points_path: Path, output_path: Path) -> int:
    """Write the seed file. Returns the number of station rows written."""
    for path in (input_path, service_points_path):
        if not path.exists():
            raise SystemExit(f"input not found: {path}")
    swiss_rail = _swiss_rail_stops(service_points_path)
    with input_path.open(newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src, delimiter=";"))
    rail_countries = {row["country"] for row in rows if _carriers(row) - COACH_CARRIERS}
    rail = [row for row in rows if _is_rail(row, swiss_rail, rail_countries)]
    # A city row (Basel, Bern) stays when one of its stations does.
    keep = {row["id"] for row in rail} | {row["parent_station_id"] for row in rail}
    kept = [row for row in rows if _usable(row) and row["id"] in keep]
    missing = ALIASES.keys() - {row["name"] for row in kept}
    if missing:
        raise SystemExit(
            f"ALIASES name stations the seed no longer holds: {sorted(missing)}"
        )
    with output_path.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.writer(dst, lineterminator="\n")
        writer.writerow(OUTPUT_COLUMNS)
        writer.writerows(_to_seed_row(row, swiss_rail) for row in kept)
    return len(kept)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build the train-station seed CSV.")
    parser.add_argument("stations", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "service_points", nargs="?", type=Path, default=DEFAULT_SERVICE_POINTS
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)
    written = build(args.stations, args.service_points, args.output)
    try:
        shown = args.output.relative_to(BACKEND_ROOT.parent)
    except ValueError:
        shown = args.output
    print(f"wrote {written} train stations → {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
