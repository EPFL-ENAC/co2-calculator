"""Distinct authenticated users seen by this pod in the last 5 minutes (#2529).

``http.server.active_requests`` is a load proxy, not a user count: one user
pulling a 40-request page and forty idle users look the same. This gauge
counts people. ``touch()`` runs on every authenticated request from
``resolve_user_by_jwt_payload``, so it stays one dict write under the lock;
pruning happens in the callback, once per export interval.

The user id never leaves the process: the series carries no attributes, so
cardinality is one series per pod whatever the user count. Registered at
import time like ``db.pool.connections``; a no-op without a MeterProvider.
"""

import threading
from collections.abc import Iterable
from time import monotonic

from opentelemetry.metrics import CallbackOptions, Observation, get_meter

WINDOW_SECONDS = 300.0

# The callback runs on the SDK's metric-reader thread while touch() runs on
# the event loop; iterating a dict another thread is resizing raises.
_lock = threading.Lock()
_last_seen: dict[int, float] = {}


def touch(user_id: int | None) -> None:
    """Mark ``user_id`` as seen now."""
    if user_id is None:
        raise ValueError("active_users.touch() needs a persisted user id")
    now = monotonic()
    with _lock:
        _last_seen[user_id] = now


def _prune_and_count(now: float) -> int:
    """Drop users idle past the window; memory stays bounded by the window."""
    cutoff = now - WINDOW_SECONDS
    with _lock:
        for user_id in [u for u, seen in _last_seen.items() if seen < cutoff]:
            del _last_seen[user_id]
        return len(_last_seen)


def _active_users_callback(_options: CallbackOptions) -> Iterable[Observation]:
    yield Observation(_prune_and_count(monotonic()))


get_meter(__name__).create_observable_gauge(
    "co2.active_users_5m",
    callbacks=[_active_users_callback],
    unit="{user}",
    description="Distinct authenticated users seen by this pod in the last 5 minutes",
)
