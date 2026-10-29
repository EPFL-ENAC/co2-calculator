"""#939: the train seed held ~26 000 bus stops, dropped the airport railway
stations, and nothing answered "Genève Cornavin".
"""

import csv
from pathlib import Path

import pytest

from scripts.build_train_seed_from_trainline import build

STATION_COLUMNS = [
    "id",
    "name",
    "uic",
    "latitude",
    "longitude",
    "parent_station_id",
    "country",
    "is_airport",
    "is_suggestable",
    "cff_id",
    "sncf_is_enabled",
    "flixbus_is_enabled",
    "info:de",
    "info:en",
    "info:fr",
    "info:it",
]

# (number, official name, means of transport)
SERVICE_POINTS = [
    ("8501008", "Genève", "TRAIN"),
    ("8503000", "Zürich HB", "TRAIN"),
    ("8506302", "St. Gallen", "TRAIN"),
    ("8500010", "Basel SBB", "TRAIN"),
    ("8501026", "Genève-Aéroport", "TRAIN"),
    ("8593014", "Genève-Aéroport, ICC", "BUS"),
    ("8503461", "Thayngen", "TRAIN"),
]


def _station(id_: str, name: str, country: str = "CH", **columns: str):
    usable = {"latitude": "46.2", "longitude": "6.1", "is_suggestable": "t"}
    return {"id": id_, "name": name, "country": country} | usable | columns


ALIASED = [
    _station("1", "Genève", cff_id="8501008", **{"info:de": "Genf"}),
    _station("2", "Zürich HB", cff_id="8503000"),
    _station("3", "St-Gallen", cff_id="8506302"),
    _station("4", "Basel SBB", cff_id="8500010", parent_station_id="5"),
]

STATIONS = ALIASED + [
    _station("5", "Basel"),  # a city: stays for its station
    _station("6", "Splügen"),  # a city without a railway station
    _station("7", "Genève Aéroport", cff_id="8501026", is_airport="t"),
    _station("8", "Genève-Aéroport ICC", cff_id="8593014", is_airport="t"),
    _station("9", "Thayngen", cff_id="8014490"),  # numbered the German way
    _station("10", "Paris", "FR", sncf_is_enabled="t"),
    _station("11", "Annonay Gare Routière", "FR", uic="8701234", sncf_is_enabled="t"),
    _station("12", "Frankfurt (M) Flughafen", "DE", uic="8004126", is_airport="t"),
    _station("13", "Lyon Part-Dieu", "FR", uic="8772319", is_suggestable="f"),
    # Sold only by coach: a bus stop where trainline sells trains (FR), not
    # where it sells none (BG)
    _station("14", "Montélimar Sud", "FR", flixbus_is_enabled="t"),
    _station("15", "Sofia", "BG", flixbus_is_enabled="t"),
]


def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, columns, delimiter=";", restval="")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _build(tmp_path: Path, stations: list[dict[str, str]]) -> dict[str, str]:
    """Run the builder; returns name → keywords of the rows written."""
    service_points = [
        dict(zip(("number", "designationOfficial", "meansOfTransport"), point))
        for point in SERVICE_POINTS
    ]
    output = tmp_path / "seed.csv"
    build(
        _write(tmp_path / "stations.csv", STATION_COLUMNS, stations),
        _write(
            tmp_path / "service_points.csv",
            ["number", "designationOfficial", "meansOfTransport"],
            service_points,
        ),
        output,
    )
    with output.open(newline="", encoding="utf-8") as src:
        return {row["name"]: row["keywords"] for row in csv.DictReader(src)}


def test_keeps_railway_stations_only_airports_included(tmp_path):
    seed = _build(tmp_path, STATIONS)

    assert set(seed) == {
        "Genève",
        "Zürich HB",
        "St-Gallen",
        "Basel SBB",
        "Basel",
        "Genève Aéroport",
        "Thayngen",
        "Paris",
        "Frankfurt (M) Flughafen",
        "Sofia",
    }


def test_keywords_hold_official_translated_and_typed_names(tmp_path):
    seed = _build(tmp_path, STATIONS)

    assert seed["Genève"] == "Genève, Genf, Cornavin"
    assert seed["St-Gallen"] == "St-Gallen, St. Gallen, Sankt Gallen"


def test_an_alias_for_a_station_no_longer_kept_fails_the_build(tmp_path):
    with pytest.raises(SystemExit, match="Zürich HB"):
        _build(tmp_path, [row for row in STATIONS if row["name"] != "Zürich HB"])
