"""#939 — travel from/to search against a real Postgres (requires Docker).

Every case below is a search a user reported broken, or one the search lost
along the way: accent folding (2026-05), the trigram indexes (2026-06
collapse, every search scanned the table), paging (``page`` ignored). See
the plan's QA table and the history on issue #939.

The seeded rows mirror ``travel_*_reference.csv``, keywords included: a case
answered by a keyword (``geneva`` → Genève) also needs that keyword in the
reference CSV.
"""

import json

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.location import LOCATION_SEARCH_COLUMNS, Location, TransportModeEnum
from app.repositories.location_repo import LocationRepository, _word_matches

TRAIN = TransportModeEnum.train
PLANE = TransportModeEnum.plane

# (country, name, keywords); coordinates only feed the natural key.
STATIONS = [
    ("CH", "Genève", "Genève, Genf, Geneva, Ginevra, Cornavin"),
    (
        "CH",
        "Genève Aéroport",
        "Genève Aéroport, Genève-Aéroport, Genf, Geneva, Ginevra",
    ),
    ("CH", "Zürich HB", "Zürich HB, Zurigo, Hauptbahnhof"),
    ("CH", "Bern", "Bern, Berne, Berna"),
    ("CH", "Bern Hbf", "Bern Hbf, Bern, Berne, Berna"),
    ("CH", "St-Gallen", "St-Gallen, St. Gallen, Saint-Gall, San Gallo, Sankt Gallen"),
    ("CH", "Basel SBB", "Basel SBB, Bâle, Basilea, Basle"),
    ("CH", "Luzern", "Luzern, Lucerne, Lucerna"),
    ("CH", "Lausanne", "Lausanne, Losanna"),
    ("CH", "Neuchâtel", "Neuchâtel, Neuenburg"),
    # Not in the reference: pins that the spelling typed ranks first.
    ("CH", "Neuchatel", "Neuchatel"),
    ("DE", "Berne", "Berne"),
    ("DE", "Oberhausen Hbf", "Oberhausen Hbf"),
    ("DE", "Stuttgart Hbf", "Stuttgart Hbf, Stoccarda"),
    ("IT", "Milano Centrale", "Milano Centrale, Mailand, Milan"),
]

# (iata, size, name, municipality, keywords, country)
AIRPORTS = [
    (
        "CDG",
        "large_airport",
        "Charles de Gaulle International Airport",
        "Paris (Roissy-en-France, Val-d'Oise)",
        "PAR, Aéroport Roissy-Charles de Gaulle, Roissy Airport",
        "FR",
    ),
    (
        "ORY",
        "large_airport",
        "Paris-Orly Airport",
        "Paris (Orly, Val-de-Marne)",
        None,
        "FR",
    ),
    ("LBG", "medium_airport", "Paris-Le Bourget Airport", "Paris", "PAR", "FR"),
    (
        "GVA",
        "large_airport",
        "Geneva Cointrin International Airport",
        "Geneva",
        "Genève, Genf, Ginevra, Cointrin",
        "CH",
    ),
    ("ZRH", "large_airport", "Zürich Airport", "Zurich", None, "CH"),
    ("LHR", "large_airport", "London Heathrow Airport", "London", "LON, Londres", "GB"),
    (
        "LGW",
        "large_airport",
        "London Gatwick Airport",
        "London",
        "LON, Crawley, Charlwood, Londres",
        "GB",
    ),
    (
        "SVO",
        "large_airport",
        "Sheremetyevo International Airport",
        "Moscow",
        "MOW, svo, sheremetyevo, moscow, Moscou, Moskva",
        "RU",
    ),
]

# Names repeat in pairs, so only the id keeps the paging order total.
FILLERS = 300

