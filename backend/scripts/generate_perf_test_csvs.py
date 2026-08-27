#!/usr/bin/env python3
"""Generate ceiling-scale test CSVs for manual performance testing (#2161).

One generator per ``DataEntryTypeEnum``, sized at the real per-unit-year
ceilings from issue #2161 (see
``docs/src/implementation-plans/2161-ceiling-scale-perf-fixtures.md``).

Rows are sampled from the real reference/factor files in ``INPUT_DATA``
rather than invented, because since #2050 Track J1 a value that cannot be
resolved no longer degrades quietly — an IATA code absent from
``travel_planes_reference.csv``, a purchase code the factor table doesn't
classify into the target category, etc. all raise, and the ingest reports
the row as an error. Invented data would measure the error path, not the
module.

Each output CSV is meant for the **module-unit-specific** upload path: the
upload job has ``data_entry_type_id`` set explicitly to the target type, so
the CSV itself carries no type/category column — that's also why one
purchase or equipment category can't just be told apart from another by
looking at the file.

``building_construction_renovation`` (data_entry_type 32, still named
``building_embodied_energy`` in the model — see #2161) has no CSV ingest at
all: it's derived server-side from ``building`` rows during ingest, so
generating ``building`` at its own ceiling already covers it.

Usage::

    uv run python -m scripts.generate_perf_test_csvs                 # all
    uv run python -m scripts.generate_perf_test_csvs --only plane
    uv run python -m scripts.generate_perf_test_csvs --out /tmp/perf --scale 2

Output goes to ``backend/INPUT_DATA/perf/`` by default. Nothing is committed —
``*.csv`` is gitignored. See ``README.md`` in this folder for the full
scripts overview.

There is deliberately **no simulator-plan CSV**: plans have no ingest path.
A plan is populated by ``set_reference_year`` copying a Calculator year, so
to test a plan at scale you load these files into a Calculator year first,
then create a plan pointing at it. See ``--help`` output.
"""

import argparse
import csv
import functools
import random
import sys
from collections.abc import Callable
from pathlib import Path

INPUT_DATA = Path(__file__).resolve().parent.parent / "INPUT_DATA"

# #2161 real per-data_entry_type ceilings, per unit-year.
CEILINGS = {
    "member": 500,
    "student": 500,
    "scientific": 1000,
    "it": 1000,
    "other": 1000,
    "plane": 500,
    "train": 5000,
    "building": 500,
    "energy_combustion": 500,
    "building_construction_renovation": 500,
    "external_clouds": 500,
    "external_ai": 500,
    "process_emissions": 500,
    "scientific_equipment": 1000,
    "it_equipment": 1000,
    "consumable_accessories": 1000,
    "biological_chemical_gaseous_product": 1000,
    "services": 1000,
    "vehicles": 1000,
    "other_purchases": 1000,
    "purchases_centralized": 1000,
    "research_facilities": 500,
    "animal_facilities": 50,
}


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


def _note_if_short(available: int, requested: int, source: str) -> None:
    if available < requested:
        print(
            f"note: only {available} distinct rows usable from {source}, "
            f"asked for {requested} — values will repeat",
            file=sys.stderr,
        )


