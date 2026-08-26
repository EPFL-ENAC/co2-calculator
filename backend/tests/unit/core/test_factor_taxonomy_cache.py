"""Tests for the process-local taxonomy TTL cache (#2258)."""

from app.core.factor_taxonomy_cache import _TTLCache


def test_set_then_get_returns_the_cached_value():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)
    cache.set(("k",), "v")

    assert cache.get(("k",)) == "v"


def test_get_missing_key_returns_none():
    cache = _TTLCache(ttl_seconds=60.0, max_entries=8)

    assert cache.get(("missing",)) is None


def test_entry_expires_after_ttl(monkeypatch):
    """The TTL is the cross-process safety net (see module docstring) —
    an entry must actually stop being served once it has expired.
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