# (mode, query, the names the results open with, in any order); () = none.
CASES = [
    # #939: page 1 of "be" held no Bern; 1-2 letters now start a word
    (TRAIN, "be", ("Bern",)),
    (TRAIN, "ber", ("Bern",)),
    (TRAIN, "hausen", ("Oberhausen Hbf",)),
    # #429, #942: accents, separators and word order
    (TRAIN, "zurich", ("Zürich HB",)),
    (TRAIN, "Zürich", ("Zürich HB",)),
    (TRAIN, "zu", ("Zürich HB",)),
    (TRAIN, "zurich hb", ("Zürich HB",)),
    (TRAIN, "hb zurich", ("Zürich HB",)),
    (TRAIN, "zurich hauptbahnhof", ("Zürich HB",)),
    (TRAIN, "St Gallen", ("St-Gallen",)),
    (TRAIN, "st. gallen", ("St-Gallen",)),
    (TRAIN, "st-gallen", ("St-Gallen",)),
    (TRAIN, "sankt gallen", ("St-Gallen",)),
    # #939, #2791, #331: Genève in every spelling
    (TRAIN, "geneve", ("Genève",)),
    (TRAIN, "Genève", ("Genève",)),
    (TRAIN, "geneva", ("Genève",)),
    (TRAIN, "Genève Cornavin", ("Genève",)),
    (TRAIN, "geneve-cornavin", ("Genève",)),
    (TRAIN, "cornavin", ("Genève",)),
    # #939: the railway station, not the ICC/WTC bus stops the seed held
    (TRAIN, "geneve aeroport", ("Genève Aéroport",)),
    (TRAIN, "genève aéroport", ("Genève Aéroport",)),
    # #1183, #1124: CH Bern before DE Berne
    (TRAIN, "bern", ("Bern",)),
    (TRAIN, "berne", ("Bern", "Bern Hbf")),
    # #1830: FR/DE names of Swiss cities
    (TRAIN, "basel", ("Basel SBB",)),
    (TRAIN, "bâle", ("Basel SBB",)),
    (TRAIN, "lucerne", ("Luzern",)),
    (TRAIN, "lausanne", ("Lausanne",)),
    # Accents fold to match; the spelling typed ranks first
    (TRAIN, "neuchâtel", ("Neuchâtel",)),
    (TRAIN, "neuchatel", ("Neuchatel",)),
    # #941, #915: stations abroad
    (TRAIN, "milan", ("Milano Centrale",)),
    (TRAIN, "stuttgart", ("Stuttgart Hbf",)),
    # #1439, #331: municipality, keywords, IATA; large airports first
    (PLANE, "paris", ("Charles de Gaulle International Airport", "Paris-Orly Airport")),
    (PLANE, "roissy", ("Charles de Gaulle International Airport",)),
    (PLANE, "cdg", ("Charles de Gaulle International Airport",)),
    (PLANE, "CDG", ("Charles de Gaulle International Airport",)),
    (PLANE, "Cdg", ("Charles de Gaulle International Airport",)),
    (PLANE, "charles de gaulle", ("Charles de Gaulle International Airport",)),
    # #2791, #368: GVA by IATA and by its French name
    (PLANE, "gva", ("Geneva Cointrin International Airport",)),
    (PLANE, "geneve", ("Geneva Cointrin International Airport",)),
    (PLANE, "Genève", ("Geneva Cointrin International Airport",)),
    (PLANE, "zurich", ("Zürich Airport",)),
    # #1436, #331: other languages, through keywords
    (PLANE, "london", ("London Heathrow Airport", "London Gatwick Airport")),
    (PLANE, "londres", ("London Heathrow Airport", "London Gatwick Airport")),
    (PLANE, "moscou", ("Sheremetyevo International Airport",)),
    # Nothing to match: an empty list, no error
    (TRAIN, "zzzzzz", ()),
    (PLANE, "zzzzzz", ()),
    # `%` and `_` are not wildcards
    (TRAIN, "%", ()),
    (TRAIN, "_", ()),
]

# (mode, query, a name that must not come back)
EXCLUDED = [
    (TRAIN, "be", "Oberhausen Hbf"),
    (TRAIN, "geneve aeroport", "Genève"),
]


