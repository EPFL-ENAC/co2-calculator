# codeql[py/unused-global-variable]
"""normalize ingestion index predicates

Revision ID: 9a1b2c3d4e5f
Revises: 8f29ed82872b
Create Date: 2026-05-12 14:44:00.000000

The previous migrations that created ``uq_aggregation_active`` and
``uq_emission_recalc_active`` used either a local inline predicate or
the PostgreSQL reflected form (``= ANY (ARRAY[...])``).  Alembic cannot
reliably round-trip advanced PostgreSQL partial-index predicates, so
autogenerate would keep proposing spurious drop/recreate cycles.

This migration drops both indexes and recreates them using the canonical
readable predicates from ``alembic.indexes``.  No data is affected.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from alembic.indexes import AGG_WHERE, RECALC_WHERE

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]

revision: str = "9a1b2c3d4e5f"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "8f29ed82872b"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    """Drop and recreate ingestion dedup indexes with canonical predicates."""
    op.drop_index("uq_aggregation_active", table_name="data_ingestion_jobs")
    op.create_index(
        "uq_aggregation_active",
        "data_ingestion_jobs",
        ["module_type_id", "year"],
        unique=True,
        postgresql_where=sa.text(AGG_WHERE),
    )

    op.drop_index("uq_emission_recalc_active", table_name="data_ingestion_jobs")
    op.create_index(
        "uq_emission_recalc_active",
        "data_ingestion_jobs",
        ["module_type_id", "data_entry_type_id", "year"],
        unique=True,
        postgresql_where=sa.text(RECALC_WHERE),
    )


def downgrade() -> None:
    """Restore indexes to state left by 8f29ed82872b.

    Clean predicates are still correct.
    """
    op.drop_index("uq_emission_recalc_active", table_name="data_ingestion_jobs")
    op.create_index(
        "uq_emission_recalc_active",
        "data_ingestion_jobs",
        ["module_type_id", "data_entry_type_id", "year"],
        unique=True,
        postgresql_where=sa.text(RECALC_WHERE),
    )

    op.drop_index("uq_aggregation_active", table_name="data_ingestion_jobs")
    op.create_index(
        "uq_aggregation_active",
        "data_ingestion_jobs",
        ["module_type_id", "year"],
        unique=True,
        postgresql_where=sa.text(AGG_WHERE),
    )
