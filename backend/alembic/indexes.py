"""Shared partial-index WHERE predicates for hand-written migrations.

Keep these constants here rather than inlining them in migrations so
that:
- Predicates are readable (``IN (...)``) instead of the reflected PG
  form (``= ANY (ARRAY[...]::ingestion_state_enum[])``).
- Drop/recreate pairs always use the exact same predicate string,
  avoiding index-not-found errors from a mismatch.
- Adding a new job-type index requires one new constant + one migration,
  with zero duplication.

These are DB/performance concerns, not ORM concerns — do NOT drive index
creation from SQLAlchemy model metadata.
"""

AGG_WHERE: str = (
    "job_type = 'aggregation'"
    " AND state IN ("
    "'NOT_STARTED'::ingestion_state_enum,"
    " 'QUEUED'::ingestion_state_enum,"
    " 'RUNNING'::ingestion_state_enum"
    ")"
)

RECALC_WHERE: str = (
    "job_type = 'emission_recalc'"
    " AND state IN ("
    "'NOT_STARTED'::ingestion_state_enum,"
    " 'QUEUED'::ingestion_state_enum,"
    " 'RUNNING'::ingestion_state_enum"
    ")"
    " AND module_type_id IS NOT NULL"
    " AND data_entry_type_id IS NOT NULL"
    " AND year IS NOT NULL"
)
