"""Process-local TTL cache for factor-derived taxonomy trees (#2258).

``GET /v1/taxonomies/module/{module}/{data_entry}`` rebuilds a
``TaxonomyNode`` tree from every ``factors`` row for a
``(data_entry_type, year)`` pair on each call — 1.3s of query plus 0.7s of
Python tree-building for the largest data entry type (20,915 rows). Factors
are reference data written only by an ingestion job, never per request, so
the result is safe to cache keyed on that pair.

Invalidation: every factor write in ``FactorRepository`` clears this cache
(see its call sites), which is exact and immediate *within one process*.
It is not enough on its own: ingestion jobs run in the dedicated poller-only
worker deployment (``helm/templates/backend-worker-deployment.yaml``),
never in the API pods that serve this endpoint, and the API itself runs
multiple uvicorn workers/pods (``backend/Dockerfile``, ``backend.replicaCount``
in ``helm/values.yaml``). A write-time ``clear()`` only ever reaches the one
process that happens to run it, so the other API workers keep serving their
already-cached tree until it expires. The TTL below is therefore the real
safety net across processes, not a fallback for a rare miss — keep it short.
"""

import time
from collections import OrderedDict

from app.schemas.taxonomy import TaxonomyNode

# Short enough to bound the cross-process staleness window (see module
# docstring) to something defensible for reference data that changes only
# via deliberate admin ingestion, not automatically; long enough to absorb
# the ~11 parallel taxonomy calls one report-page load fires. Public so the
# router can mirror it in a `Cache-Control: max-age` header.
TAXONOMY_CACHE_TTL_SECONDS = 60.0
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


# Module-level singleton: cheap to share across the service (reads) and the
# repository (write-time invalidation) without wiring it through either
# constructor — both sides operate on the process' own reference data.
taxonomy_cache: _TTLCache[TaxonomyNode] = _TTLCache(
    TAXONOMY_CACHE_TTL_SECONDS, _MAX_ENTRIES
)
