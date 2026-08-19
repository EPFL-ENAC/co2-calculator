#!/usr/bin/env python3
"""Generate ceiling-scale test CSVs for manual performance testing (#2050).

Rows are sampled from the real reference files in ``INPUT_DATA`` rather than
invented, because since #2050 Track J1 a value that cannot be resolved no
longer degrades quietly — a room absent from ``building_rooms_reference.csv``
or an IATA code absent from ``travel_planes_reference.csv`` raises, and the
ingest reports the row as an error. Invented data would measure the error
path, not the module.

Sizes follow the per-unit-year ceilings agreed in #2161:

    travel 5,500 · buildings 1,500 · purchase 8,000

Usage::

    uv run python -m scripts.generate_perf_test_csvs                 # all
    uv run python -m scripts.generate_perf_test_csvs --only travel
    uv run python -m scripts.generate_perf_test_csvs --out /tmp/perf --scale 2

Output goes to ``backend/INPUT_DATA/perf/`` by default. Nothing is committed —
``*.csv`` is gitignored.

There is deliberately **no simulator-plan CSV**: plans have no ingest path.
A plan is populated by ``set_reference_year`` copying a Calculator year, so to
test a plan at scale you load these files into a Calculator year first, then
create a plan pointing at it. See ``--help`` output.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

INPUT_DATA = Path(__file__).resolve().parent.parent / "INPUT_DATA"

# #2161 ceilings, per unit-year.
CEILINGS = {"travel": 5_500, "buildings": 1_500, "purchase": 8_000}


def _read(name: str) -> list[dict[str, str]]:
    path = INPUT_DATA / name
    if not path.exists():
        raise SystemExit(
            f"{path} not found. These generators sample the real reference "
            f"files; INPUT_DATA is gitignored, so run this where it exists."
        )
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(out_dir: Path, name: str, fieldnames: list[str], rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_travel(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
    """Plane trips between IATA codes that exist in the reference file.

    An unknown code resolves to no airport, which now fails the row rather
    than silently dropping the leg.
    """
    airports = [
        row["iata_code"]
        for row in _read("travel_planes_reference.csv")
        if row.get("iata_code") and len(row["iata_code"]) == 3
    ]
    if len(airports) < 2:
        raise SystemExit("travel_planes_reference.csv yielded no usable IATA codes")

    cabins = ["economy", "business", "first"]
    rows = []
    for i in range(count):
        origin, destination = rng.sample(airports, 2)
        departure = f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        rows.append(
            {
                "origin_iata": origin,
                "destination_iata": destination,
                "user_institutional_id": f"{100000 + (i % 400):06d}",
                "departure_date": departure,
                "number_of_trips": rng.randint(1, 3),
                "cabin_class": rng.choice(cabins),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_travel_planes.csv",
            [
                "origin_iata",
                "destination_iata",
                "user_institutional_id",
                "departure_date",
                "number_of_trips",
                "cabin_class",
                "note",
            ],
            rows,
        )
    ]


def generate_buildings(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
    """Rooms taken verbatim from the reference file.

    A room_name absent from it has no surface, and since #2050 Track J1 that
    raises instead of quietly producing a zero-emission building.
    """
    reference = _read("building_rooms_reference.csv")
    if not reference:
        raise SystemExit("building_rooms_reference.csv is empty")
    sample = rng.sample(reference, min(count, len(reference)))
    if len(sample) < count:
        print(
            f"note: only {len(sample)} distinct reference rooms available, "
            f"asked for {count}",
            file=sys.stderr,
        )
    rows = [
        {
            "building_location": row["building_location"],
            "building_name": row["building_name"],
            "room_name": row["room_name"],
            "room_type": row["room_type"],
            "note": "",
        }
        for row in sample
    ]
    return [
        _write(
            out_dir,
            "perf_building_rooms.csv",
            ["building_location", "building_name", "room_name", "room_type", "note"],
            rows,
        )
    ]


def generate_purchase(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
    """Purchases reusing institutional codes that appear in the real data, so
    the classification resolves to a factor.
    """
    source = _read("purchases_common_data.csv")
    usable = [
        row
        for row in source
        if row.get("purchase_institutional_code") and row.get("name")
    ]
    if not usable:
        raise SystemExit("purchases_common_data.csv yielded no usable rows")

    rows = []
    for i in range(count):
        origin = usable[i % len(usable)]
        rows.append(
            {
                "name": f"{origin['name'][:60]} #{i}",
                "supplier": origin.get("supplier") or "Test supplier",
                "quantity": origin.get("quantity") or 1,
                "total_spent_amount": round(rng.uniform(50, 5000), 2),
                "currency": "chf",
                "purchase_institutional_code": origin["purchase_institutional_code"],
                "purchase_additional_code": origin.get("purchase_additional_code")
                or "",
                "purchase_institutional_description": "",
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_purchases_itequipment.csv",
            [
                "name",
                "supplier",
                "quantity",
                "total_spent_amount",
                "currency",
                "purchase_institutional_code",
                "purchase_additional_code",
                "purchase_institutional_description",
                "note",
            ],
            rows,
        )
    ]


GENERATORS = {
    "travel": generate_travel,
    "buildings": generate_buildings,
    "purchase": generate_purchase,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default=str(INPUT_DATA / "perf"))
    parser.add_argument("--only", choices=sorted(GENERATORS), action="append")
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="multiply the #2161 ceilings (e.g. 2 for twice a full unit-year)",
    )
    parser.add_argument("--seed", type=int, default=2050)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out)
    wanted = args.only or sorted(GENERATORS)

    written: list[Path] = []
    for name in wanted:
        count = int(CEILINGS[name] * args.scale)
        written.extend(GENERATORS[name](out_dir, count, rng))
        print(f"{name}: {count} rows")

    print("\nWrote:")
    for path in written:
        print(f"  {path}  ({path.stat().st_size / 1024:.0f} KB)")
    print(
        "\nSimulator Plan has no CSV: a plan is populated by set_reference_year\n"
        "copying a Calculator year. Load these into a Calculator year first,\n"
        "then create a plan whose reference year points at it."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
