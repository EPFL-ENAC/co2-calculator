# codeql[py/unused-global-variable]
"""emission_recalc dedup-active partial unique index

Revision ID: f8a9b1c2d3e4
Revises: e7f1a2b3c4d5
Create Date: 2026-05-07 14:32:00.000000

Plan 310-D / #1064 — partial unique index that prevents redundant
``emission_recalc`` jobs being created when ``factor_ingest`` fan-out
chains ``emission_recalc`` children for the same
``(module_type_id, data_entry_type_id, year)`` scope back-to-back.

Generalises the dedup pattern introduced for ``aggregation`` in
``e7f1a2b3c4d5`` to a second job type.  The dedup contract lives in
``app.tasks._chain.DedupConfig`` so additional consumers can opt in
with one new ``DedupConfig`` instance + one matching partial index
migration.

The WHERE clause covers every non-terminal state (``NOT_STARTED``,
``QUEUED``, ``RUNNING``) so dedup applies for the entire window
between "we want one" and "the work is done".  ``FINISHED`` rows
are excluded so historical recalcs don't block future ones for the
same scope (each fan-out batch gets its own recalc; subsequent
batches are not blocked by completed history).

The scope keys are required NOT NULL in the partial WHERE — Postgres
treats NULLs as distinct in unique indexes by default, so an index
without those guards would silently allow duplicates whenever any
key was NULL.  The matching ``chain_job`` entry validation refuses
NULL scope values for any ``DedupConfig`` so prod paths can't reach
the index with NULLs anyway, but the guard keeps the index correct
in isolation.

State values use native PG enum labels because the column is
``SAEnum(IngestionState, name='ingestion_state_enum',
native_enum=True)``; mirrors the existing ``uq_aggregation_active``
and ``ix_data_ingestion_jobs_pending`` partial-index style.

Uses ``CREATE UNIQUE INDEX CONCURRENTLY`` inside an autocommit_block
so the migration cannot block writers on ``data_ingestion_jobs``
while it runs.  The aggregation index migration was created on a
fresh table and didn't need this; the emission_recalc index lands
on a table that's already hot in dev/staging environments.
"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "f8a9b1c2d3e4"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "e7f1a2b3c4d5"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


_INDEX_NAME = "uq_emission_recalc_active"


def upgrade() -> None:
    """Upgrade schema."""
    # CONCURRENTLY cannot run inside a transaction; autocommit_block
    # detaches the connection from Alembic's per-migration transaction
    # for the duration of this statement.  Equivalent to running this
    # migration with transaction_per_migration=False, but scoped.
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX_NAME}
              ON data_ingestion_jobs (module_type_id, data_entry_type_id, year)
              WHERE job_type = 'emission_recalc'
                AND state IN (
                    'NOT_STARTED'::ingestion_state_enum,
                    'QUEUED'::ingestion_state_enum,
                    'RUNNING'::ingestion_state_enum
                )
                AND module_type_id IS NOT NULL
                AND data_entry_type_id IS NOT NULL
                AND year IS NOT NULL
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX_NAME}")
