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
    added (#2654). Backfill it from the value that was always there —
    ``meta.config.carbon_report_module_id`` — then forbid the shape.

    The check is added validating (not ``NOT VALID``): the table is small,
    and a ``MODULE_UNIT_SPECIFIC`` row with no recoverable module id is
    exactly the thing that must stop the deploy rather than pass quietly.
    Pre-flight on each environment::

        SELECT id, job_type, created_at
        FROM data_ingestion_jobs
        WHERE entity_type = 'MODULE_UNIT_SPECIFIC'
          AND entity_id IS NULL
          AND (meta -> 'config' ->> 'carbon_report_module_id') !~ '^[0-9]+$';

    Autogenerate also proposed dropping ``ix_classification_translations_label_trgm``
    and re-creating ``uq_emission_recalc_active_scoped`` with a differently
    formatted expression; both are false positives and were pruned.
    """
    op.execute(
        "UPDATE data_ingestion_jobs "
        "SET entity_id = (meta -> 'config' ->> 'carbon_report_module_id')::int "
        "WHERE entity_type = 'MODULE_UNIT_SPECIFIC' "
        "AND entity_id IS NULL "
        "AND (meta -> 'config' ->> 'carbon_report_module_id') ~ '^[0-9]+$'"
    )
    op.create_check_constraint(
        "ck_data_ingestion_jobs_unit_specific_has_entity_id",
        "data_ingestion_jobs",
        "entity_type <> 'MODULE_UNIT_SPECIFIC' OR entity_id IS NOT NULL",
    )


def downgrade() -> None:
    """Downgrade schema. The backfilled ids are left in place."""
    op.drop_constraint(
        "ck_data_ingestion_jobs_unit_specific_has_entity_id",
        "data_ingestion_jobs",
        type_="check",
    )
