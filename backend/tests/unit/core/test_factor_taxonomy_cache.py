"""Tests for the process-local taxonomy TTL cache (#2258, #2391)."""

from app.core.factor_taxonomy_cache import (
    STARTED_YEAR_CACHE_TTL_SECONDS,
    TAXONOMY_CACHE_TTL_SECONDS,
    TaxonomyCacheEntry,
    _TTLCache,
    compute_taxonomy_etag,
)
from app.schemas.taxonomy import TaxonomyNode


def test_set_then_get_returns_the_cached_value():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)
    cache.set(("k",), "v")

    assert cache.get(("k",)) == "v"


def test_get_missing_key_returns_none():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)

    assert cache.get(("missing",)) is None


def test_entry_expires_after_ttl(monkeypatch):
    """An entry must actually stop being served once it has expired --
    the TTL is now a backstop for a missed broadcast, not the
    cross-process correctness mechanism (see module docstring, #2391).
    """
    now = 1000.0
    monkeypatch.setattr("app.core.factor_taxonomy_cache.time.monotonic", lambda: now)
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)
    cache.set(("k",), "v")

    now += 61.0
    assert cache.get(("k",)) is None


def test_entry_still_served_before_ttl_elapses(monkeypatch):
    now = 1000.0
    monkeypatch.setattr("app.core.factor_taxonomy_cache.time.monotonic", lambda: now)
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)
    cache.set(("k",), "v")

    now += 59.0
    assert cache.get(("k",)) == "v"


def test_clear_removes_every_entry():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)
    cache.set(("a",), 1)
    cache.set(("b",), 2)

    cache.clear()

    assert cache.get(("a",)) is None
    assert cache.get(("b",)) is None


def test_max_entries_evicts_least_recently_used():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=2)
    cache.set(("a",), 1)
    cache.set(("b",), 2)
    cache.set(("c",), 3)

    # ("a",) was the least recently touched when ("c",) pushed past capacity.
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == 2
    assert cache.get(("c",)) == 3


def test_ttl_raised_to_one_hour_now_broadcast_is_the_correctness_mechanism():
    """#2391 decision 2: cross-pod broadcast invalidation (#2280) makes the
    tree cache's TTL a backstop, not the staleness bound, so it can be
    sized for hit rate instead of the old 60s cross-process bound.
    """
    assert TAXONOMY_CACHE_TTL_SECONDS == 3600.0


def test_started_year_cache_ttl_stays_short():
    """Unlike the tree cache, is_started has no broadcast invalidation
    (see factor_taxonomy_cache module docstring) -- kept short so a flip
    from preparing to started reaches Cache-Control quickly.
    """
    assert STARTED_YEAR_CACHE_TTL_SECONDS == 60.0


def _tree(
    name: str = "root", children: list[TaxonomyNode] | None = None
) -> TaxonomyNode:
    return TaxonomyNode(name=name, label=name.title(), children=children)


def test_compute_taxonomy_etag_is_deterministic_for_the_same_content():
    """Same data → same ETag across cache rebuilds -- what lets every pod
    emit the identical ETag with zero per-request queries (#2391).
    """
    first = compute_taxonomy_etag(_tree(children=[_tree("a"), _tree("b")]))
    second = compute_taxonomy_etag(_tree(children=[_tree("a"), _tree("b")]))

    assert first == second


def test_compute_taxonomy_etag_ignores_child_order():
    """The factors query that feeds tree-building carries no ORDER BY (see
    module docstring) -- the hash must not flip just because the DB
    happened to return rows in a different order on a rebuild.
    """
    forward = _tree(children=[_tree("a"), _tree("b")])
    backward = _tree(children=[_tree("b"), _tree("a")])

    assert compute_taxonomy_etag(forward) == compute_taxonomy_etag(backward)


def test_compute_taxonomy_etag_changes_with_content():
    smaller = _tree(children=[_tree("a")])
    bigger = _tree(children=[_tree("a"), _tree("b")])

    assert compute_taxonomy_etag(smaller) != compute_taxonomy_etag(bigger)


def test_compute_taxonomy_etag_is_quoted_for_the_etag_header():
    etag = compute_taxonomy_etag(_tree())

    assert etag.startswith('"')
    assert etag.endswith('"')


def test_taxonomy_cache_entry_bundles_tree_and_etag():
    tree = _tree()
    entry = TaxonomyCacheEntry(tree=tree, etag=compute_taxonomy_etag(tree))
    cache: _TTLCache[TaxonomyCacheEntry] = _TTLCache(ttl_seconds=60.0, max_entries=8)

    cache.set(("k",), entry)
    cached = cache.get(("k",))

    assert cached is entry
    assert cached.tree is tree