def generate_headcount_member(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Members reusing real (name, sius_code) pairs from real member data.

    sius_code is validated against a fixed set server-side; reusing real
    rows keeps names/codes realistic without needing a lookup.
    """
    reference = _read("headcount_member_data.csv")
    if not reference:
        raise SystemExit("headcount_member_data.csv is empty")
    _note_if_short(len(reference), count, "headcount_member_data.csv")
    rows = []
    for i in range(count):
        origin = reference[i % len(reference)]
        rows.append(
            {
                "name": f"{origin['name']} #{i}",
                "sius_code": origin["sius_code"],
                "user_institutional_id": f"{100000 + (i % 400):06d}",
                "fte": round(rng.uniform(0.1, 1.0), 2),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_headcount_member.csv",
            ["name", "sius_code", "user_institutional_id", "fte", "note"],
            rows,
        )
    ]


def generate_headcount_student(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Students: ``fte`` is the only field the ingest DTO requires."""
    rows = [{"fte": round(rng.uniform(0.1, 1.0), 2)} for _ in range(count)]
    return [_write(out_dir, "perf_headcount_student.csv", ["fte"], rows)]


def generate_equipment(
    out_dir: Path, count: int, rng: random.Random, category: str
) -> list[Path]:
    """Equipment reusing (equipment_class, sub_class) pairs the real factor
    table classifies into ``category`` — an unresolved pair fails the row
    since #2050 Track J1.
    """
    pairs = [
        (row["equipment_class"], row.get("sub_class") or "")
        for row in _read("equipment_factors.csv")
        if row.get("equipment_category") == category
    ]
    if not pairs:
        raise SystemExit(
            f"no equipment_category={category!r} rows in equipment_factors.csv"
        )
    _note_if_short(len(pairs), count, f"equipment_factors.csv[{category}]")

    rows = []
    for i in range(count):
        equipment_class, sub_class = pairs[i % len(pairs)]
        rows.append(
            {
                "equipment_class": equipment_class,
                "sub_class": sub_class,
                "equipment_id": f"PERF-{category.upper()}-{i}",
                "name": f"{equipment_class} #{i}",
                "active_usage_hours_per_week": rng.randint(0, 40),
                "standby_usage_hours_per_week": rng.randint(0, 40),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            f"perf_equipment_{category}.csv",
            [
                "equipment_class",
                "sub_class",
                "equipment_id",
                "name",
                "active_usage_hours_per_week",
                "standby_usage_hours_per_week",
                "note",
            ],
            rows,
        )
    ]


def generate_travel_plane(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
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


def generate_travel_train(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
    """Train legs between stations that exist in the reference file.

    Mirrors ``generate_travel_plane``: an unknown station has no route
    factor, and fails the row rather than silently dropping the leg.
    """
    stations = [
        (row["name"], row["country_code"])
        for row in _read("travel_trains_reference.csv")
        if row.get("name") and row.get("country_code")
    ]
    if len(stations) < 2:
        raise SystemExit("travel_trains_reference.csv yielded no usable stations")

    cabins = ["first", "second"]
    rows = []
    for i in range(count):
        (origin_name, origin_country), (dest_name, dest_country) = rng.sample(
            stations, 2
        )
        departure = f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        rows.append(
            {
                "origin_name": origin_name,
                "origin_country_code": origin_country,
                "destination_name": dest_name,
                "destination_country_code": dest_country,
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
            "perf_travel_trains.csv",
            [
                "origin_name",
                "origin_country_code",
                "destination_name",
                "destination_country_code",
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
    _note_if_short(len(sample), count, "building_rooms_reference.csv")
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


def generate_energy_combustion(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Combustion entries reusing real (name, unit) pairs from the factor
    table — an unresolved pair has no emission factor.
    """
    pairs = [
        (row["name"], row["unit"])
        for row in _read("building_energycombustions_factors.csv")
        if row.get("name") and row.get("unit")
    ]
    if not pairs:
        raise SystemExit(
            "building_energycombustions_factors.csv yielded no usable pairs"
        )
    _note_if_short(len(pairs), count, "building_energycombustions_factors.csv")

    rows = []
    for i in range(count):
        name, unit = pairs[i % len(pairs)]
        rows.append(
            {
                "name": name,
                "unit": unit,
                "quantity": round(rng.uniform(10, 5000), 2),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_building_energycombustions.csv",
            ["name", "unit", "quantity", "note"],
            rows,
        )
    ]


def generate_building_construction_renovation(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """No CSV ingest exists for this type — it's derived server-side from
    ``building`` rows during ingest (see module docstring). Generating
    ``building`` at its own ceiling already produces this data.
    """
    print(
        "building_construction_renovation: no CSV ingest — derived from "
        "'building' rows at ingest time, see generate_buildings()",
        file=sys.stderr,
    )
    return []


def generate_external_clouds(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Cloud spend reusing real (service_type, provider, currency) triples
    from the factor table — the factor is keyed by all three.
    """
    triples = [
        (row["service_type"], row["provider"], row["currency"])
        for row in _read("external_clouds_factors.csv")
        if row.get("service_type") and row.get("provider") and row.get("currency")
    ]
    if not triples:
        raise SystemExit("external_clouds_factors.csv yielded no usable rows")
    _note_if_short(len(triples), count, "external_clouds_factors.csv")

    rows = []
    for i in range(count):
        service_type, provider, currency = triples[i % len(triples)]
        rows.append(
            {
                "service_type": service_type,
                "provider": provider,
                "spent_amount": round(rng.uniform(50, 5000), 2),
                "currency": currency,
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_external_clouds.csv",
            ["service_type", "provider", "spent_amount", "currency", "note"],
            rows,
        )
    ]


def generate_external_ai(out_dir: Path, count: int, rng: random.Random) -> list[Path]:
    """AI usage reusing real (provider, usage_type) pairs from the factor
    table. ``requests_per_user_per_day`` is a fixed frequency bucket, not a
    lookup key, so it's picked freely.
    """
    pairs = [
        (row["provider"], row["usage_type"])
        for row in _read("external_ai_factors.csv")
        if row.get("provider") and row.get("usage_type")
    ]
    if not pairs:
        raise SystemExit("external_ai_factors.csv yielded no usable rows")
    _note_if_short(len(pairs), count, "external_ai_factors.csv")

    buckets = ["1_5", "5_20", "20_100", "gt_100"]
    rows = []
    for i in range(count):
        provider, usage_type = pairs[i % len(pairs)]
        rows.append(
            {
                "provider": provider,
                "usage_type": usage_type,
                "requests_per_user_per_day": rng.choice(buckets),
                "fte_count": round(rng.uniform(0.1, 10.0), 1),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_external_ai.csv",
            [
                "provider",
                "usage_type",
                "requests_per_user_per_day",
                "fte_count",
                "note",
            ],
            rows,
        )
    ]


def generate_process_emissions(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Process emissions reusing real (category, subcategory) pairs from the
    factor table — subcategory is legitimately blank for some categories.
    """
    pairs = [
        (row["category"], row.get("subcategory") or "")
        for row in _read("processemissions_factors.csv")
        if row.get("category")
    ]
    if not pairs:
        raise SystemExit("processemissions_factors.csv yielded no usable rows")
    _note_if_short(len(pairs), count, "processemissions_factors.csv")

    rows = []
    for i in range(count):
        category, subcategory = pairs[i % len(pairs)]
        rows.append(
            {
                "category": category,
                "subcategory": subcategory,
                "quantity_kg": round(rng.uniform(1, 500), 2),
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_processemissions.csv",
            ["category", "subcategory", "quantity_kg", "note"],
            rows,
        )
    ]


def generate_purchase(
    out_dir: Path, count: int, rng: random.Random, category: str
) -> list[Path]:
    """Purchases reusing institutional codes that the real factor table
    (``purchases_common_factors.csv``) classifies into ``category`` — an
    unclassified code fails the row since #2050 Track J1.
    """
    valid_keys = {
        (row["purchase_institutional_code"], row["purchase_additional_code"])
        for row in _read("purchases_common_factors.csv")
        if row.get("purchase_category") == category
    }
    if not valid_keys:
        raise SystemExit(
            f"no purchase_category={category!r} rows in purchases_common_factors.csv"
        )
    usable = [
        row
        for row in _read("purchases_common_data.csv")
        if (row.get("purchase_institutional_code"), row.get("purchase_additional_code"))
        in valid_keys
    ]
    if not usable:
        raise SystemExit(
            f"purchases_common_data.csv has no rows classified {category!r}"
        )
    _note_if_short(len(usable), count, f"purchases_common_data.csv[{category}]")

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
            f"perf_purchases_{category}.csv",
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


def generate_purchases_centralized(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Centralized purchases: classification is by ``name`` directly (no
    institutional code), so ``name`` must match a real factor row verbatim.
    """
    names = [
        row["name"]
        for row in _read("purchases_centralized_factors.csv")
        if row.get("name")
    ]
    if not names:
        raise SystemExit("purchases_centralized_factors.csv yielded no usable names")
    _note_if_short(len(names), count, "purchases_centralized_factors.csv")

    rows = []
    for i in range(count):
        rows.append(
            {
                "name": names[i % len(names)],
                "unit": "kg",
                "annual_consumption": round(rng.uniform(1, 500), 2),
                "coef_to_kg": 1,
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_purchases_centralized.csv",
            ["name", "unit", "annual_consumption", "coef_to_kg", "note"],
            rows,
        )
    ]


def generate_research_facilities(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Research facility usage reusing real (id, name, use_unit) triples."""
    triples = [
        (row["researchfacility_id"], row["researchfacility_name"], row["use_unit"])
        for row in _read("researchfacilities_common_factors.csv")
        if row.get("researchfacility_id") and row.get("researchfacility_name")
    ]
    if not triples:
        raise SystemExit("researchfacilities_common_factors.csv yielded no usable rows")
    _note_if_short(len(triples), count, "researchfacilities_common_factors.csv")

    rows = []
    for i in range(count):
        facility_id, facility_name, use_unit = triples[i % len(triples)]
        rows.append(
            {
                "researchfacility_id": facility_id,
                "researchfacility_name": facility_name,
                "use": round(rng.uniform(100, 10000), 2),
                "use_unit": use_unit,
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_researchfacilities_common.csv",
            ["researchfacility_id", "researchfacility_name", "use", "use_unit", "note"],
            rows,
        )
    ]


def generate_animal_facilities(
    out_dir: Path, count: int, rng: random.Random
) -> list[Path]:
    """Animal facility usage reusing real (id, name, type, use_unit) rows."""
    quads = [
        (
            row["researchfacility_id"],
            row["researchfacility_name"],
            row["researchfacility_type"],
            row["use_unit"],
        )
        for row in _read("researchfacilities_animals_factors.csv")
        if row.get("researchfacility_id") and row.get("researchfacility_type")
    ]
    if not quads:
        raise SystemExit(
            "researchfacilities_animals_factors.csv yielded no usable rows"
        )
    _note_if_short(len(quads), count, "researchfacilities_animals_factors.csv")

    rows = []
    for i in range(count):
        facility_id, facility_name, facility_type, use_unit = quads[i % len(quads)]
        rows.append(
            {
                "researchfacility_id": facility_id,
                "researchfacility_name": facility_name,
                "researchfacility_type": facility_type,
                "use": round(rng.uniform(10, 1000), 2),
                "use_unit": use_unit,
                "note": "",
            }
        )
    return [
        _write(
            out_dir,
            "perf_researchfacilities_animals.csv",
            [
                "researchfacility_id",
                "researchfacility_name",
                "researchfacility_type",
                "use",
                "use_unit",
                "note",
            ],
            rows,
        )
    ]


GENERATORS: dict[str, Callable[[Path, int, random.Random], list[Path]]] = {
    "member": generate_headcount_member,
    "student": generate_headcount_student,
    "scientific": functools.partial(generate_equipment, category="scientific"),
    "it": functools.partial(generate_equipment, category="it"),
    "other": functools.partial(generate_equipment, category="other"),
    "plane": generate_travel_plane,
    "train": generate_travel_train,
    "building": generate_buildings,
    "energy_combustion": generate_energy_combustion,
    "building_construction_renovation": generate_building_construction_renovation,
    "external_clouds": generate_external_clouds,
    "external_ai": generate_external_ai,
    "process_emissions": generate_process_emissions,
    "scientific_equipment": functools.partial(
        generate_purchase, category="scientific_equipment"
    ),
    "it_equipment": functools.partial(generate_purchase, category="it_equipment"),
    "consumable_accessories": functools.partial(
        generate_purchase, category="consumable_accessories"
    ),
    "biological_chemical_gaseous_product": functools.partial(
        generate_purchase, category="biological_chemical_gaseous_product"
    ),
    "services": functools.partial(generate_purchase, category="services"),
    "vehicles": functools.partial(generate_purchase, category="vehicles"),
    "other_purchases": functools.partial(generate_purchase, category="other_purchases"),
    "purchases_centralized": generate_purchases_centralized,
    "research_facilities": generate_research_facilities,
    "animal_facilities": generate_animal_facilities,
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
