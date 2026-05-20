"""Per-scope advisory locks shared by ingestion handlers (#1236 Phase 4B).

Factor writes and emission recalcs for the SAME ``(module_type_id, year)``
scope must not run concurrently. Both reach the same ``factors`` row set:
``factor_ingest`` writes, ``emission_recalc`` reads. Without serialisation
a recalc that started mid-write computes emissions against half-loaded
factor values — silently wrong numbers, no error surfaced.

This module provides a transaction-scoped Postgres advisory lock both
handlers acquire at the start of the work. ``pg_advisory_xact_lock`` is
held until the holding transaction commits or rolls back — perfect fit
for "hold for the duration of the handler's data work."

Lock key encoding: 2-int variant ``pg_advisory_xact_lock(category, key)``
where ``category`` is a dedicated #1236-Phase-4B constant so we never
collide with other advisory-lock users (the aggregation per-year lock
in Phase 4A.2 uses a different category for the same reason).

Dialect-gated: on non-Postgres backends (the SQLite unit-test fixture)
the lock call is a no-op — SQLite's single-writer model already
serialises any concurrent writers, so the lock is unnecessary and the
``pg_advisory_xact_lock`` function doesn't exist there anyway.
"""

from typing import Optional

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

# Dedicated namespace for the factor-vs-recalc per-(module, year) mutex.
# Distinct from the Phase 4A.2 aggregation per-year category (1236) so
# the two lock spaces never accidentally serialise unrelated work.
_FACTOR_RECALC_LOCK_CATEGORY = 1237


def _encode_module_year_key(module_type_id: int, year: int) -> int:
    """Pack ``(module_type_id, year)`` into a single int64 lock key.

    Module ids are tiny (< 100), years comfortably fit in 5 digits, so
    ``module * 100000 + year`` is collision-free and well within int64.
    """
    return module_type_id * 100_000 + year


async def acquire_factor_recalc_lock(
    data_session: AsyncSession,
    *,
    module_type_id: Optional[int],
    year: Optional[int],
    handler_label: str,
) -> None:
    """Acquire the per-``(module, year)`` mutex for the duration of the
    caller's transaction. No-op on non-Postgres or when scope is missing
    (defensive: skip rather than crash a job whose scope wasn't set —
    such a job is already wrong and the lock isn't what would save it).

    ``handler_label`` is plumbed through for the debug log so traces
    show which handler took the lock.
    """
    if module_type_id is None or year is None:
        logger.debug(
            f"{handler_label}: missing module_type_id or year — "
            "skipping factor/recalc advisory lock"
        )
        return
    try:
        dialect_name = data_session.get_bind().dialect.name
    except Exception:
        dialect_name = ""
    if dialect_name != "postgresql":
        return
    key = _encode_module_year_key(int(module_type_id), int(year))
    await data_session.execute(
        text("SELECT pg_advisory_xact_lock(:cat, :key)"),
        {"cat": _FACTOR_RECALC_LOCK_CATEGORY, "key": key},
    )
    logger.debug(
        f"{handler_label}: acquired pg_advisory_xact_lock"
        f"({_FACTOR_RECALC_LOCK_CATEGORY}, {key}) for "
        f"(module={module_type_id}, year={year})"
    )
