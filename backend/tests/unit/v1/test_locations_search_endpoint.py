"""#939 — ``GET /locations/search`` pages and matches word by word.

FastAPI drops undeclared query params, so ``page`` used to be ignored and
every page returned the same first ``limit`` rows. Goes through the HTTP
layer on purpose: a direct call to the route function would not catch a
mis-wired ``Query``.
"""

import re
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.location import Location


def _stub_user():
    """Named function, not ``MagicMock``: FastAPI reads the override's
    signature and would turn ``*args, **kw`` into query params.
    """
    return MagicMock()


# The id tiebreaker sits right before LIMIT: names repeat, and without a
# total order consecutive pages could overlap or skip rows.
_TAIL = re.compile(r"locations\.id ASC\s+LIMIT %\((\w+)\)s\S* OFFSET %\((\w+)\)s")


def _search(params: dict) -> tuple[int, AsyncMock]:
    session = AsyncMock()
    session.execute.return_value = MagicMock(fetchall=MagicMock(return_value=[]))
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = _stub_user
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/locations/search", params=params)
    finally:
        app.dependency_overrides.clear()
    return response.status_code, session


def _compiled(params: dict):
    status_code, session = _search(params)
    assert status_code == 200
    return session.execute.call_args.args[0].compile(dialect=postgresql.dialect())


def _limit_offset(params: dict) -> tuple[int, int]:
    compiled = _compiled(params)
    tail = _TAIL.search(str(compiled))
    assert tail, str(compiled)
    return compiled.params[tail[1]], compiled.params[tail[2]]


def test_page_offsets_the_ranked_search():
    params = {"query": "be", "transport_mode": "train", "limit": 10, "page": 3}
    assert _limit_offset(params) == (10, 20)


def test_page_defaults_to_the_first():
    params = {"query": "be", "transport_mode": "train", "limit": 10}
    assert _limit_offset(params) == (10, 0)


def test_plane_search_pages_on_the_same_total_order():
    params = {"query": "be", "transport_mode": "plane", "page": 2}
    assert _limit_offset(params) == (5, 5)


def test_page_past_the_cap_is_rejected_before_the_offset_overflows():
    params = {"query": "be", "transport_mode": "train", "limit": 20}
    assert _limit_offset({**params, "page": 10_000}) == (20, 199_980)
    # Uncapped, page 107_374_184 overflows OFFSET $n::INTEGER: a 500.
    status_code, session = _search({**params, "page": 10_001})
    assert status_code == 422
    session.execute.assert_not_called()


def test_query_longer_than_the_searched_columns_is_rejected():
    _compiled({"query": "a" * 255, "transport_mode": "train"})
    status_code, session = _search({"query": "a" * 256, "transport_mode": "train"})
    assert status_code == 422
    session.execute.assert_not_called()


def _word_patterns(query: str) -> list[str]:
    compiled = _compiled({"query": query, "transport_mode": "train"})
    values = compiled.params.values()
    return sorted(v for v in values if isinstance(v, str) and v.startswith("%"))


def test_separators_and_word_order_do_not_matter():
    """One ``%genève aéroport%`` pattern never matched "Genève-Aéroport"."""
    expected = ["%aéroport%", "%genève%"]
    assert _word_patterns("genève aéroport") == expected
    assert _word_patterns("aéroport-genève") == expected


def test_short_words_match_a_word_start():
    """``be`` listed Oberhausen; a 1-2 letter word now starts a word."""
    assert _word_patterns("zurich hb") == ["% hb%", "%zurich%"]


def test_accents_fold_and_the_spelling_typed_ranks_first():
    """A search for ``zurich`` found no ``Zürich`` station before ``unaccent``."""
    sql = str(_compiled({"query": "neuchâtel", "transport_mode": "train"}))
    assert re.search(r"ILIKE unaccent\(%\(\w+\)s", sql), sql
    assert re.search(r"similarity\(name, %\(query\)s\) DESC", sql), sql


def test_every_searched_column_has_its_trigram_index():
    """The 2026-06 migration collapse turned these indexes into btrees and
    every search scanned the table; a column searched without its index, or
    on a different expression, is that regression again.
    """
    sql = str(_compiled({"query": "bern", "transport_mode": "train"}))
    searched = set(re.findall(r"search_text\(locations\.(\w+)\) ILIKE", sql))
    indexed = {
        match[1]
        for index in Location.__table__.indexes
        if index.dialect_options["postgresql"]["using"] == "gin"
        for match in [
            re.fullmatch(r"search_text\(\((\w+)\)::text\)", str(index.expressions[0]))
        ]
        if match
    }
    assert searched == indexed == {"name", "iata_code", "municipality", "keywords"}
