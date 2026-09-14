"""Per-scope advisory locks shared by ingestion handlers (#1236 Phase 4B).

The invariant is **factor writes vs factor reads**: ``factor_ingest``
rewrites the ``factors`` row set for a ``(module_type_id, year)`` scope
while ``emission_recalc`` reads it. Without serialisation a recalc that
started mid-write computes emissions against half-loaded factor values —
silently wrong numbers, no error surfaced.

#2527 Phase B1 splits that into two lock modes, because "must not read
mid-write" never required data writers to serialise against each other:

- **Exclusive** ``(module_type_id, year)`` — the factor writer, and any
  recalc that rewrites the whole ``(det, year)`` slice.
- **Shared** ``(module_type_id, year)`` **plus exclusive on the
  ``carbon_report_module_id``** — a unit-scoped ``csv_ingest`` /
  ``api_ingest`` and the module-scoped ``emission_recalc`` it chains.
  They only read factors, so they share the factor gate; the rows they
  actually rewrite (the pre-import DELETE cascade and the emission
  rewrite) belong to one carbon report module, so that is what they take
  exclusively. Two units' uploads of the same module and year now run
  concurrently instead of head-to-tail.

Narrowing is only safe while module-scoped recalc children dedup on their
own key (``EMISSION_RECALC_SCOPED_DEDUP``, #2527 Phase A) —
``data_entry_emissions`` has no unique constraint, so nothing else stops
two identical scoped recalcs from double-writing. Pinned by
``tests/unit/tasks/test_scoped_dedup_ordering.py``.

Both modes acquire in the same order (factor gate first, module second),
so no pair of callers can deadlock.

Lock key encoding: 2-int variant ``pg_advisory_xact_lock(category, key)``
where ``category`` is a dedicated constant per lock space so we never
collide with other advisory-lock users (the aggregation per-year lock in
Phase 4A.2 uses a different category for the same reason).
``pg_advisory_xact_lock`` is held until the holding transaction commits
or rolls back — perfect fit for "hold for the duration of the handler's
data work."

Dialect-gated: on non-Postgres backends (the SQLite unit-test fixture)
the lock call is a no-op — SQLite's single-writer model already
serialises any concurrent writers, so the lock is unnecessary and the
``pg_advisory_xact_lock`` function doesn't exist there anyway.
"""

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

# Dedicated namespace for the factor-vs-recalc per-(module, year) gate.
# Distinct from the Phase 4A.2 aggregation per-year category (1236) so
# the two lock spaces never accidentally serialise unrelated work.
_FACTOR_RECALC_LOCK_CATEGORY = 1237

# Namespace for the per-carbon-report-module write mutex (#2527 B1).
# Its keys are raw carbon_report_module ids, so it needs a category of
# its own or a module id could collide with a packed (module, year) key.
_MODULE_WRITE_LOCK_CATEGORY = 1238

_LOCK_EXCLUSIVE_SQL = text("SELECT pg_advisory_xact_lock(:cat, :key)")
_LOCK_SHARED_SQL = text("SELECT pg_advisory_xact_lock_shared(:cat, :key)")


def _encode_module_year_key(module_type_id: int, year: int) -> int:
    """Pack ``(module_type_id, year)`` into a single int64 lock key.

    Module ids are tiny (< 100), years comfortably fit in 5 digits, so
    ``module * 100000 + year`` is collision-free and well within int64.
    """
    return module_type_id * 100_000 + year


def _is_postgres(data_session: AsyncSession) -> bool:
    """Advisory locks only exist on Postgres; other dialects no-op."""
    try:
        return data_session.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


async def acquire_factor_recalc_lock(
    data_session: AsyncSession,
    *,
    module_type_id: int | None,
    year: int | None,
    handler_label: str,
    carbon_report_module_id: int | None = None,
) -> None:
    """Acquire the factor gate for the duration of the caller's transaction.

    ``carbon_report_module_id`` set → the caller only reads factors and
    writes one carbon report module's rows: shared factor gate plus an
    exclusive lock on that module. Left ``None`` → exclusive factor gate,
    which is what a factor writer and a whole-slice recalc need. Callers
    that cannot narrow their scope must pass ``None``: over-serialising
    is slow, under-locking writes duplicate rows.

    No-op on non-Postgres or when scope is missing (defensive: skip
    rather than crash a job whose scope wasn't set — such a job is
    already wrong and the lock isn't what would save it).

    ``handler_label`` is plumbed through for the debug log so traces
    show which handler took the lock.
    """
    if module_type_id is None or year is None:
        logger.debug(
            f"{handler_label}: missing module_type_id or year — "
            "skipping factor/recalc advisory lock"
        )
        return
    if not _is_postgres(data_session):
        return
    key = _encode_module_year_key(int(module_type_id), int(year))
    locks = [(_LOCK_EXCLUSIVE_SQL, _FACTOR_RECALC_LOCK_CATEGORY, key)]
    if carbon_report_module_id is not None:
        locks = [
            (_LOCK_SHARED_SQL, _FACTOR_RECALC_LOCK_CATEGORY, key),
            (
                _LOCK_EXCLUSIVE_SQL,
                _MODULE_WRITE_LOCK_CATEGORY,
                int(carbon_report_module_id),
            ),
        ]
    for sql, category, lock_key in locks:
        await data_session.execute(sql, {"cat": category, "key": lock_key})
    logger.debug(
        f"{handler_label}: acquired {len(locks)} advisory lock(s) for "
        f"(module={module_type_id}, year={year}, "
        f"carbon_report_module={carbon_report_module_id})"
    )
