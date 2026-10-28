---
status: in-progress
issue: 939
last_updated: 2026-10-28
summary: "GET /locations/search honours `page` on a total order and matches word by word, ignoring accents and separators. Each word is served by a trigram GIN index on `search_text(column)`. The travel from/to selects load the next page by infinite scroll."
---

# 939 — Travel from/to search: paging, word matching, trigram indexes

## Bug

`GET /locations/search?query=be&transport_mode=train&limit=10&page=3`
returned the same rows as `page=1`. The route never declared `page`, and
FastAPI drops undeclared query params without an error. The from/to
q-selects asked for one page of 20 and nothing more, so a short query such
as `be` (5 422 train matches) could never reach most stations.

The search also matched the whole query as one accent-sensitive
substring. `genève aéroport` found nothing while `genève-aéroport` found
the Genève-Aéroport stations, and `zurich` found no Zürich station.

## History

The [issue comment](https://github.com/EPFL-ENAC/co2-calculator/issues/939#issuecomment-6445992604)
has the full account. In short:

| date       | commit      | change                                                                                                                         |
| ---------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 2026-01-23 | `6d93a467c` | ICU collations `ch_*_ci_ai`: case- and accent-insensitive                                                                      |
| 2026-05-05 | `54114853f` | pg_trgm GIN on 4 columns, raw SQL; collations dropped, accent folding lost; `LOWER(col) %` could not use the indexes           |
| 2026-06-15 | `7c7423b48` | `ILIKE` per column, so the indexes became usable (`paris` → CDG, #1439)                                                        |
| 2026-06-15 | `72d56d583` | migration collapse rebuilt 3 of the 4 trigram indexes as btree; only `keywords` survived; every search scanned the table since |

## Design

### Paging (shipped, confirmed)

- `page: int = Query(1, ge=1, le=10_000)`. The service turns it into
  `offset=(page - 1) * limit`, the repo applies `.offset().limit()`. The
  asyncpg dialect binds `OFFSET $n::INTEGER`, so the cap keeps a huge page
  from overflowing int4 into a 500; 10 000 pages of 20 is past any result
  set. `query` is capped at 255, the searched columns' length.
- `Location.id` closes both ORDER BY branches: `name` repeats, and a
  non-total order lets consecutive pages overlap or skip rows.
- The response stays `list[LocationRead]`. No COUNT: a page shorter than
  `limit` is the last one.
- Frontend: `composables/useLocationSearch.ts` replaces the duplicated
  `filterFrom`/`filterTo` in `CO2DestinationInput.vue`, and
  `molecules/LocationSelectField.vue` holds one from/to q-select with its
  search, menu states and pick handling (499 → 331 + 110 lines). The atom
  keeps the from/to values, the swap and the plain-input fallback. `filter`
  loads page 1 for the trimmed query;
  `onVirtualScroll` appends the next page when the last option renders,
  then `ref.refresh()` (Quasar's infinite-scroll pattern). A request
  counter, bumped when a search, a page load or a reset starts, lets only
  the latest request touch the list, the loading flag and the error, as in
  `VirtualSelectField.vue`.
- The menu says why it is empty or short, with the keys
  `VirtualSelectField` already uses: `common_type_to_search` under 2
  characters, `common_no_search_results` for no match, and
  `module_options_load_error` when page 1 fails. A failed page-N fetch keeps
  the rows shown, stops paging until the next search, and shows the same
  error after the last row.

### Matching

- The query splits into words (`[^\W_]+`). Every word must match (AND),
  in any of `name`, `iata_code`, `municipality`, `keywords` (OR).
  Separators and word order no longer matter. `%`/`_` are no longer
  wildcards; a query with no letter or digit returns `[]` without a query.
- Words of 3+ letters match anywhere: `bahnhof` finds Hauptbahnhof,
  `hausen` finds Oberhausen. Words of 1–2 letters match a word start: `be`
  finds Bern, not Oberhausen; `hb` finds Zürich HB. A short word is never
  refused, since `be` → Bern is the bug itself. Prefix for short words,
  infix for longer ones is what Sphinx (`min_prefix_len`/`min_infix_len`)
  and Elasticsearch (edge-ngram + ngram) do.
- Accents are folded on both sides (`zurich` finds Zürich, `évé` finds
  `evenement`). Ties after the folded relevance go to the raw
  `similarity(name, query)`, so the spelling typed comes first:
  `neuchâtel` lists Neuchâtel before Neuchatel. A mistyped accent never
  empties the list.

### Indexes

- `search_text(text)`: one IMMUTABLE SQL function,
  `' ' || regexp_replace(public.unaccent('public.unaccent', $1), '[[:space:][:punct:]]+', ' ', 'g')`.
  - IMMUTABLE because `unaccent()` is only STABLE and cannot be indexed.
  - Schema-qualified because pg_restore runs with an empty `search_path`.
  - Separators become one space and a space is prepended, so a word start
    is always `' ' + word`. `'% be%'` then extracts the trigrams `"  b"` and
    `" be"`, and the index serves it.
  - The separator classes are ASCII-safe: `[^[:alnum:]]` would erase
    non-ASCII letters under a C ctype. The databases are libc
    `en_US.utf8`.
- Four GIN `gin_trgm_ops` indexes, `ix_locations_<column>_trgm`, on
  `search_text(column)`, one per entry of `LOCATION_SEARCH_COLUMNS` in
  `models/location.py`. The repo builds its WHERE from the same tuple. The
  expression is spelled `search_text((name)::text)`, the way Postgres
  stores it, so autogenerate compares it equal and proposes nothing. They
  replace `ix_locations_keywords`. The btree on `iata_code` stays for
  `get_by_iata`.
- The pattern side is `unaccent('%word%')` or `unaccent('% wo%')`, not
  `search_text()`, which would prepend a space.
- Why `LIKE`, not a regex: in `(^|[^[:alnum:]])be`, pg_trgm cannot expand
  the negated class, so the GIN scan matches every row. `\m` is ignored.
  Checked in `trgm_regexp.c` and `trgm_op.c`.
- Cost: four GIN indexes slow the location seed somewhat.

### Migration

- Revision `c69b88dfd949`. `make db-revision message="..."` (on a local DB)
  autogenerates the `drop_index("ix_locations_keywords")` and the four
  `create_index`; the `uq_emission_recalc_active_scoped` re-create it
  also emits is autogenerate noise and was pruned.
- Hand-added before them:
  `CREATE EXTENSION IF NOT EXISTS unaccent SCHEMA public` (`search_text`
  calls `public.unaccent`; without `SCHEMA` the extension lands in a
  role-named schema if one exists) and
  `CREATE OR REPLACE FUNCTION public.search_text`. `downgrade()` drops the
  function and the extension after the autogenerated index changes. Both
  are listed in `backend/alembic/CUSTOM_DB_OBJECTS.md`.
- The data_ingestion Postgres fixture builds the schema with
  `create_all`, so it creates `unaccent` and the function first, as it
  already does for `pg_trgm`. Function DDL lives once in
  `SEARCH_TEXT_FUNCTION_SQL`; the migration keeps its own frozen copy.

### Train reference data

The trainline-eu dump is multimodal, and the builder kept every suggestable
row. The reference held ~20 000 Swiss bus and tram stops and coach stops
abroad. Its `is_airport != t` filter dropped the airport railway stations
(Genève Aéroport, Zürich Flughafen), and nothing answered "Cornavin".

`backend/scripts/build_train_seed_from_trainline.py` now keeps:

- in CH, a row whose stop number, or failing that its name, is a `TRAIN` or
  `RACK_RAILWAY` service point in the official list (opentransportdata.swiss
  "Service Points (actual date)"). The name catches the Schaffhausen line,
  which trainline numbers the German way. A city row stays when one of its
  stations does.
- elsewhere, a row with a UIC code or a railway carrier, unless its name
  says bus (`BUS_NAME`). A row sold only by coach goes only in a country
  where trainline sells trains: elsewhere (BG, UA, BA, LT, GR) coach is
  all trainline sells, so it says nothing about the stop. This still drops
  the Dublin DART halts (Raheny, Sydney Parade) and PL Kłodzko and Piła;
  a national list, as for CH, would recover them.
- airports under the same rules.

Keywords hold the name, the Swiss official name, the de/en/fr/it names and
`ALIASES` (Cornavin, Hauptbahnhof, Sankt Gallen, Basle). The build fails
when an alias's station is no longer in the output.

Against the current reference: 51 299 → 25 660 rows. 25 559 natural keys
stay; 25 740 go (CH 20 268, ES 2 999, HR 572, IT 503, NO 299, IE 213, PL
169, FR 128); 101 arrive, all airport railway stations.

Open before the upload: **saved trips.** A train entry stores
`origin_natural_key` and `destination_natural_key`. If the upload removes
one, `pre_compute` logs a warning and returns `{}`, and the trip's emission
becomes zero without an error. Run the orphan query on each environment
first; remap or block.

Prod, 2026-10-27: 53 locations, 226 trips. 50 stay; 3 go, all bus stops in
the official list, 8 trips: Ecublens VD EPFL Piccard (4), St-Sulpice VD
Chantres (2), Zürich Flughafen REGA (2). Tracked in #3142; dev
and stage not checked yet.

## Not done

- `stores/unitFilters.ts` (backoffice reporting filters) has the same
  infinite-scroll shape, but the scroll never fires: `total_pages` is pinned
  to 1 and `currentPage*` is never incremented. Out of scope.
- Language variants need the names in `keywords`; folding accents does not
  bridge them. The train builder now writes the de/en/fr/it names
  (`Geneva`, `Bâle`, #1830); for planes, `Londres` and `Moscou` still
  come from hand edits to the reference CSV.
- Typo tolerance (`zurch` → Zürich) went with the 2026-06-15 switch to
  `ILIKE`; not restored.
- #2791 (explicit "no airport found" for plane) and #1436 (travel table
  filter) are separate issues.

## Tests

- `backend/tests/unit/v1/test_locations_search_endpoint.py` goes through
  the HTTP layer, so a mis-wired `Query` fails it too: `page=3&limit=10`
  binds `LIMIT 10 OFFSET 20`, the default page binds `OFFSET 0`, the order
  ends on `locations.id` for train and plane. `page=10001` and a 256-char
  `query` are 422s that never reach the DB. `genève aéroport` and
  `aéroport-genève` bind the same patterns; `zurich hb` binds a word-start
  `% hb%`. Every column the query searches has its `_trgm` index on the
  same `search_text()` expression.
- `backend/tests/integration/services/data_ingestion/test_location_search_pg.py`
  (Docker Postgres), the permanent regression suite. It seeds the reference
  rows, their keywords included, plus 300 fillers with repeated names. It
  checks every searchable QA case below, the DATA ones through the seeded
  keywords; a DATA case passes in the app only once the reference CSV
  carries the same keywords. It walks every page of a 300-row result:
  pages are disjoint and complete. An EXPLAIN ANALYZE checks that each word
  is served by all four `_trgm` bitmap index scans, each returning fewer
  rows than the fillers. A plan label alone is not enough: a match-all GIN
  scan is also a bitmap index scan.
- `backend/tests/unit/seed/test_build_train_seed_from_trainline.py`: on a
  small dump, Swiss railway and rack-railway stops stay, Swiss bus stops
  go, an airport railway station stays, a city stays for its station, and
  a bus-named row abroad goes. A coach-only row goes in a country where
  trainline sells trains and stays elsewhere. Genève carries "Cornavin"; a
  missing alias station fails the build.
- `frontend/tests/unit/location-search-paging.spec.ts`: page 1 returns a
  full page of 20, which leads to a request for page 2. Page 2 is short, so
  no page 3 is requested. `a ` sends no request and asks for 2 characters;
  no match says so; a failed page 1 shows the load error instead of a
  blank; a failed page 2 keeps the rows and shows the error; a late page-2
  failure of the previous query does not flag the new list; a pick emits
  the name and the location.

## QA cases

Mined from all 1 071 issues; 17 travel-search issues read. "DATA" depends
on `keywords`/Trainline rows, not on the search code.

| #   | mode  | type                                                                                                               | expect                                                                 | issues       |
| --- | ----- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- | ------------ |
| 1   | train | `ge`, scroll                                                                                                       | pages load; CH stations first; every row has a word starting with "ge" | #939, #429   |
| 2   | train | `be`                                                                                                               | Bern ranks high, reachable by scrolling                                | #939, #915   |
| 3   | train | `ber`                                                                                                              | Bern                                                                   | #939         |
| 4   | train | `Milan`                                                                                                            | Milano Centrale                                                        | #941, #915   |
| 5   | train | `Stuttgart`                                                                                                        | German stations, usable as origin and destination                      | #915         |
| 6   | train | `Strasbourg`, `Paris`, `Bonn`                                                                                      | stations found                                                         | #941         |
| 7   | train | `zurich`                                                                                                           | Zürich HB                                                              | #429, #939   |
| 8   | train | `zurch` (typo)                                                                                                     | no result, shown as an empty state, no hang                            | #429         |
| 9   | train | `zu`                                                                                                               | Zürich stations, no "No result" flash                                  | #942         |
| 10  | train | `zurich hb`                                                                                                        | Zürich HB first                                                        | #429         |
| 11  | train | `hb zurich`                                                                                                        | same as 10                                                             | rules        |
| 12  | train | `St Gallen`, `st. gallen`, `st-gallen`; `sankt gallen`                                                             | St. Gallen for the first three; `sankt` DATA                           | #429         |
| 13  | train | `geneve`, `Genève`, `Geneve`                                                                                       | Genève (main station; Cornavin is a keyword)                           | #2791, #939  |
| 14  | train | `Geneva`                                                                                                           | Genève (en name in keywords)                                           | #331, #1436  |
| 15  | train | `geneve aeroport`                                                                                                  | Genève Aéroport railway station, no ICC/WTC bus stops                  | #939         |
| 16  | train | `Genève Cornavin`, `Geneve-Cornavin`                                                                               | Genève first                                                           | #939         |
| 17  | train | `Lausanne`                                                                                                         | Lausanne (CH) first                                                    | #2791, #429  |
| 18  | train | `Bern`, `Berne`                                                                                                    | CH Bern first; DE "Berne" after, country shown                         | #1183, #1124 |
| 19  | train | `Berne`: DE as origin, CH as destination                                                                           | both selectable, saves without HTTP 500                                | #1124        |
| 20  | train | `Basel`/`Bâle`, `Lugano`, `Luzern`/`Lucerne`, `Biel`/`Bienne`, `Thun`, `Sion`, `Fribourg`, `Neuchâtel`/`Neuchatel` | CH station on top; FR/DE variants DATA                                 | #1830, #429  |
| 21  | train | `sai`                                                                                                              | European/CH rows before JP, IN, BR                                     | #941         |
| 22  | train | `g`                                                                                                                | the select waits for 2 characters; no hang, no flash                   | #939         |
| 23  | train | `zu`, switch tab, come back                                                                                        | list stays, no sticky "No result"                                      | #942         |
| 24  | train | type fast `g`,`ge`,`gen`,`gene`                                                                                    | final list matches `gene`                                              | #939, #942   |
| 25  | train | `ge`, scroll to the end                                                                                            | no duplicates or gaps; last page ends, no endless spinner              | #939         |
| 26  | train | scroll past page 1, then edit the query                                                                            | list restarts at page 1                                                | rules        |
| 27  | plane | `Paris`                                                                                                            | CDG and ORY, large airports first                                      | #331, #1439  |
| 28  | plane | `Lausanne`                                                                                                         | empty state (explicit message is #2791)                                | #2791        |
| 29  | plane | `Geneve`, `Genève`                                                                                                 | GVA                                                                    | #2791        |
| 30  | plane | `cdg`, `CDG`, `Cdg`                                                                                                | CDG first                                                              | #1439        |
| 31  | plane | `GVA`, `SFO`, `ZRH`                                                                                                | exact IATA first                                                       | #368, #18    |
| 32  | plane | `Charles de Gaulle`                                                                                                | CDG first                                                              | #1439        |
| 33  | plane | `roissy`                                                                                                           | CDG (keywords)                                                         | #1439        |
| 34  | plane | `Paris`, matched on municipality only                                                                              | CDG via "Paris (Roissy-en-France, Val-d'Oise)"                         | #1439        |
| 35  | plane | `London`; `Londres`                                                                                                | Heathrow, Gatwick…; `Londres` DATA                                     | #1436        |
| 36  | plane | `Moscow`, `Moscou`, `Moskva`                                                                                       | DATA; record the result                                                | #331         |
| 37  | plane | a query matching a large airport and a small airfield                                                              | large airport first                                                    | #331         |
| 38  | plane | `zzzzzz`                                                                                                           | empty state, EN and FR                                                 | #2791, #939  |
| 39  | both  | same query, FR then EN UI                                                                                          | same results; messages translated                                      | #2516, #2791 |
| 40  | both  | select a result, reopen the select                                                                                 | label shows name + country; entry saved with its natural_key           | #1124, #1183 |
| 41  | both  | round trip, then change origin                                                                                     | both ends resolve to the right places                                  | #18, #1124   |
| 42  | both  | every keystroke                                                                                                    | < 300 ms deployed, ideally ~100 ms                                     | #429         |
| 43  | both  | travel table loupe filter `London`                                                                                 | out of scope here, open as #1436                                       | #1436, #2516 |
| 44  | train | names with non-Latin letters                                                                                       | displayed without mojibake                                             | #331         |
| 45  | train | `Bern HB`, `Bern`                                                                                                  | no near-duplicate rows for one station (DATA)                          | #1183, #1305 |

## Performance (local DB, `be`/train)

| request                     | seq scan (before) | trigram indexes |
| --------------------------- | ----------------- | --------------- |
| page 1, `limit=10`          | 51–82 ms          | to measure      |
| page 3, `limit=10`          | 52–55 ms          | to measure      |
| page 30, `limit=10`         | 50 ms             | to measure      |
| page 272 (last), `limit=20` | 73 ms             | to measure      |

Walking all 272 pages returned 5 422 rows with 5 422 unique ids (contains
matching; word-start matching returns fewer).
