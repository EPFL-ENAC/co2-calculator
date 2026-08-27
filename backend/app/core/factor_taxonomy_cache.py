"""Process-local caches for factor-derived taxonomy data (#2258, #2391).

``GET /v1/taxonomies/module/{module}/{data_entry}`` rebuilds a
``TaxonomyNode`` tree from every ``factors`` row for a
``(data_entry_type, year)`` pair on each call — 1.3s of query plus 0.7s of
Python tree-building for the largest data entry type (20,915 rows). Factors
are reference data written only by an ingestion job, never per request, so
the result is safe to cache keyed on that pair.

Invalidation: every factor write in ``FactorRepository`` clears this cache
(see its call sites) and, since #2280, broadcasts that clear to every other
live API pod (``app/core/taxonomy_cache_broadcast.py`` +
``app/api/internal.py``) — exact, cross-process invalidation within one HTTP
round trip of the write that changed the data. The TTL below is no longer
what keeps this cache correct; it is only the backstop for whatever the
broadcast doesn't reach (a pod mid-restart, a network blip, a broadcast bug),
so it can be sized for hit rate rather than staleness.
"""

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass

from app.schemas.taxonomy import TaxonomyNode

# Sized for hit rate now that cross-pod broadcast invalidation (#2280) is the
# correctness mechanism (see module docstring), not a staleness bound -- an
# hour comfortably outlives normal request traffic between deliberate CSV
# ingestions, while still self-healing from a broadcast a dead or
# restarting pod never received. Public so tests can assert against it.
TAXONOMY_CACHE_TTL_SECONDS = 3600.0
# Bounded by data_entry_type × year combinations actually queried, but that
# grows over uptime as users browse historical years — cap it so a busy
# instance can't accumulate one multi-MB tree (det=66 is ~20k rows) per
# worker process indefinitely.
_MAX_ENTRIES = 64


class _TTLCache[T]:
    """Tiny LRU + TTL cache — no external dependency needed for this size."""

    def __init__(self, ttl_seconds: float, max_entries: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple, tuple[float, T]] = OrderedDict()

    def get(self, key: tuple) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, key: tuple, value: T) -> None:
        self._entries[key] = (time.monotonic() + self._ttl_seconds, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()


@dataclass(frozen=True, slots=True)
class TaxonomyCacheEntry:
    """A built tree plus the ETag for its exact content (#2391 decision 2).

    Both travel together so every pod serving this ``(data_entry_type,
    year)`` from cache reuses the ETag computed once at build time instead
    of recomputing it per request — same DB, same marker, so every pod
    emits the identical ETag for identical data with zero extra queries.
    """

    tree: TaxonomyNode
    etag: str


def _canonical_taxonomy(node: TaxonomyNode) -> dict:
    """Order-independent dict for ``compute_taxonomy_etag`` below.

    Children are sorted by name so the hash is stable across rebuilds even
    though the factors query that feeds tree-building carries no
    ``ORDER BY`` — only the resulting node set matters, never incidental
    row order.
    """
    children = sorted(
        (_canonical_taxonomy(child) for child in node.children or []),
        key=lambda child: child["name"],
    )
    return {
        "name": node.name,
        "label": node.label,
        "translation_key": node.translation_key,
        "meta": node.meta,
        "children": children,
    }


def compute_taxonomy_etag(node: TaxonomyNode) -> str:
    """Deterministic content hash of a tree, quoted ready for an ETag header.

    ``factors`` carries no updated-at/created-at column (see
    ``app/models/factor.py``) to use as an ingestion marker, and a CSV
    ingestion touches many rows with no single "last write" timestamp to
    key off either — so there is no cheap marker to hash instead of the
    content itself. Hashing the tree is exact by construction: identical
    factors always build an identical tree, and any real data change flips
    the hash.
    """
    payload = json.dumps(
        _canonical_taxonomy(node), sort_keys=True, separators=(",", ":")
    ).encode()
    return f'"{hashlib.sha256(payload).hexdigest()}"'


# Module-level singleton: cheap to share across the service (reads) and the
# repository (write-time invalidation) without wiring it through either
# constructor — both sides operate on the process' own reference data.
taxonomy_cache: _TTLCache[TaxonomyCacheEntry] = _TTLCache(
    TAXONOMY_CACHE_TTL_SECONDS, _MAX_ENTRIES
)

# Separate, short-lived cache for the (year, provider) -> is_started lookup
# that decides each taxonomies response's Cache-Control max-age (#2391
# decision 2). Kept alongside the taxonomy cache above because it exists
# for the same reason: the batch route can resolve up to ~11 entries per
# request, and without this every one of them would re-query
# year_configuration for a value that's identical across all of them. Short
# TTL, not broadcast-invalidated: ``is_started`` only ever flips prep ->
# started, never back (the lifecycle invariant this cache-control split is
# built on), so a few stale seconds of "not started yet" costs a browser
# one extra revalidation at worst -- never wrong data, since the ETag above
# is what actually governs correctness.
STARTED_YEAR_CACHE_TTL_SECONDS = 60.0
started_year_cache: _TTLCache[bool] = _TTLCache(
    STARTED_YEAR_CACHE_TTL_SECONDS, _MAX_ENTRIES
)
