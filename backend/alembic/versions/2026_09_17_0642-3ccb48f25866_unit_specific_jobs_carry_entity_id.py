# codeql[py/unused-global-variable]
"""unit specific jobs carry entity_id

Revision ID: 3ccb48f25866
Revises: c1f2a3b4d5e6
Create Date: 2026-09-17 06:42:11.794294

"""

from collections.abc import Sequence

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


# revision identifiers, used by Alembic.
revision: str = "3ccb48f25866"  # noqa: F841
down_revision: str | Sequence[str] | None = "c1f2a3b4d5e6"  # noqa: F841
branch_labels: str | Sequence[str] | None = None  # noqa: F841
depends_on: str | Sequence[str] | None = None  # noqa: F841


def upgrade() -> None:
    """Upgrade schema.

    ``data_ingestion_jobs.entity_id`` is the column every ``/sync`` read gate
    resolves a job's unit from, and nothing wrote it from the day it was
    added (#2654). From here on a ``MODULE_UNIT_SPECIFIC`` row must carry it.

    ``NOT VALID``, as in c1f2a3b4d5e6: binds every INSERT and UPDATE, skips
    the table scan, and leaves the historical NULL rows alone — they are
    finished jobs nobody streams or recovers, so scoping them buys nothing.

    Autogenerate also proposed dropping ``ix_classification_translations_label_trgm``
    and re-creating ``uq_emission_recalc_active_scoped`` with a differently
    formatted expression; both are false positives and were pruned.
    """
    op.create_check_constraint(
        "ck_data_ingestion_jobs_unit_specific_has_entity_id",
        "data_ingestion_jobs",
        "entity_type <> 'MODULE_UNIT_SPECIFIC' OR entity_id IS NOT NULL",
        postgresql_not_valid=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_data_ingestion_jobs_unit_specific_has_entity_id",
        "data_ingestion_jobs",
        type_="check",
    )