def _station(country: str, name: str, keywords: str | None, n: int) -> Location:
    latitude, longitude = 40.0 + n / 1000, 5.0
    return Location(
        transport_mode=TRAIN,
        name=name,
        keywords=keywords,
        latitude=latitude,
        longitude=longitude,
        country_code=country,
        natural_key=Location.compute_natural_key(
            transport_mode=TRAIN,
            name=name,
            latitude=latitude,
            longitude=longitude,
            country_code=country,
        ),
    )


async def _seed(session: AsyncSession) -> None:
    rows = [_station(*station, n) for n, station in enumerate(STATIONS)]
    rows += [
        _station("FR", f"Filler {n % (FILLERS // 2):03d}", None, len(STATIONS) + n)
        for n in range(FILLERS)
    ]
    rows += [
        Location(
            transport_mode=PLANE,
            iata_code=iata,
            airport_size=size,
            name=name,
            municipality=municipality,
            keywords=keywords,
            country_code=country,
            latitude=0.0,
            longitude=0.0,
            natural_key=Location.compute_natural_key(
                transport_mode=PLANE, iata_code=iata
            ),
        )
        for iata, size, name, municipality, keywords, country in AIRPORTS
    ]
    session.add_all(rows)
    await session.commit()


async def _names(session: AsyncSession, mode: TransportModeEnum, query: str):
    found = await LocationRepository(session).search_location(query, mode, limit=20)
    return [location.name for location in found]


async def test_reported_searches_find_the_right_place(pg_session):
    await _seed(pg_session)

    wrong = []
    for mode, query, leading in CASES:
        names = await _names(pg_session, mode, query)
        if set(names[: len(leading)]) != set(leading) or (not leading and names):
            wrong.append(f"{mode.value} {query!r}: expected {leading}, got {names}")
    for mode, query, name in EXCLUDED:
        names = await _names(pg_session, mode, query)
        if name in names:
            wrong.append(f"{mode.value} {query!r}: {name!r} should not match")
    assert not wrong, "\n".join(wrong)


async def test_pages_are_disjoint_and_complete(pg_session):
    """``page`` used to be ignored: page 3 repeated page 1 (#939)."""
    await _seed(pg_session)
    repo = LocationRepository(pg_session)

    ids: list[int | None] = []
    offset = 0
    while page := await repo.search_location("filler", TRAIN, limit=20, offset=offset):
        ids += [location.id for location in page]
        offset += 20

    assert len(ids) == len(set(ids)) == FILLERS


async def test_each_word_is_served_by_its_trigram_indexes(pg_session):
    """The 2026-06 migration collapse turned these indexes into btrees and
    every search scanned the table. A plan label is not enough: a pattern
    pg_trgm cannot extract trigrams from (a negated regex class) still shows
    a bitmap index scan, one that returns every row. So each index scan must
    return fewer rows than the fillers alone.
    """
    await _seed(pg_session)
    connection = await pg_session.connection()
    await connection.exec_driver_sql("SET LOCAL enable_seqscan = off")

    expected = {f"ix_locations_{column}_trgm" for column in LOCATION_SEARCH_COLUMNS}
    for word in ("be", "geneve"):
        statement = select(Location.id).where(_word_matches(word))
        sql = str(
            statement.compile(
                dialect=connection.dialect, compile_kwargs={"literal_binds": True}
            )
        )
        result = await connection.exec_driver_sql(
            f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}"
        )
        plan = result.scalar_one()
        scans = _index_scans(json.loads(plan) if isinstance(plan, str) else plan)

        assert {name for name, _ in scans} == expected, (word, scans)
        assert all(rows < FILLERS for _, rows in scans), (word, scans)


def _index_scans(node) -> list[tuple[str, int]]:
    if isinstance(node, list):
        return [scan for item in node for scan in _index_scans(item)]
    plan = node.get("Plan", node)
    scans = [(plan["Index Name"], plan["Actual Rows"])] if "Index Name" in plan else []
    return scans + _index_scans(plan.get("Plans", []))
