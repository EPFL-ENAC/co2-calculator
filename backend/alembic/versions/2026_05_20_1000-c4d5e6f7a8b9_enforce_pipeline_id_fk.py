# codeql[py/unused-global-variable]
"""enforce data_ingestion_jobs.pipeline_id FK (#1236 Phase 2)

Phase-1's ``add_pipelines_table`` migration deliberately left the
``data_ingestion_jobs.pipeline_id`` column as a plain UUID with no FK
so it could apply onto an existing DB without rejecting pre-Phase-1
rows whose pipeline_ids have no ``pipelines`` row.

v0.x drops the DB between deploys, so by the time this migration
applies on the next deployment cycle every ``pipeline_id`` in
``data_ingestion_jobs`` was minted *under Phase-1 code* and has a
matching ``pipelines`` row (via ``ensure_pipeline_exists``).  We can
therefore enforce the FK without a backfill.

Also adds an explicit index on ``pipeline_id``.  Postgres does NOT
auto-create an index on the referencing column of a foreign key, and
the console + recalc fan-out path query ``WHERE pipeline_id = …`` on
every poll.

Revision ID: c4d5e6f7a8b9
Revises: a3b8c9d0e1f2
Create Date: 2026-05-20 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

__all__ = [
    "revision",
    "down_revision",
    "branch_labels",
    "depends_on",
]


revision: str = "c4d5e6f7a8b9"  # noqa: F841
down_revision: Union[str, Sequence[str], None] = "a3b8c9d0e1f2"  # noqa: F841
branch_labels: Union[str, Sequence[str], None] = None  # noqa: F841
depends_on: Union[str, Sequence[str], None] = None  # noqa: F841


def upgrade() -> None:
    op.create_index(
        "ix_data_ingestion_jobs_pipeline_id",
        "data_ingestion_jobs",
        ["pipeline_id"],
        unique=False,
    )
    # Default ON DELETE RESTRICT: pipelines are append-only operational
    # ledger today (no delete code path).  RESTRICT refuses to drop a
    # pipeline that still has jobs — if we ever want to purge old
    # pipelines, jobs must be dropped first (explicit, not silent).
    op.create_foreign_key(
        "fk_data_ingestion_jobs_pipeline_id",
        "data_ingestion_jobs",
        "pipelines",
        ["pipeline_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_data_ingestion_jobs_pipeline_id",
        "data_ingestion_jobs",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_data_ingestion_jobs_pipeline_id",
        table_name="data_ingestion_jobs",
    )
