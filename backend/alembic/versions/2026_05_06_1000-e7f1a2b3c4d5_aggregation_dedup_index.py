# codeql[py/unused-global-variable]
"""aggregation dedup-active partial unique index

Revision ID: e7f1a2b3c4d5
Revises: d3e5f7a9b1c4
Create Date: 2026-05-06 10:00:00.000000

Plan 310-D — partial unique index that prevents N redundant
``aggregation`` jobs being created when ``factor_ingest`` fan-out
chains N ``emission_recalc`` children for the same
``(module_type_id, year)``.

Each child wants to chain a follow-up ``aggregation`` job for the
same scope.  Without dedup that's N aggregation jobs.  With this
index, ``chain_job(dedup_active=True)`` (added in a separate PR)
uses ``INSERT ... ON CONFLICT DO NOTHING`` — the first child wins,
the rest see the existing pending row and skip.  Once the first
aggregation finishes (state=FINISHED), the index permits a new
aggregation row, so subsequent fan-out batches stay correct.

The WHERE clause covers every non-terminal state — ``NOT_STARTED``,
``QUEUED``, ``RUNNING`` — so dedup applies for the entire window
between "we want one" and "the work is done".  ``FINISHED`` rows
are excluded so historical aggregation jobs don't block future
ones for the same scope.

State values use native PG enum labels because the column is
``SAEnum(IngestionState, name='ingestion_state_enum',
native_enum=True)``; mirrors the existing
``ix_data_ingestion_jobs_pending`` partial-index style.

Chains off ``d3e5f7a9b1c4`` (Plan 310-C observability columns) —
``feat/310c-handler-registrations`` (PR #1048) carries no migrations
of its own, so dev's head ``d3e5f7a9b1c4`` is also our parent.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "e7f1a2b3c4d5"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "d3e5f7a9b1c4"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


_INDEX_NAME = "uq_aggregation_active"
_TABLE_NAME = "data_ingestion_jobs"
_PARTIAL_WHERE = (
    "job_type = 'aggregation' "
    "AND state IN ("
    "'NOT_STARTED'::ingestion_state_enum, "
    "'QUEUED'::ingestion_state_enum, "
    "'RUNNING'::ingestion_state_enum"
    ")"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        ["module_type_id", "year"],
        unique=True,
        postgresql_where=sa.text(_PARTIAL_WHERE),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        _INDEX_NAME,
        table_name=_TABLE_NAME,
        postgresql_where=sa.text(_PARTIAL_WHERE),
    )
